import pytest

from data_access.sqlitedb import SQLiteDatabase


@pytest.fixture
def sdb(tmp_path):
    return SQLiteDatabase(tmp_path / "test.db")


def test_get_returns_default_when_missing(sdb):
    assert sdb.get("a.b") is None
    assert sdb.get("a.b", 5) == 5


def test_set_and_get_roundtrip_json_values(sdb):
    sdb.set("a.list", [1, 2, {"x": "ñ"}])
    assert sdb.get("a.list") == [1, 2, {"x": "ñ"}]


def test_set_overwrites(sdb):
    sdb.set("k", 1)
    sdb.set("k", 2)
    assert sdb.get("k") == 2


def test_keypath_as_list(sdb):
    sdb.set(["a", "b", "c"], "v")
    assert sdb.get("a.b.c") == "v"


def test_delete_reports_if_existed(sdb):
    sdb.set("k", 1)
    assert sdb.delete("k") is True
    assert sdb.delete("k") is False
    assert sdb.get("k") is None


def test_ensure_only_sets_when_missing(sdb):
    assert sdb.ensure("k", "default") == "default"
    sdb.set("k", "real")
    assert sdb.ensure("k", "default") == "real"


def test_update_applies_function(sdb):
    sdb.set("n", 1)
    assert sdb.update("n", lambda v: v + 1) == 2
    assert sdb.get("n") == 2


def test_get_children_returns_only_direct_children(sdb):
    sdb.set("p.game_list.a", "/a")
    sdb.set("p.game_list.b", "/b")
    sdb.set("p.game_list.b.nested", "x")
    sdb.set("p.other", 1)
    assert sdb.get_children("p.game_list") == {"a": "/a", "b": "/b"}


def test_delete_prefix_leaves_other_keys(sdb):
    sdb.set("global.running.a", 1)
    sdb.set("global.running.b", 2)
    sdb.set("global.other", 3)
    sdb.delete_prefix("global.running")
    assert sdb.get_children("global.running") == {}
    assert sdb.get("global.other") == 3


def test_rename_prefix_moves_all_keys(sdb):
    sdb.set("old.game_list.a", "/a")
    sdb.set("old.favorites", ["a"])
    sdb.rename_prefix("old", "new")
    assert sdb.get("new.game_list.a") == "/a"
    assert sdb.get("new.favorites") == ["a"]
    assert sdb.get_all() == {"new.game_list.a": "/a", "new.favorites": ["a"]}


def test_resolve_game_returns_platform_and_path(sdb):
    sdb.set("steam.game_list.hollow", "/games/hollow.exe")
    assert sdb.resolve_game("hollow") == ("steam", "/games/hollow.exe")


def test_resolve_game_unknown_raises(sdb):
    with pytest.raises(ValueError):
        sdb.resolve_game("nope")


def test_resolve_game_underscore_is_literal(sdb):
    sdb.set("p.game_list.myXgame", "/wrong")
    with pytest.raises(ValueError):
        sdb.resolve_game("my_game")


def test_resolve_game_matches_wildcard_chars_literally(sdb):
    sdb.set("p.game_list.my_game", "/ok")
    sdb.set("p.game_list.100%", "/pct")
    assert sdb.resolve_game("my_game") == ("p", "/ok")
    assert sdb.resolve_game("100%") == ("p", "/pct")
