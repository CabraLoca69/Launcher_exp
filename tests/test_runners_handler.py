from types import SimpleNamespace

import pytest

from platform_adapters.runners_handler import LinuxWineRunner


def proc(name, cmdline):
    return SimpleNamespace(name=lambda: name, cmdline=lambda: cmdline)


@pytest.mark.parametrize(
    ("p", "expected"),
    [
        (proc("game.exe", ["C:/users/x/.wine/drive_c/Games/Game.exe"]), True),
        (proc("game.exe", ["/home/x/prefix/drive_c/Game.exe"]), True),
        (proc("wineserver", ["/home/x/.wine/drive_c/Game.exe"]), False),
        (proc("game.exe", ["/usr/bin/Game.exe"]), False),
        (proc("other.exe", ["/home/x/.wine/drive_c/Other.exe"]), False),
        (proc("game.exe", []), False),
    ],
)
def test_cmdline_matches(p, expected):
    assert LinuxWineRunner("/tmp/prefix")._cmdline_matches(p, "game.exe") is expected
