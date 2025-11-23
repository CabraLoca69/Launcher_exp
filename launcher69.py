import sys
from cloudsync import call_merge
from interfaces import LauncherUI
from datafiles import db
from helpers import GameLauncherController

def main():
    if "--launch" in sys.argv:
        game_name = sys.argv[sys.argv.index("--launch") + 1]
        launcher_controler = GameLauncherController()
        launcher_controler.launch_game(game_name)
            
    else:
        if db.get("global.cloud_sync_enabled"):
            call_merge()

        launcher_controler = GameLauncherController()
        launcherui = LauncherUI() 
        launcherui.set()

if __name__ == "__main__":
    main()
