import os

from interface_files.event_bus import QtEventBus


class FailingUI:
    def update_on_close(self, game_name, platform_name):
        raise RuntimeError("boom")


class RecordingUI:
    def __init__(self):
        self.calls = []
        self.running = []

    def update_on_close(self, game_name, platform_name):
        self.calls.append((game_name, platform_name))

    def mark_game_running(self, game_name):
        self.running.append(game_name)


def test_game_closed_reaches_registered_ui():
    bus = QtEventBus()
    ui = RecordingUI()
    bus.ui_registry["steam"] = ui
    bus.notify_game_closed("steam", "a")
    assert ui.calls == [("a", "steam")]


def test_ui_error_on_close_is_logged_not_raised():
    bus = QtEventBus()
    bus.ui_registry["steam"] = FailingUI()
    bus._on_game_closed("steam", "a")


def test_register_ui_marks_games_already_running(store):
    for platform, game in [("steam", "a"), ("gog", "b")]:
        store.add_game(platform, game, f"/{game}")
        store.start_session(store.get_game(platform, game).id, "pc", pid=os.getpid())
    ui = RecordingUI()
    QtEventBus().register_ui("steam", ui)
    assert ui.running == ["a"]
