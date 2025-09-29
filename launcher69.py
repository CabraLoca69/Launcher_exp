
import sys
import datafiles
from interfaces import LauncherUI
from helpers import GameLauncherController, clean_orphaned_sessions

def main():
    if "--launch" in sys.argv and "--platform" in sys.argv:
        game_name = sys.argv[sys.argv.index("--launch") + 1]
        platform_name = sys.argv[sys.argv.index("--platform") + 1]
        game_path = datafiles.config.get(platform_name, {}).get("game_list", {}).get(game_name)
        launcher_controler = GameLauncherController()
        if game_path:
            launcher_controler.launch_game(platform_name, game_name, game_path)
        else:
            print("No se encontró el juego.")
            
    else:
        clean_orphaned_sessions()  
        launcherui = LauncherUI() 
        launcher_controler = GameLauncherController() 
        launcherui.set()
        

if __name__ == "__main__":
    main()

# si abro un juego seguido del otro no cuenta las horas (Probarlo)
# actualizar las ultimas sesiones con el launcher abierto
# intentar coordinar con una nube? que pasa si juego desde otra pc??
# revisar cerrar el launcher con las notas abiertas no se guarda