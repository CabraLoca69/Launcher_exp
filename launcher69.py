import sys
from cloudsync import call_merge
from interfaces import LauncherUI, update_ui
from datafiles import db, THEMES_DIR
from helpers import GameLauncherController
from qt_interface import NewLauncherUI

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
        #start_old_ui()
        start_new_ui()

def start_old_ui():
    launcherui = LauncherUI() 
    launcherui.set()

def start_new_ui():
    NewLauncherUI.launch_ui()

if __name__ == "__main__":
    main()


#### A implementar
"""
Nueva interfaz Qt6

funcion para quitar acc directos y menu de inicio?
"""
######## Reparar
""" 
hacer bien lo de agregar steam_id (se ve horrible)
para esto se va a implementar una ventana nueva con opciones sobre los juegos 
"""
