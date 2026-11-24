import os
from types import SimpleNamespace

import pytest

from helpers import games_launcher
from helpers.games_launcher import GameLauncherController, SessionsCleaner

DEAD_PID = 2**22 + 12345  # por encima de pid_max por defecto en Linux


def test_sessions_cleaner_drops_dead_and_keeps_alive(clean_db):
    alive = os.getpid()
    clean_db.set("global.actual_running.alive", {"pid": alive})
    clean_db.set("global.actual_sessions.alive", {"pid": alive, "start_time": "t"})
    clean_db.set("global.actual_running.dead", {"pid": DEAD_PID})
    clean_db.set("global.actual_sessions.dead", {"pid": DEAD_PID, "start_time": "t"})

    SessionsCleaner().clean_orphaned_sessions()

    assert clean_db.get_children("global.actual_running") == {"alive": {"pid": alive}}
    assert list(clean_db.get_children("global.actual_sessions")) == ["alive"]


def test_update_playtime_accumulates_total_and_updates_session(clean_db):
    c = GameLauncherController()
    c._update_playtime_records("steam", "a", "pc1", 1.5, 0, 90, "2026-01-01 10:00:00")
    c._update_playtime_records("steam", "a", "pc1", 1.5, 0, 180, "2026-01-01 10:00:00")

    assert clean_db.get("steam.game_total_times.a.pc1") == 3.0
    assert clean_db.get("steam.game_times.a") == [
        {"Start": "2026-01-01 10:00:00", "Tiempo": 3.0}
    ]


def test_update_playtime_keeps_last_five_sessions(clean_db):
    c = GameLauncherController()
    for i in range(7):
        c._update_playtime_records("steam", "a", "pc1", 1, 0, 60, f"s{i}")
    assert [s["Start"] for s in clean_db.get("steam.game_times.a")] == [
        f"s{i}" for i in range(2, 7)
    ]


@pytest.fixture
def fake_launch(monkeypatch):
    """Corre launch_game de forma síncrona con un runner falso que 'termina' al instante."""
    runner = SimpleNamespace(calls=[])

    def run(path):
        runner.calls.append(path)
        return SimpleNamespace(pid=DEAD_PID)

    runner.run = run

    def sync_thread(target, *args, daemon=True, **kwargs):
        if target.__name__ == "execute":  # el periodic_saver no se corre (duerme 60s)
            target(*args, **kwargs)

    monkeypatch.setattr(games_launcher, "safe_thread", sync_thread)
    monkeypatch.setattr(
        games_launcher, "PlatformHandler", lambda: SimpleNamespace(get=lambda k: runner)
    )
    return runner


def test_launch_game_runs_and_records_session(clean_db, fake_launch):
    clean_db.set("global.allow_multiple_games", True)
    clean_db.set("steam.game_list.a", "/g/a.exe")

    GameLauncherController().launch_game("a")

    assert fake_launch.calls == ["/g/a.exe"]
    assert len(clean_db.get("steam.game_times.a")) == 1
    assert clean_db.get_children("global.actual_running") == {}


def test_launch_game_without_multiple_allowed_and_nothing_running(
    clean_db, fake_launch
):
    clean_db.set("global.allow_multiple_games", False)
    clean_db.set("steam.game_list.a", "/g/a.exe")

    GameLauncherController().launch_game("a")

    assert fake_launch.calls == ["/g/a.exe"]


def test_launch_game_blocked_when_another_is_running(clean_db, fake_launch):
    clean_db.set("global.allow_multiple_games", False)
    clean_db.set("steam.game_list.a", "/g/a.exe")
    clean_db.set("global.actual_running.otro", {"pid": os.getpid()})

    GameLauncherController().launch_game("a")

    assert fake_launch.calls == []


def test_launch_game_with_platform_uses_that_platform(clean_db, fake_launch):
    clean_db.set("global.allow_multiple_games", True)
    clean_db.set("steam.game_list.a", "/steam/a.exe")
    clean_db.set("gog.game_list.a", "/gog/a.exe")

    GameLauncherController().launch_game("a", "gog")

    assert fake_launch.calls == ["/gog/a.exe"]
    assert clean_db.get("steam.game_times.a") is None
    assert len(clean_db.get("gog.game_times.a")) == 1


def test_launch_game_unknown_in_platform_raises(clean_db, fake_launch):
    clean_db.set("steam.game_list.a", "/steam/a.exe")
    with pytest.raises(ValueError):
        GameLauncherController().launch_game("a", "gog")
    assert fake_launch.calls == []
