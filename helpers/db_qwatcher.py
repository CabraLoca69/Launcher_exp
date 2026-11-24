from PySide6.QtCore import QObject, QTimer, Signal

# --------- imports internos -------
from data_access.datafiles import store


class RunningGameWatcher(QObject):
    """Avisa cuando termina un juego que corre en otro proceso (ej. --launch)."""

    game_closed_detected = Signal(str, str)  # platform, game_name

    def __init__(self, platform_name, game_name, interval_ms=5000):
        super().__init__()
        self.platform_name = platform_name
        self.game_name = game_name
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check)
        self.timer.start(interval_ms)

    def _check(self):
        if store.open_session_for(self.platform_name, self.game_name) is None:
            self.timer.stop()
            self.game_closed_detected.emit(self.platform_name, self.game_name)
