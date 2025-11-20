import threading
import logging
import traceback

def safe_thread(target, *args, **kwargs):
    def wrapper():
        try:
            target(*args, **kwargs)
        except Exception:
            logging.error(f"Target: {target}")
            logging.error(traceback.format_exc())

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    return t