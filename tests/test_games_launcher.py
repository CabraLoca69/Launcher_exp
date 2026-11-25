import os
from datetime import datetime, timedelta
from types import SimpleNamespace

import psutil
import pytest

from helpers import games_launcher
from helpers.games_launcher import GameLauncherController

DEAD_PID = 2**22 + 12345  # por encima de pid_max por defecto en Linux


@pytest.fixture
def fake_launch(monkeypatch):
    """Corre la partida de forma síncrona con un runner falso que 'termina' al instante."""
    runner = SimpleNamespace(calls=[])

    def run(path, steam_appid=None):
        runner.calls.append((path, steam_appid))
        return SimpleNamespace(pid=DEAD_PID)

    runner.run = run

    def sync_thread(target, *args, daemon=True, **kwargs):
        if target.__name__ == "_run_session":  # el heartbeat no se corre (espera 60s)
            target(*args, **kwargs)

    monkeypatch.setattr(games_launcher, "safe_thread", sync_thread)
    monkeypatch.setattr(
        games_launcher, "PlatformHandler", lambda: SimpleNamespace(get=lambda k: runner)
    )
    return runner


def test_launch_game_runs_and_records_closed_session(store, fake_launch):
    store.add_game("steam", "a", "/g/a.exe")
    store.set_steam_appid("steam", "a", "620")

    GameLauncherController().launch_game("a")

    assert fake_launch.calls == [("/g/a.exe", "620")]
    [session] = store.recent_sessions("steam", "a")
    assert session.ended_at is not None
    assert store.open_sessions() == []


def test_launch_game_with_platform_uses_that_platform(store, fake_launch):
    store.add_game("steam", "a", "/steam/a.exe")
    store.add_game("gog", "a", "/gog/a.exe")

    GameLauncherController().launch_game("a", "gog")

    assert fake_launch.calls == [("/gog/a.exe", None)]
    assert store.recent_sessions("steam", "a") == []
    assert len(store.recent_sessions("gog", "a")) == 1


def test_launch_game_unknown_raises(store, fake_launch):
    store.add_game("steam", "a", "/steam/a.exe")
    with pytest.raises(ValueError):
        GameLauncherController().launch_game("a", "gog")
    with pytest.raises(ValueError):
        GameLauncherController().launch_game("nope")
    assert fake_launch.calls == []


def test_upload_on_close_runs_in_the_session_thread(store, fake_launch, monkeypatch):
    """Con `--launch` el proceso sale al terminar la partida: la subida no puede
    quedar en un hilo daemon que muera antes de terminar."""
    uploads = []
    monkeypatch.setattr(
        games_launcher, "sync_once", lambda upload: uploads.append(upload)
    )
    store.set_setting("cloud_sync_enabled", True)
    store.add_game("steam", "a", "/g/a.exe")

    GameLauncherController().launch_game("a")  # el fixture lo corre síncrono

    assert uploads == [True]


def _running(store, platform, game):
    store.add_game(platform, game, f"/{game}")
    return store.start_session(store.get_game(platform, game).id, "pc", pid=os.getpid())


def test_launch_game_skips_game_already_running(store, fake_launch):
    _running(store, "steam", "a")
    GameLauncherController().launch_game("a")
    assert fake_launch.calls == []


def test_launch_game_without_multiple_allowed_and_nothing_running(store, fake_launch):
    store.set_setting("allow_multiple_games", False)
    store.add_game("steam", "a", "/g/a.exe")
    GameLauncherController().launch_game("a")
    assert len(fake_launch.calls) == 1


def test_launch_game_blocked_when_another_is_running(store, fake_launch):
    store.set_setting("allow_multiple_games", False)
    store.add_game("steam", "a", "/g/a.exe")
    _running(store, "steam", "otro")
    GameLauncherController().launch_game("a")
    assert fake_launch.calls == []


def _session(pid, started_at):
    return SimpleNamespace(pid=pid, started_at=started_at.isoformat(timespec="seconds"))


def test_session_alive_only_for_the_process_we_launched():
    me = psutil.Process()
    after_me = datetime.fromtimestamp(me.create_time()) + timedelta(seconds=1)
    assert games_launcher.is_session_alive(_session(os.getpid(), after_me))
    assert not games_launcher.is_session_alive(_session(DEAD_PID, after_me))


def test_reused_pid_after_reboot_is_not_the_game():
    """La sesión empezó antes de que existiera el proceso con ese PID: es otro."""
    long_ago = datetime(2020, 1, 1)
    assert not games_launcher.is_session_alive(_session(os.getpid(), long_ago))
