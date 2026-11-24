from helpers.data_manager import DataManager


def test_toggle_favorite_adds_then_removes(clean_db):
    dm = DataManager()
    ok, _ = dm.toggle_favorite("steam", "a")
    assert ok and clean_db.get("steam.favorites") == ["a"]

    ok, _ = dm.toggle_favorite("steam", "a")
    assert ok and clean_db.get("steam.favorites") == []


def test_toggle_favorite_respects_limit(clean_db):
    clean_db.set("steam.favorites", ["a", "b"])
    ok, _ = DataManager().toggle_favorite("steam", "c", limit=2)
    assert ok is False
    assert clean_db.get("steam.favorites") == ["a", "b"]
