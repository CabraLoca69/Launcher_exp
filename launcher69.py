import sys

from interface_files.tk_interface import TkLauncherUI
from interface_files.qt_interface import QtLauncherUI
from interface_files.ui_handler import init_event_bus

from data_access.cloudsync import call_merge
from data_access.datafiles import db, THEMES_DIR

from helpers.helpers import GameLauncherController

def main():
    launcher_controler = GameLauncherController()
    if "--launch" in sys.argv:
        game_name = sys.argv[sys.argv.index("--launch") + 1]
        launcher_controler.launch_game(game_name)
               
    elif "--qt" in sys.argv:
        start_qt_ui()
    
    else:
        start_tk_ui()

def start_tk_ui():
    init("Tk")
    TkLauncherUI().set()

def start_qt_ui():
    init("Qt")
    QtLauncherUI.launch_ui()

def init(interface: str):
    init_event_bus(interface)
    
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

