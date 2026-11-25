import logging
import threading

logger = logging.getLogger(__name__)


def safe_thread(target, *args, daemon=True, **kwargs):
    def wrapper():
        try:
            target(*args, **kwargs)
        except Exception:
            logger.exception("Error en el hilo %s", target)

    t = threading.Thread(target=wrapper, daemon=daemon)
    t.start()
    return t
