import sys
from .runners_handler import WindowsRunner, LinuxSelector
from .executables_handler import WindowsExecutableDetector, UnixExecutableDetector
from .shortcuts_handler import WindowsShortcutCreator, LinuxShortcutCreator
from .paths_handler import WindowsGoToFolder, LinuxGoToFolder
from .icons_handler import WindowsIconProvider, LinuxIconProvider
from .menus_handler import WindowsMenuOptions, LinuxMenuOptions


def _detect_os() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("linux"):
        return "linux"
    raise RuntimeError("Sistema no soportado")


CURRENT_OS = _detect_os()

PLATFORM_METHODS = {
    "windows": {
        "runner": WindowsRunner,
        "menu-options": WindowsMenuOptions,
        "shortcut": WindowsShortcutCreator,
        "exedetect": WindowsExecutableDetector,
        "paths": WindowsGoToFolder,
        "icons": WindowsIconProvider,
    },
    "linux": {
        "runner": LinuxSelector,
        "menu-options": LinuxMenuOptions,
        "shortcut": LinuxShortcutCreator,
        "exedetect": UnixExecutableDetector,
        "paths": LinuxGoToFolder,
        "icons": LinuxIconProvider,
    },
}


class PlatformHandler:
    _instances_cache: dict[str, object] = {}

    def get(self, key: str):
        try:
            handlers = PLATFORM_METHODS[CURRENT_OS]
        except KeyError:
            raise RuntimeError(f"Sistema no soportado: {CURRENT_OS}")

        if key not in handlers:
            raise KeyError(
                f"'{key}' no existe para '{CURRENT_OS}'. "
                f"Opciones válidas: {list(handlers.keys())}"
            )

        if key not in self._instances_cache:
            self._instances_cache[key] = handlers[key]()

        return self._instances_cache[key]