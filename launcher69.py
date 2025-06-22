
import sys
from datafiles import config
from interfaces import LauncherUI
from helpers import GameLauncherController, clean_orphaned_sessions

def main():
    if "--launch" in sys.argv and "--platform" in sys.argv:
        game_name = sys.argv[sys.argv.index("--launch") + 1]
        platform_name = sys.argv[sys.argv.index("--platform") + 1]
        game_path = config.get(platform_name, {}).get("game_list", {}).get(game_name)
        launcher_controler = GameLauncherController()
        if game_path:
            launcher_controler.launch_game(platform_name, game_name, game_path)
        else:
            print("No se encontró el juego.")
            
    else:
        clean_orphaned_sessions()
        launcherui = LauncherUI()
        launcher_controler = GameLauncherController()
        launcherui.start()
        
        #steam = SteamIntegration(config)
        #if steam.is_ready():
        #    games = steam.get_owned_games()
        #    formatted = steam.format_games(games)
        #    steam.format_and_cache_games(games)
        #    for game in formatted[:10]:
        #        print(f"🎮 {game['name']} ({game['appid']}) - {game['time']} hs")
        #        print(f"🖼 Icono: {game['icon']}")
        #else:
        #    print("⚠ No se configuró Steam correctamente.")

if __name__ == "__main__":
    main()

# implementar "pantallas de carga" para que se vea mas lindo
# separar las clases en los diferentes archivos para mas organizacion
# intentar coordinar con una nube? que pasa si juego desde otra pc??
# tratar de integrar ia (para boludear)