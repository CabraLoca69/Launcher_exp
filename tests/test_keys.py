from data_access.keys import game_name_from_path, is_valid_platform_name, key_segment


def test_key_segment_replaces_dots():
    assert key_segment("Game.v2") == "Game_v2"
    assert key_segment("plain") == "plain"


def test_game_name_from_path_drops_extension_and_dots():
    assert game_name_from_path("/g/Game.v2.exe") == "Game_v2"
    assert game_name_from_path("C:/g/Hollow.exe") == "Hollow"
    assert game_name_from_path("/usr/bin/game") == "game"


def test_is_valid_platform_name():
    assert is_valid_platform_name("Steam Deck")
    assert not is_valid_platform_name("Steam.Deck")
    assert not is_valid_platform_name("   ")
