import sys
from helpers.games_launcher import GameLauncherController

def main():
    launcher_controler = GameLauncherController()
    if "--launch" in sys.argv:
        game_name = sys.argv[sys.argv.index("--launch") + 1]
        launcher_controler.launch_game(game_name)
               
    elif "--tk" in sys.argv:
        start_tk_ui()
    
    else:
        start_qt_ui()

def start_tk_ui():
    from interface_files.tk_interface import TkLauncherUI
    init("Tk")
    TkLauncherUI().set()

def start_qt_ui():
    from interface_files.qt_interface import QtLauncherUI
    init("Qt")
    QtLauncherUI.launch_ui()

def init(interface: str):
    from interface_files.ui_handler import init_event_bus
    init_event_bus(interface)
    
if __name__ == "__main__":
    main()