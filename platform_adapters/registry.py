import sys
from .runners_handler import WindowsRunner, LinuxSelector
from .executables_handler import WindowsExecutableDetector, UnixExecutableDetector
from .shortcuts_handler import WindowsShortcutCreator, LinuxShortcutCreator
from .paths_handler import WindowsGoToFolder, LinuxGoToFolder
from .icons_handler import WindowsIconProvider, LinuxIconProvider
from .menus_handler import WindowsMenuOptions, LinuxMenuOptions

if sys.platform.startswith("win"):
    CURRENT_OS = "windows"
elif sys.platform.startswith("linux"):
    CURRENT_OS = "linux"

else:
    raise RuntimeError("Sistema no soportado")

PLATFORM_METHODS = {
    "windows": {
        "runner": WindowsRunner,
        "menu-options": WindowsMenuOptions,
        "shortcut": WindowsShortcutCreator,
        "exedetect" : WindowsExecutableDetector,
        "paths" : WindowsGoToFolder,
        "icons" : WindowsIconProvider
    },
    "linux": {
    "runner": LinuxSelector,
    "menu-options": LinuxMenuOptions,
    "shortcut" : LinuxShortcutCreator,
    "exedetect" : UnixExecutableDetector,
    "paths" : LinuxGoToFolder,
    "icons" : LinuxIconProvider
    }
}