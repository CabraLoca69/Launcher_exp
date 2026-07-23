import sys
from pathlib import Path

#este codigo debe vivir en la raiz del proyecto, todos los paths nacen relativos al raiz, 
#aca nos encargamos de definir el raiz, data_access.datafiles hace el resto
def get_portable_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent