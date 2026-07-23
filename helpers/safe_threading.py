import threading
import logging
import traceback

def safe_thread(target, *args, daemon = True, **kwargs):
    def wrapper():
        try:
            target(*args, **kwargs)
        except Exception:
            logging.error(f"Error en: {target}")
            logging.error(traceback.format_exc())

    t = threading.Thread(target=wrapper, daemon = daemon)
    t.start()
    return t