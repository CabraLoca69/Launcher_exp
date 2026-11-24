import os
import sys

import pytest

from data_access.datafiles import ICONS_CACHE_DIR
from helpers.file_manager import FileManager


@pytest.fixture
def fm():
    return FileManager()


def test_add_game_stores_path_by_stem(fm, clean_db):
    ok, name = fm.add_game("steam", "/games/Hollow.exe")
    assert (ok, name) == (True, "Hollow")
    assert clean_db.get("steam.game_list.Hollow") == "/games/Hollow.exe"


def test_add_game_with_dots_in_name_is_listed(fm, clean_db):
    ok, name = fm.add_game("steam", "/g/Game.v2.exe")
    assert (ok, name) == (True, "Game_v2")
    assert clean_db.get_children("steam.game_list") == {"Game_v2": "/g/Game.v2.exe"}


def test_add_game_rejects_duplicate(fm):
    fm.add_game("steam", "/a/Hollow.exe")
    ok, _ = fm.add_game("steam", "/b/Hollow.exe")
    assert ok is False


def test_delete_game_removes_everything(fm, clean_db):
    clean_db.set("steam.game_list.a", "/g/a.exe")
    clean_db.set("steam.game_times.a", [{"Start": "x", "Tiempo": 1}])
    clean_db.set("steam.game_total_times.a", {"pc": 1.0})
    clean_db.set("steam.favorites", ["a", "b"])
    icon = ICONS_CACHE_DIR / "a.png"
    icon.write_bytes(b"x")

    fm.delete_game("steam", "a")

    assert clean_db.get("steam.game_list.a") is None
    assert clean_db.get("steam.game_times.a") is None
    assert clean_db.get("steam.game_total_times.a") is None
    assert clean_db.get("steam.favorites") == ["b"]
    assert not icon.exists()


def test_delete_folder_removes_only_its_games(fm, clean_db):
    clean_db.set("steam.platform_folders", ["/lib1", "/lib2"])
    clean_db.set("steam.game_list.a", "/lib1/a.exe")
    clean_db.set("steam.game_list.b", "/lib2/b.exe")

    removed = fm.delete_folder("steam", "/lib1")

    assert removed == ["a"]
    assert clean_db.get_children("steam.game_list") == {"b": "/lib2/b.exe"}
    assert clean_db.get("steam.platform_folders") == ["/lib2"]


def test_sort_key_recent_first_then_unplayed_alphabetical(fm):
    times = {
        "old": [{"Start": "2025-01-01 10:00:00"}],
        "new": [{"Start": "2026-01-01 10:00:00"}],
    }
    names = ["zeta", "old", "Alpha", "new"]
    assert sorted(names, key=lambda n: fm.sort_key(n, times)) == [
        "new",
        "old",
        "Alpha",
        "zeta",
    ]


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="detección por bit de ejecución"
)
def test_scan_for_games_finds_executables_and_skips_ignored(fm, clean_db, tmp_path):
    for name, executable in [
        ("game", True),
        ("Game.v2.x86_64", True),
        ("setup_x", True),
        ("notes.txt", False),
    ]:
        f = tmp_path / "sub" / name
        f.parent.mkdir(exist_ok=True)
        f.write_text("")
        if executable:
            os.chmod(f, 0o755)
    clean_db.set("lin.platform_folders", [str(tmp_path)])

    fm.scan_for_games("lin")

    assert clean_db.get_children("lin.game_list") == {
        "game": str(tmp_path / "sub" / "game"),
        "Game_v2": str(tmp_path / "sub" / "Game.v2.x86_64"),
    }


def test_rename_platform(fm, clean_db):
    clean_db.set("global.tab_order", ["old"])
    clean_db.set("old.game_list.a", "/a")
    assert fm.rename_platform("old", "new") is True
    assert clean_db.get("global.tab_order") == ["new"]
