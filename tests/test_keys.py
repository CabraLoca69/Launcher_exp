from data_access.keys import is_valid_platform_name, key_segment


def test_key_segment_replaces_dots():
    assert key_segment("Game.v2") == "Game_v2"
    assert key_segment("plain") == "plain"


def test_is_valid_platform_name():
    assert is_valid_platform_name("Steam Deck")
    assert not is_valid_platform_name("Steam.Deck")
    assert not is_valid_platform_name("   ")
