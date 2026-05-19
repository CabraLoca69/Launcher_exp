import sys
from switcher import WindowsMenuCreator, LinuxMenuCreator, WindowsShortcutCreator, LinuxShortcutCreator, WindowsRunner, LinuxSelector

if sys.platform.startswith("win"):
    CURRENT_OS = "windows"
elif sys.platform.startswith("linux"):
    CURRENT_OS = "linux"

else:
    raise RuntimeError("Sistema no soportado")

PLATFORM_METHODS = {
    "windows": {
        "runner": WindowsRunner,
        "menu": WindowsMenuCreator,
        "shortcut": WindowsShortcutCreator,
        "exedetect" : WindowsExecutableDetector,
    },
    "linux": {
    "runner": LinuxSelector,
    "menu": LinuxMenuCreator,
    "shortcut" : LinuxShortcutCreator,
    "exedetect" : UnixExecutableDetector,
    }
}


