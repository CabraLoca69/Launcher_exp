import sys

import pytest

from platform_adapters.shortcuts_handler import LinuxShortcutCreator, launch_args


def test_launch_args_include_game_and_platform():
    assert launch_args("steam", "Hollow Knight") == (
        '--launch "Hollow Knight" --platform "steam"'
    )


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="accesos .desktop")
def test_linux_desktop_shortcut_launches_with_platform(home):
    LinuxShortcutCreator().create_direct_access("gog", "Hollow", "/g/Hollow.exe")
    content = (home / "Desktop" / "Hollow.desktop").read_text()
    assert f'Exec="{sys.executable}" --launch "Hollow" --platform "gog"' in content


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="accesos .desktop")
def test_linux_start_menu_shortcut_launches_with_platform(home):
    LinuxShortcutCreator().create_start_menu_shortcut("gog", "Hollow", "/g/Hollow.exe")
    content = (home / ".local/share/applications/hollow.desktop").read_text()
    assert f'Exec="{sys.executable}" --launch "Hollow" --platform "gog"' in content
