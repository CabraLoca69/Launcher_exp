import os
from pathlib import Path

# Sufijos que en Linux sí son "extensión" y se quitan del nombre del juego.
# Cualquier otro sufijo (ej. `Game.v2`) es parte del nombre.
_UNIX_EXECUTABLE_SUFFIXES = {
    # Wine
    ".exe",
    ".bat",
    ".cmd",
    # nativos
    ".sh",
    ".x86_64",
    ".x86",
    ".appimage",
    ".run",
    ".bin",
}


class ExecutableDetector:
    def is_executable(self, path: str) -> bool:
        raise NotImplementedError

    def game_name(self, path: str) -> str:
        """Nombre del juego para un ejecutable: el archivo sin su extensión."""
        raise NotImplementedError


class WindowsExecutableDetector(ExecutableDetector):
    def is_executable(self, path):
        return os.path.splitext(path)[1].lower() in [".exe", ".bat", ".cmd"]

    def game_name(self, path: str) -> str:
        return Path(path).stem


class UnixExecutableDetector(ExecutableDetector):
    def is_executable(self, path):
        return os.path.isfile(path) and os.access(path, os.X_OK)

    def game_name(self, path: str) -> str:
        p = Path(path)
        return p.stem if p.suffix.lower() in _UNIX_EXECUTABLE_SUFFIXES else p.name
