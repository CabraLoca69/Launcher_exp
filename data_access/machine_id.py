import logging
import uuid

# --------- imports internos -------
from .datafiles import MACHINE_ID_FILE

logger = logging.getLogger(__name__)
_cached: str | None = None


def get_machine_id() -> str:
    """Id persistente de esta PC. Si no existe, lo genera (uuid4) y lo guarda.

    Si el archivo no se puede leer ni escribir, usa un id temporal, pero el mismo
    durante toda la ejecución (así las sesiones de esta corrida quedan juntas).
    """
    global _cached
    if _cached is None:
        try:
            if MACHINE_ID_FILE.exists():
                _cached = MACHINE_ID_FILE.read_text(encoding="utf-8").strip()
            else:
                _cached = str(uuid.uuid4())
                MACHINE_ID_FILE.write_text(_cached, encoding="utf-8")
        except OSError:
            logger.exception("No se pudo leer/guardar el id de la PC; uso uno temporal")
            _cached = _cached or str(uuid.uuid4())
    return _cached
