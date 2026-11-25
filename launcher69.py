import argparse
import logging
import sys

from data_access.datafiles import store
from data_access.machine_id import get_machine_id
from data_access.migrate_kv import run_pending_migration
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
    args, _ = parser.parse_known_args(argv)  # Qt puede recibir argumentos propios
    if args.platform and not args.launch:
        parser.error("--platform solo tiene sentido junto con --launch")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run_pending_migration()
    try:
        store.compact_months(get_machine_id())
    except Exception:  # un resumen fallido no debe impedir jugar
        logging.getLogger(__name__).exception("No se pudo resumir los meses cerrados")
    if args.launch:
        try:
            GameLauncherController().launch_game(args.launch, args.platform)
        except ValueError:  # ej. acceso directo a un juego que ya no está
            logging.getLogger(__name__).exception("No se pudo lanzar '%s'", args.launch)
            sys.exit(1)
    else:
        start_qt_ui()


def start_qt_ui() -> None:
    from interface_files.qt_interface import QtLauncherUI
    from interface_files.ui_handler import init_event_bus

    init_event_bus("Qt")
    GameLauncherController()  # cierra las sesiones huérfanas antes de mostrar la UI
    QtLauncherUI.launch_ui()


if __name__ == "__main__":
    main()
