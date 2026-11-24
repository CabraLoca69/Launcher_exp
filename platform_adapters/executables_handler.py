import os
from pathlib import Path

# --------- imports internos -------
from data_access.keys import key_segment

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
        """Nombre del juego (y segmento de clave de la DB) para un ejecutable."""
        raise NotImplementedError


class WindowsExecutableDetector(ExecutableDetector):
    def is_executable(self, path):
        return os.path.splitext(path)[1].lower() in [".exe", ".bat", ".cmd"]

    def game_name(self, path: str) -> str:
        return key_segment(Path(path).stem)


class UnixExecutableDetector(ExecutableDetector):
    def is_executable(self, path):
        return os.path.isfile(path) and os.access(path, os.X_OK)

    def game_name(self, path: str) -> str:
        p = Path(path)
        name = p.stem if p.suffix.lower() in _UNIX_EXECUTABLE_SUFFIXES else p.name
        return key_segment(name)
