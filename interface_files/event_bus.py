import time
from safe_threading import safe_thread
from datafiles import db

# --- interfaz común ---
class GameEventBus:
    def register_ui(self, platform, ui_instance):
        raise NotImplementedError

    def notify_game_closed(self, platform_name, game_name):
        raise NotImplementedError


#Tk
class TkEventBus(GameEventBus):
    def __init__(self):
        self.ui_registry = {}
        self.update_thread_running = False

    def register_ui(self, platform, ui_instance):
        self.ui_registry[platform] = ui_instance
        if not self.update_thread_running:
            self.update_thread_running = True
            safe_thread(self._watcher)

    def notify_game_closed(self, platform_name, game_name):
        # flag en db, la lee tk y actualiza - deprecada en futuras versiones
        db.set(f"global.update_ui.{platform_name}", game_name)

    def _watcher(self):
        while True:
            time.sleep(2)
            for platform_name, ui in list(self.ui_registry.items()):
                game_name = db.get(f"global.update_ui.{platform_name}")
                if not game_name:
                    continue
                db.delete(f"global.update_ui.{platform_name}")
                try:
                    ui.update_on_close(game_name, platform_name)
                except Exception as e:
                    logging.error(f"Error updating UI for {platform_name}: {e}")


#Qt
from PySide6.QtCore import QObject, Signal

class QtEventBus(QObject, GameEventBus):
    game_closed = Signal(str, str)  # platform_name, game_name

    def __init__(self):
        super().__init__()
        self.ui_registry = {}
        self.game_closed.connect(self._on_game_closed)

    def register_ui(self, platform, ui_instance):
        self.ui_registry[platform] = ui_instance

    def notify_game_closed(self, platform_name, game_name):
        # esto puede llamarse desde CUALQUIER thread, Qt lo marshalla solo
        self.game_closed.emit(platform_name, game_name)

    def _on_game_closed(self, platform_name, game_name):
        # esto SIEMPRE corre en el thread de la UI (main thread)
        ui = self.ui_registry.get(platform_name)
        if ui:
            try:
                ui.update_on_close(game_name, platform_name)
            except Exception as e:
                logging.error(f"Error updating UI for {platform_name}: {e}")