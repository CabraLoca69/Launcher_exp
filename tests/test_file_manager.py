import os
import sys

import pytest

from data_access.datafiles import ICONS_CACHE_DIR
from helpers.file_manager import FileManager
from helpers.icon_utils import icon_cache_name


@pytest.fixture
def fm():
    return FileManager()


def test_add_game_uses_detector_name(fm, store):
    ok, name = fm.add_game("steam", "/games/Hollow.exe")
    assert (ok, name) == (True, "Hollow")
    assert store.get_game("steam", "Hollow").path == "/games/Hollow.exe"


def test_add_game_rejects_duplicate(fm):
    fm.add_game("steam", "/a/Hollow.exe")
    ok, _ = fm.add_game("steam", "/b/Hollow.exe")
    assert ok is False


def test_delete_game_hides_it_keeps_playtime_and_removes_icon(fm, store):
    fm.add_game("steam", "/g/a.exe")
    game = store.get_game("steam", "a")
    sid = store.start_session(game.id, "pc", pid=None)
    store.end_session(sid, 60)
    icon = ICONS_CACHE_DIR / f"{icon_cache_name('/g/a.exe')}.png"
    icon.write_bytes(b"x")

    fm.delete_game("steam", "a")

    assert store.list_games("steam") == []
    assert store.total_seconds("steam", "a") == 60
    assert not icon.exists()


def test_delete_folder_hides_only_its_games(fm, store):
    store.add_folder("steam", "/lib1")
    store.add_folder("steam", "/lib2")
    store.add_game("steam", "a", "/lib1/a.exe")
    store.add_game("steam", "b", "/lib2/b.exe")

    assert fm.delete_folder("steam", "/lib1") == ["a"]
    assert [g.name for g in store.list_games("steam")] == ["b"]
    assert store.list_folders("steam") == ["/lib2"]


def test_delete_folder_does_not_touch_sibling_with_same_prefix(fm, store):
    store.add_game("steam", "a", "/juegos/PC/a.exe")
    store.add_game("steam", "b", "/juegos/PC2/b.exe")
    assert fm.delete_folder("steam", "/juegos/PC") == ["a"]
    assert [g.name for g in store.list_games("steam")] == ["b"]


def test_delete_platform_hides_tab_and_games(fm, store):
    fm.add_platform("steam", "/no/existe")
    store.add_game("steam", "a", "/a")
    fm.delete_platform("steam")
    assert store.list_platforms() == []
    assert store.list_games("steam") == []


def test_rename_platform(fm, store):
    store.add_platform("old")
    store.add_game("old", "a", "/a")
    assert fm.rename_platform("old", "new") is True
    assert store.list_platforms() == ["new"]
    assert store.get_game("new", "a") is not None


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="detección por bit de ejecución"
)
def test_add_platform_scans_and_revives_hidden_games(fm, store, tmp_path):
    files = [
        ("game", True),
        ("Game.v2.x86_64", True),
        ("tool.v3", True),
        ("setup_x", True),
        ("notes.txt", False),
    ]
    for name, executable in files:
        f = tmp_path / "sub" / name
        f.parent.mkdir(exist_ok=True)
        f.write_text("")
        if executable:
            os.chmod(f, 0o755)
    store.add_game("lin", "game", "/vieja/ruta")
    store.hide_game("lin", "game")

    fm.add_platform("lin", str(tmp_path))

    assert store.list_platforms() == ["lin"]
    assert {g.name: g.path for g in store.list_games("lin")} == {
        "game": str(tmp_path / "sub" / "game"),
        "Game.v2": str(tmp_path / "sub" / "Game.v2.x86_64"),
        "tool.v3": str(tmp_path / "sub" / "tool.v3"),
    }


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="detección por bit de ejecución"
)
def test_reload_does_not_bring_back_deleted_games(fm, store, tmp_path):
    """Borrar un juego y apretar Recargar (o agregar otra carpeta) no lo revive."""
    for name in ("a", "b"):
        exe = tmp_path / "lib" / name
        exe.parent.mkdir(exist_ok=True)
        exe.write_text("")
        os.chmod(exe, 0o755)
    (tmp_path / "otra").mkdir()
    fm.add_platform("lin", str(tmp_path / "lib"))
    fm.delete_game("lin", "a")

    fm.scan_for_games("lin")
    fm.add_folder("lin", str(tmp_path / "otra"))

    assert [g.name for g in store.list_games("lin")] == ["b"]
