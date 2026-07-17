import subprocess
import os
import psutil
import time

from data_access.datafiles import db

INVALID_NAMES = {
    "reaper", "wineserver", "steam", "steamwebhelper",
    "services.exe", "explorer.exe"
}

class GameRunner:
    def run(self, game_path):
        raise NotImplementedError

class WindowsRunner(GameRunner):
    def run(self, game_path):
        return subprocess.Popen(game_path)

class LinuxNativeRunner(GameRunner):
    def run(self, game_path):
        return subprocess.Popen([game_path])

class LinuxWineRunner(GameRunner):
    def __init__(self, wineprefix=None):
        self.wineprefix = wineprefix or os.path.expanduser("~/.wine")

    def run(self, game_path):
        game_name = os.path.splitext(os.path.basename(game_path))[0] #este le quita el .exe
        steam_appid = db.get(f"global.steam_ids.{game_name}")
        game_exe = os.path.basename(game_path) #este devuelve con el .exe

        if steam_appid:
            process= subprocess.Popen(["steam", f"steam://rungameid/{steam_appid}"])

        else :
            env = os.environ.copy()
            env["WINEPREFIX"] = self.wineprefix
        
            process= subprocess.Popen(["wine", game_path], env=env)

        real_proc = self.find_real_wine_process(process.pid, game_exe)

        return real_proc or process

    #al ejecutar desde steam o wine primero se llama a un proceso que va a crear el proceso real del juego... 
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
                except:
                    pass

            # 2. Buscar globalmente en cmdline (necesario para Steam/Proton)
            for proc in psutil.process_iter(['cmdline']):
                try:
                    if self._cmdline_matches(proc, expected_exe):
                        print(f"proceso retornado: {proc}")
                        return proc

                except Exception as e:
                    print(f"se rompio : {e}")
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
            
            if ".wine" not in cmd[0].lower() and "drive_c" not in cmd[0].lower():
                return False

            return True

        except Exception as e:
            print (f"exepcion buscando matches en cmd : {e}")
            return False

class LinuxSelector(GameRunner):
    def run(self, game_path):
        ext = os.path.splitext(game_path)[1].lower()
        needs_wine = ext in [".exe", ".bat", ".cmd"]

        if needs_wine:
            wineprefix = db.get("global.wineprefix", os.path.expanduser("~/.wine"))
            return LinuxWineRunner(wineprefix).run(game_path)

        return LinuxNativeRunner().run(game_path)