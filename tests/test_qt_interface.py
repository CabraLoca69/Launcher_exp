import os

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from helpers.games_launcher import GameLauncherController
from interface_files import qt_interface
from interface_files.ui_handler import init_event_bus


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bus(app, monkeypatch):
    bus = init_event_bus("Qt")
    monkeypatch.setattr(GameLauncherController(), "event_bus", bus)
    return bus


@pytest.fixture
def no_icons(monkeypatch):
    """Sin extraer íconos reales (no existen los ejecutables de prueba)."""
    from helpers import data_manager

    class Icons:
        def get_icon(self, path):
            return None

    monkeypatch.setattr(
        data_manager,
        "PlatformHandler",
        lambda: type("H", (), {"get": lambda s, k: Icons()})(),
    )


def _tab(store, platform="steam", games=("a", "b", "c")):
    store.add_platform(platform)
    for g in games:
        store.add_game(platform, g, f"/{g}")
    tab = qt_interface.PlatformTab(platform)
    tab.fill_games(
        qt_interface.DataManager().collect_platform_data(platform)["grouped"]
    )
    return tab


def _names(tab):
    t = tab.games_tree
    return [t.topLevelItem(i).text(0) for i in range(t.topLevelItemCount())]


def _play(store, platform, game, seconds):
    sid = store.start_session(store.get_game(platform, game).id, "pc", pid=None)
    store.end_session(sid, seconds)


def test_enter_launches_selected_game(store, bus, no_icons, monkeypatch):
    tab = _tab(store)
    launched = []
    monkeypatch.setattr(tab, "launch_game", launched.append)
    tab._launch_selected()  # sin selección: nada
    tab.games_tree.setCurrentItem(tab._find_item_by_name("b"))
    tab._launch_selected()
    assert launched == ["b"]


def test_delete_key_asks_before_removing(store, bus, no_icons, monkeypatch):
    tab = _tab(store)
    asked = []
    monkeypatch.setattr(tab, "confirm_remove", lambda: asked.append(True))
    tab._confirm_remove_selected()  # sin selección: no pregunta
    tab.games_tree.setCurrentItem(tab._find_item_by_name("a"))
    tab._confirm_remove_selected()
    assert asked == [True]
    assert store.get_game("steam", "a").hidden is False


def test_closing_a_game_moves_it_to_the_top_and_refreshes_favorites(
    store, bus, no_icons
):
    tab = _tab(store)
    store.set_favorite("steam", "c", True)
    _play(store, "steam", "c", 3600)

    tab.update_on_close("c", "steam")

    assert _names(tab)[0] == "c"
    assert tab.detail_panel.current_game == "c"
    assert "1.0 hs" in tab.detail_panel.name_label.text()
    assert (
        "1.0 hs"
        in tab.favorites_panel._container.findChildren(
            qt_interface.QLabel, "favoriteGameHours"
        )[0].text()
    )


def test_detail_panel_refreshes_while_game_runs(store, bus, no_icons):
    tab = _tab(store)
    tab.detail_panel.show_game("a")
    sid = store.start_session(store.get_game("steam", "a").id, "pc", pid=os.getpid())
    store.update_session(sid, 7200)
    tab.detail_panel._refresh_if_running()
    assert "2.0 hs" in tab.detail_panel.name_label.text()


def test_settings_window_toggles_multiple_games(store, bus):
    win = qt_interface.SettingsWindow(None)
    assert win.chk_multiple.isChecked() is True  # por defecto, permitido
    win.chk_multiple.setChecked(False)
    assert store.get_setting("allow_multiple_games") is False


def test_properties_dialog_renames_and_manages_folders(
    store, bus, no_icons, monkeypatch
):
    store.add_platform("steam")
    store.add_folder("steam", "/lib1")
    store.add_folder("steam", "/lib2")
    store.add_game("steam", "a", "/lib1/a")
    dlg = qt_interface.PlatformPropertiesDialog(None, "steam")
    assert [dlg.folder_list.item(i).text() for i in range(dlg.folder_list.count())] == [
        "/lib1",
        "/lib2",
    ]

    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    dlg.folder_list.setCurrentRow(0)
    dlg._remove_folder()
    assert store.list_folders("steam") == ["/lib2"]
    assert store.list_games("steam") == []

    dlg.name_edit.setText("Steam Deck")
    dlg._rename()
    assert (dlg.changed, dlg.platform_name, store.list_platforms()) == (
        True,
        "Steam Deck",
        ["Steam Deck"],
    )


def test_main_window_restores_and_remembers_last_tab(store, bus, no_icons):
    win = qt_interface.MainWindow()  # DB vacía: no lanza la recarga en otro hilo
    for name in ("steam", "gog", "epic"):
        store.add_platform(name)
    store.set_setting("last_selected_tab", "gog")
    data = [
        qt_interface.DataManager().collect_platform_data(n)
        for n in store.list_platforms()
    ]

    win._on_reload_finished(data)
    assert win.tab_widget.tabText(win.tab_widget.currentIndex()) == "gog"

    win.tab_widget.setCurrentIndex(2)
    assert store.get_setting("last_selected_tab") == "epic"


def test_main_window_detects_games_launched_from_shortcuts(store, bus, no_icons):
    win = qt_interface.MainWindow()
    store.add_platform("steam")
    store.add_game("steam", "a", "/a")
    win._on_reload_finished([qt_interface.DataManager().collect_platform_data("steam")])

    store.start_session(store.get_game("steam", "a").id, "pc", pid=os.getpid())
    bus.watch_external()
    QApplication.processEvents()
    assert "a" in win.sessions_bar.sessions

    bus.watch_external()  # no duplica watchers
    assert len(bus._watchers) == 1


def test_notes_are_saved_on_close(store, bus, no_icons, monkeypatch):
    tab = _tab(store)
    tab.detail_panel.show_game("a")

    def fake_exec(dlg):
        dlg.editor.setPlainText("pasar el jefe")
        return 0  # cerrado con la X

    monkeypatch.setattr(qt_interface.NotesDialog, "exec", fake_exec)
    tab.detail_panel._open_notes()
    assert store.get_game("steam", "a").notes == "pasar el jefe"
