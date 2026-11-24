import os

import pytest

from platform_adapters.executables_handler import (
    UnixExecutableDetector,
    WindowsExecutableDetector,
)


def test_windows_detects_by_extension():
    d = WindowsExecutableDetector()
    assert d.is_executable("C:/g/Game.EXE")
    assert d.is_executable("run.bat")
    assert not d.is_executable("readme.txt")


def test_unix_detects_by_exec_bit(tmp_path):
    f = tmp_path / "bin"
    f.write_text("")
    d = UnixExecutableDetector()
    assert not d.is_executable(str(f))
    os.chmod(f, 0o755)
    assert d.is_executable(str(f))
    assert not d.is_executable(str(tmp_path))  # un directorio no cuenta


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("C:/g/Hollow.exe", "Hollow"),
        ("C:/g/Game.v2.exe", "Game_v2"),
        ("run.BAT", "run"),
    ],
)
def test_windows_game_name(path, expected):
    assert WindowsExecutableDetector().game_name(path) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/g/Hollow.exe", "Hollow"),  # Wine
        ("/g/game.x86_64", "game"),
        ("/g/Game.AppImage", "Game"),
        ("/g/start.sh", "start"),
        ("/g/game", "game"),
        ("/g/Game.v2", "Game_v2"),  # sufijo desconocido: es parte del nombre
        ("/g/Game.v2.x86_64", "Game_v2"),
    ],
)
def test_unix_game_name(path, expected):
    assert UnixExecutableDetector().game_name(path) == expected
