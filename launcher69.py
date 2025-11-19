
import sys
from cloudsync import call_merge
from interfaces import LauncherUI
from datafiles import db, remove_temp_path
from helpers import GameLauncherController, clean_orphaned_sessions

def main():
    if "--launch" in sys.argv and "--platform" in sys.argv:
        game_name = sys.argv[sys.argv.index("--launch") + 1]
        platform_name = sys.argv[sys.argv.index("--platform") + 1]
        game_path = db.get([platform_name, "game_list", game_name])
        launcher_controler = GameLauncherController()
        if game_path:
            launcher_controler.launch_game(game_name)
        else:
            print("No se encontró el juego.")
            
    else:
        if db.get("global.cloud_sync_enabled"):
            call_merge()

        clean_orphaned_sessions()  
        launcherui = LauncherUI() 
        launcher_controler = GameLauncherController()
        launcherui.set()
        remove_temp_path()

        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Launcher finalizado por interrupción de VS Code.")

# revisar cerrar el launcher con las notas abiertas no se guarda
# revisar buscador