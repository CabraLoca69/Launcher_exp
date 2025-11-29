import sys
from cloudsync import call_merge
from interfaces import LauncherUI, update_ui
from datafiles import db
from helpers import GameLauncherController

def main():
    if "--launch" in sys.argv:
        game_name = sys.argv[sys.argv.index("--launch") + 1]
        launcher_controler = GameLauncherController()
        launcher_controler.launch_game(game_name)
            
    else:
        if db.get("global.cloud_sync_enabled"):
            def call_update(data):
                update_ui(launcherui)
            
            call_merge(callback= call_update)

        launcher_controler = GameLauncherController()
        launcherui = LauncherUI() 
        launcherui.set()

if __name__ == "__main__":
    main()