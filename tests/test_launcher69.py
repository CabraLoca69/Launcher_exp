import pytest

import launcher69


def test_parse_launch_with_platform():
    args = launcher69.parse_args(["--launch", "Hollow", "--platform", "steam"])
    assert (args.launch, args.platform) == ("Hollow", "steam")


def test_parse_launch_without_platform_is_allowed():
    assert launcher69.parse_args(["--launch", "Hollow"]).platform is None


def test_parse_launch_without_name_exits():
    with pytest.raises(SystemExit):
        launcher69.parse_args(["--launch"])


def test_parse_platform_without_launch_exits():
    with pytest.raises(SystemExit):
        launcher69.parse_args(["--platform", "steam"])


def test_parse_ignores_unknown_args():
    assert launcher69.parse_args(["-style", "fusion"]).launch is None


def test_main_launch_passes_platform(monkeypatch):
    calls = []

    class FakeController:
        def launch_game(self, game_name, platform_name=None):
            calls.append((game_name, platform_name))

    monkeypatch.setattr(launcher69, "GameLauncherController", FakeController)
    launcher69.main(["--launch", "Hollow", "--platform", "gog"])
    assert calls == [("Hollow", "gog")]


def test_main_launch_unknown_game_exits_cleanly(store):
    with pytest.raises(SystemExit) as exc:
        launcher69.main(["--launch", "no-existe"])
    assert exc.value.code == 1
