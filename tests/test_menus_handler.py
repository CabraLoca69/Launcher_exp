from platform_adapters.menus_handler import LinuxMenuOptions, WindowsMenuOptions


class Frame:
    def __init__(self):
        self.launched = []

    def launch_game(self, game_name):
        self.launched.append(game_name)

    def __getattr__(self, name):  # el resto de las acciones no importan acá
        return lambda *a, **k: None


def _option(options, label):
    return next(cmd for text, _, cmd in options if label in text)


def test_play_option_launches_the_clicked_game():
    for handler in (WindowsMenuOptions(), LinuxMenuOptions()):
        frame = Frame()
        _option(handler.get_options("Hollow", False, frame), "Jugar")()
        assert frame.launched == ["Hollow"]


def test_props_button_menu_has_no_play_option():
    options = WindowsMenuOptions().get_options("Hollow", True, Frame())
    assert not any("Jugar" in text for text, _, _ in options)


def test_empty_area_menu_offers_add_game():
    options = WindowsMenuOptions().get_options(None, False, Frame())
    assert [text for text, _, _ in options] == ["＋ Agregar juego"]
