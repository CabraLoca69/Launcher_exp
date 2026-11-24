from helpers.data_manager import DataManager


def test_toggle_favorite_adds_then_removes(store):
    store.add_game("steam", "a", "/a")
    dm = DataManager()
    ok, _ = dm.toggle_favorite("steam", "a")
    assert ok and store.get_game("steam", "a").favorite

    ok, _ = dm.toggle_favorite("steam", "a")
    assert ok and not store.get_game("steam", "a").favorite


def test_toggle_favorite_respects_limit(store):
    for name in "abc":
        store.add_game("steam", name, f"/{name}")
    store.set_favorite("steam", "a", True)
    store.set_favorite("steam", "b", True)
    ok, _ = DataManager().toggle_favorite("steam", "c", limit=2)
    assert ok is False
    assert [g.name for g in store.list_favorites("steam")] == ["a", "b"]


def test_toggle_favorite_unknown_game(store):
    ok, _ = DataManager().toggle_favorite("steam", "nope")
    assert ok is False
