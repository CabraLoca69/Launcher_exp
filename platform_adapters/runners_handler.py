import subprocess
import os
from datafiles import db

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
        game_name = os.path.splitext(os.path.basename(game_path))[0]
        steam_appid = db.get(f"global.steam_ids.{game_name}")

        if steam_appid:
            return subprocess.Popen(["steam", f"steam://rungameid/{steam_appid}"])

        env = os.environ.copy()
        env["WINEPREFIX"] = self.wineprefix
        
        return subprocess.Popen(["wine", game_path], env=env)

class LinuxSelector(GameRunner):
    def run(self, game_path):
        ext = os.path.splitext(game_path)[1].lower()
        needs_wine = ext in [".exe", ".bat", ".cmd"]

        if needs_wine:
            wineprefix = db.get("global.wineprefix", os.path.expanduser("~/.wine"))
            return LinuxWineRunner(wineprefix).run(game_path)

        return LinuxNativeRunner().run(game_path)