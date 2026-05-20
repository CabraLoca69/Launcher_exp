import os
import sys
import platform
import ctypes
from pathlib import Path
from PIL import Image, ImageTk

import datafiles

# =============== OPTIONAL UI ADAPTER ====================
class IconUIAdapter:
    def __init__(self, provider):
        self.provider = provider

    def get_icon(self, path, size=(16,16)):
        img = self.provider.get_icon(path, size)
        return ImageTk.PhotoImage(img)


def load_icon(path, size=(16,16)):
    path = Path(path)
    if platform.system() == "Linux" and path.suffix.lower() == ".ico":
        path = ico_to_png(path, output_dir=path.parent)
    img = Image.open(path).resize(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img) 

def ico_to_png(ico_path, output_dir=None, size=(256,256)):
    """
    Convierte un archivo .ico a .png, evitando regenerar si ya existe.
    
    :param ico_path: Ruta del archivo .ico (Path o str)
    :param output_dir: Directorio donde guardar el .png (por defecto el mismo del .ico)
    :param size: Tamaño del .png generado (ancho, alto)
    :return: Ruta del archivo .png generado (Path)
    """
    ico_path = Path(ico_path)
    if not ico_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {ico_path}")

    # Directorio destino
    if output_dir is None:
        output_dir = ico_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    png_path = output_dir / (ico_path.stem + ".png")

    # ❗ Si ya existe, no lo volvemos a generar
    if png_path.exists():
        return png_path

    # Convertir
    img = Image.open(ico_path).convert("RGBA")
    if size:
        img.thumbnail(size)

    img.save(png_path, "PNG")

    return png_path