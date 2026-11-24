from interface_files.event_bus import QtEventBus


class FailingUI:
    def update_on_close(self, game_name, platform_name):
        raise RuntimeError("boom")


class RecordingUI:
    def __init__(self):
        self.calls = []

    def update_on_close(self, game_name, platform_name):
        self.calls.append((game_name, platform_name))


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
