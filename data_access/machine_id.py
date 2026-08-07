import uuid

#--------- imports internos -------
from .datafiles import MACHINE_ID_FILE

def get_machine_id():
    """
    Devuelve un id persistente para la máquina.
    Si no existe, genera uno nuevo (uuid4) y lo guarda.
    """
    try:
        if MACHINE_ID_FILE.exists():
            return MACHINE_ID_FILE.read_text(encoding="utf-8").strip()
        else:
            mid = str(uuid.uuid4())
            MACHINE_ID_FILE.write_text(mid, encoding="utf-8")
            return mid
    except Exception as e:
        # En caso raro de fallo, devolvemos un uuid temporal (no persistente)
        return str(uuid.uuid4())