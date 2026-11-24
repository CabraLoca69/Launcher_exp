import logging

from PySide6.QtCore import QObject, Signal

# --------- imports internos -------
from data_access.datafiles import store
from helpers.db_qwatcher import RunningGameWatcher

logger = logging.getLogger(__name__)


# --- interfaz común ---
class GameEventBus:
    def register_ui(self, platform, ui_instance):
        raise NotImplementedError

    def notify_game_started(self, platform_name, game_name):
        raise NotImplementedError

    def notify_game_closed(self, platform_name, game_name):
        raise NotImplementedError


class QtEventBus(QObject, GameEventBus):
    game_closed = Signal(str, str)
    game_started = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.ui_registry = {}
        self.game_closed.connect(self._on_game_closed)
        self.game_started.connect(lambda p, g: self._running.add((p, g)))
        self._watchers = []
        # juegos que la UI ya sabe que corren (lanzados acá o vigilados)
        self._running: set[tuple[str, str]] = set()

    def register_ui(self, platform, ui_instance):
        self.ui_registry[platform] = ui_instance
        self._watch_running(platform, ui_instance)

    def notify_game_closed(self, platform_name, game_name):
        self.game_closed.emit(platform_name, game_name)

    def notify_game_started(self, platform_name, game_name):
        self.game_started.emit(platform_name, game_name)

    def watch_external(self):
        """Busca juegos lanzados desde otro proceso (accesos directos con --launch).

        La UI la llama periódicamente con un timer.
        """
        for platform_name, ui in list(self.ui_registry.items()):
            self._watch_running(platform_name, ui)

    def _watch_running(self, platform_name, ui_instance):
        """Empieza a vigilar los juegos de la plataforma que corren y la UI no conocía."""
        for session in store.open_sessions():
            key = (platform_name, session.game)
            if session.platform != platform_name or key in self._running:
                continue
            self._running.add(key)
            if hasattr(ui_instance, "mark_game_running"):
                ui_instance.mark_game_running(session.game)
            self.notify_game_started(platform_name, session.game)
            watcher = RunningGameWatcher(platform_name, session.game)
            watcher.game_closed_detected.connect(self.notify_game_closed)
            self._watchers.append(watcher)

    def _on_game_closed(self, platform_name, game_name):
        self._running.discard((platform_name, game_name))
        ui = self.ui_registry.get(platform_name)
        if ui:
            try:
                ui.update_on_close(game_name, platform_name)
            except Exception:
                logger.exception("Error actualizando la UI de %s", platform_name)


class NullEventBus(GameEventBus):
    """Sin UI (`--launch`): nadie escucha."""

    def register_ui(self, platform, ui_instance):
        pass

    def notify_game_started(self, platform_name, game_name):
        pass

    def notify_game_closed(self, platform_name, game_name):
        pass
