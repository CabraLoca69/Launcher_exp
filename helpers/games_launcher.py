import logging
import threading
import time
from datetime import datetime

import psutil

# -------- imports internos -------
from data_access.cloudsync import sync_once
from data_access.datafiles import store
from data_access.machine_id import get_machine_id
from data_access.store import Game, Session
from helpers.safe_threading import safe_thread
from interface_files.ui_handler import get_event_bus
from platform_adapters.platform_handler import PlatformHandler

logger = logging.getLogger(__name__)

HEARTBEAT_S = 60  # cada cuánto se guarda la duración de una partida en curso
# `started_at` se guarda sin fracciones de segundo: margen para comparar relojes
_PID_MARGIN_S = 5


def is_session_alive(session: Session) -> bool:
    """El proceso de la sesión sigue vivo y es el mismo que lanzamos.

    Tras un reinicio, otro proceso puede tener el mismo PID: si arrancó después
    que la sesión, no es el juego.
    """
    if session.pid is None:
        return False
    try:
        process = psutil.Process(session.pid)
        if process.status() == psutil.STATUS_ZOMBIE:
            return False
        started = datetime.fromisoformat(session.started_at).timestamp()
        return process.create_time() <= started + _PID_MARGIN_S
    except psutil.Error:
        return False


def _upload_if_enabled() -> None:
    """Sube en el hilo que llama (el de la partida, no daemon).

    Con `--launch` no hay UI: un hilo daemon moriría al salir el proceso, antes
    de terminar la subida.
    """
    if not store.get_setting("cloud_sync_enabled", False):
        return
    try:
        sync_once(upload=True)
    except Exception:
        logger.exception("Error subiendo el backup a la nube")


class GameLauncherController:
    _instance = None
    _initialized = False
    _new_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._new_lock:
                if not cls._instance:  # doble check adentro del lock
                    store.close_orphan_sessions(is_session_alive)
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if GameLauncherController._initialized:
            return
        self.lock = threading.Lock()
        self.event_bus = get_event_bus()
        GameLauncherController._initialized = True

    def launch_game(self, game_name: str, platform_name: str | None = None) -> None:
        """Lanza un juego. Sin plataforma, lo busca en todas (primera coincidencia)."""
        game = self._resolve(game_name, platform_name)
        safe_thread(self._run_session, game, daemon=False)

    def _resolve(self, game_name: str, platform_name: str | None) -> Game:
        if platform_name is None:
            game = store.find_game(game_name)
        else:
            game = store.get_game(platform_name, game_name)
        if game is None:
            where = f" en '{platform_name}'" if platform_name else ""
            raise ValueError(f"Juego '{game_name}' no encontrado{where}")
        return game

    def _run_session(self, game: Game) -> None:
        with self.lock:
            if store.open_session_for(game.platform, game.name):
                return  # ya está corriendo (ej. doble click)
            if (
                not store.get_setting("allow_multiple_games", True)
                and store.open_sessions()
            ):
                logger.info("Ya hay un juego en ejecución, no se puede iniciar otro.")
                return
            runner = PlatformHandler().get("runner")
            process = runner.run(game.path, steam_appid=game.steam_appid)
            session_id = store.start_session(game.id, get_machine_id(), process.pid)

        self.event_bus.notify_game_started(game.platform, game.name)
        started = time.time()  # reloj de pared: el tiempo suspendido también cuenta
        stop = threading.Event()

        def heartbeat():
            while not stop.wait(HEARTBEAT_S):
                store.update_session(session_id, int(time.time() - started))

        safe_thread(heartbeat)
        try:
            if psutil.pid_exists(process.pid):
                psutil.Process(process.pid).wait()
        except Exception:
            logger.exception("Error esperando el proceso %s", process.pid)
        finally:
            stop.set()
            store.end_session(session_id, int(time.time() - started))
            self.event_bus.notify_game_closed(game.platform, game.name)
            _upload_if_enabled()

    def register_ui(self, platform, ui_instance):
        self.event_bus.register_ui(platform, ui_instance)

    def force_close_game(self, platform_name: str, game_name: str) -> None:
        session = store.open_session_for(platform_name, game_name)
        if session is None or session.pid is None:
            logger.warning("No hay una sesión en curso para '%s'.", game_name)
            return
        try:
            psutil.Process(session.pid).terminate()
            logger.info(
                "Juego '%s' (%s) cerrado forzosamente.", game_name, platform_name
            )
        except psutil.NoSuchProcess:
            logger.warning(
                "El proceso %s ya no existía al intentar cerrarlo.", session.pid
            )
        except Exception:
            logger.exception("Error al cerrar el juego '%s'", game_name)
