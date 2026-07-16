import sys

from cloudsync import call_merge
from interfaces import LauncherUI, update_ui
from datafiles import db, THEMES_DIR
from helpers import GameLauncherController
from qt_interface import NewLauncherUI
from interface_files.event_bus_factory import init_event_bus

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

        start_tk_ui()
        
        #start_qt_ui()

def start_tk_ui():
    init("Tk")
    launcherui = LauncherUI().set()

def start_qt_ui():
    init("Qt")
    NewLauncherUI.launch_ui()

def init(interface: str):
    init_event_bus(interface)
    launcher_controler = GameLauncherController()

if __name__ == "__main__":
    main()


#### A implementar
"""
Nueva interfaz Qt6

funcion para quitar acc directos y menu de inicio?

guardar iconos de acc directo en .local/share/applications/icons
"""
######## Reparar
""" 
self.parent.favorites_panel.refresh() revisar esto dentro de gamedetailspanel, intentar con signal
hacer bien lo de agregar steam_id (se ve horrible)
para esto se va a implementar una ventana nueva con opciones sobre los juegos 
"""
