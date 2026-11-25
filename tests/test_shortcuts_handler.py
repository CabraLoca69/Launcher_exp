import sys

import pytest

from platform_adapters import shortcuts_handler
from platform_adapters.shortcuts_handler import LinuxShortcutCreator, launch_args

SCRIPT = shortcuts_handler._SCRIPT


def test_launch_args_include_game_and_platform():
    assert launch_args("steam", "Hollow Knight") == (
        f'"{SCRIPT}" --launch "Hollow Knight" --platform "steam"'
    )


def test_frozen_launcher_needs_no_script(monkeypatch):
    """Congelado, el ejecutable es el launcher: no se le pasa `launcher69.py`."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert launch_args("steam", "Hollow") == '--launch "Hollow" --platform "steam"'


def test_script_path_points_to_entry_point():
    assert SCRIPT.is_file()


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="accesos .desktop")
def test_linux_desktop_shortcut_launches_with_platform(home):
    LinuxShortcutCreator().create_direct_access("gog", "Hollow", "/g/Hollow.exe")
    content = (home / "Desktop" / "Hollow.desktop").read_text()
    assert (
        f'Exec="{sys.executable}" "{SCRIPT}" --launch "Hollow" --platform "gog"'
        in content
    )


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="accesos .desktop")
def test_linux_start_menu_shortcut_launches_with_platform(home):
    LinuxShortcutCreator().create_start_menu_shortcut("gog", "Hollow", "/g/Hollow.exe")
    content = (home / ".local/share/applications/hollow.desktop").read_text()
    assert (
        f'Exec="{sys.executable}" "{SCRIPT}" --launch "Hollow" --platform "gog"'
        in content
    )
