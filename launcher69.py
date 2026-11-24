import argparse

from helpers.games_launcher import GameLauncherController


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="launcher69")
    parser.add_argument(
        "--launch", metavar="JUEGO", help="lanza un juego sin abrir la UI"
    )
    parser.add_argument(
        "--platform",
        metavar="PLATAFORMA",
        help="plataforma del juego; sin ella, --launch usa la primera coincidencia",
    )
    parser.add_argument("--tk", action="store_true", help="usa la UI vieja (Tk)")
    args, _ = parser.parse_known_args(argv)  # Qt puede recibir argumentos propios
    if args.platform and not args.launch:
        parser.error("--platform solo tiene sentido junto con --launch")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.launch:
        GameLauncherController().launch_game(args.launch, args.platform)
    elif args.tk:
        start_tk_ui()
    else:
        start_qt_ui()


def start_tk_ui():
    from interface_files.tk_interface import TkLauncherUI

    init("Tk")
    set_launcher_controller()
    TkLauncherUI().set()


def start_qt_ui():
    from interface_files.qt_interface import QtLauncherUI

    init("Qt")
    set_launcher_controller()
    QtLauncherUI.launch_ui()


def set_launcher_controller():
    GameLauncherController()


def init(interface: str):
    from interface_files.ui_handler import init_event_bus

    init_event_bus(interface)


if __name__ == "__main__":
    main()
