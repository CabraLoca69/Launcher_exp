import logging
import os
import subprocess
import time

import psutil

# --------- imports internos -------
from data_access.datafiles import store

logger = logging.getLogger(__name__)

INVALID_NAMES = {
    "reaper",
    "wineserver",
    "steam",
    "steamwebhelper",
    "services.exe",
    "explorer.exe",
}


def _game_dir(game_path: str) -> str | None:
    """Carpeta del juego: muchos juegos buscan sus archivos relativos a ella."""
    return os.path.dirname(game_path) or None


class GameRunner:
    def run(self, game_path: str, steam_appid: str | None = None):
        raise NotImplementedError


class WindowsRunner(GameRunner):
    def run(self, game_path, steam_appid=None):
        return subprocess.Popen(game_path, cwd=_game_dir(game_path))


class LinuxNativeRunner(GameRunner):
    def run(self, game_path, steam_appid=None):
        return subprocess.Popen([game_path], cwd=_game_dir(game_path))


class LinuxWineRunner(GameRunner):
    def __init__(self, wineprefix=None):
        self.wineprefix = wineprefix or os.path.expanduser("~/.wine")

    def run(self, game_path, steam_appid=None):
        game_exe = os.path.basename(game_path)  # este devuelve con el .exe

        if steam_appid:
            process = subprocess.Popen(["steam", f"steam://rungameid/{steam_appid}"])

        else:
            env = os.environ.copy()
            env["WINEPREFIX"] = self.wineprefix

            process = subprocess.Popen(
                ["wine", game_path], env=env, cwd=_game_dir(game_path)
            )

        real_proc = self.find_real_wine_process(process.pid, game_exe)

        return real_proc or process

    # al ejecutar desde steam o wine primero se llama a un proceso que va a crear el proceso real del juego...
    def find_real_wine_process(self, parent_pid, expected_exe):
        expected_exe = expected_exe.lower()

        for _ in range(200):  # hasta 20 segundos
            # 1. Buscar como proceso hijo (solo funciona en Wine directo)
            if psutil.pid_exists(parent_pid):
                try:
                    parent = psutil.Process(parent_pid)
                    for proc in parent.children(recursive=True):
                        if self._cmdline_matches(proc, expected_exe):
                            return proc
                except psutil.Error:
                    pass

            # 2. Buscar globalmente en cmdline (necesario para Steam/Proton)
            for proc in psutil.process_iter(["cmdline"]):
                try:
                    if self._cmdline_matches(proc, expected_exe):
                        logger.info("Proceso del juego encontrado: %s", proc)
                        return proc

                except psutil.Error:
                    continue

            time.sleep(0.1)

        return None

    def _cmdline_matches(self, proc, expected_exe):
        try:
            name = proc.name().lower()
            if name in INVALID_NAMES:
                return False

            cmd = proc.cmdline()
            if not cmd:
                return False

            last_base = os.path.basename(cmd[0]).lower()

            if expected_exe not in last_base:
                return False

            exe_path = cmd[0].lower()
            return ".wine" in exe_path or "drive_c" in exe_path

        except psutil.Error:
            return False


class LinuxSelector(GameRunner):
    def run(self, game_path, steam_appid=None):
        ext = os.path.splitext(game_path)[1].lower()
        needs_wine = ext in [".exe", ".bat", ".cmd"]

        if needs_wine:
            wineprefix = store.get_setting("wineprefix", os.path.expanduser("~/.wine"))
            return LinuxWineRunner(wineprefix).run(game_path, steam_appid)

        return LinuxNativeRunner().run(game_path)
