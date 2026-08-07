import os
import sys
import ctypes
import platform
from io import BytesIO
from PySide6.QtGui import QIcon, QPixmap
from pathlib import Path

#--------- imports internos -------
from data_access.datafiles import ICONS

from .icon_utils import ico_to_png

DEFAULT_ICON = str(os.path.join(ICONS, "no_icon.ico"))

def load_qicon(path, size=(128, 128)):
    path = Path(path)

    # *El mismo fix para Linux con .ico*
    if platform.system() == "Linux" and path.suffix.lower() == ".ico":
        path = ico_to_png(path, output_dir=path.parent)
    
    if not path:
        return QIcon(DEFAULT_ICON)  # icono por defecto
    
    path = str(path)
    pix = QPixmap(path)

    if pix.isNull():
        return QIcon()  # por si falló
    
    if size:
        pix = pix.scaled(size[0], size[1])
    
    return QIcon(pix)