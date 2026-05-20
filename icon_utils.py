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

    def get_icon(self, path, size=(16, 16)):
        img = self.provider.get_icon(path, size)
        return ImageTk.PhotoImage(img)

# ------------- Icono por defecto -------------#
def set_window_icon(window, icon_name="icon.ico"):
    icon_path = Path(datafiles.ICONS) / icon_name

    if platform.system() == "Windows":
        def resource_path(rel_path):
            if hasattr(sys, "_MEIPASS"):
                return os.path.join(sys._MEIPASS, rel_path)
            return rel_path
        
        icon_path = resource_path(icon_path)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Launcher69.App")
        try:
            window.iconbitmap(icon_path)
        except Exception as e:
            print(f"Error seteando icono: {e}")
    else:
        # Convertir a PNG (si no existe ya)
        png_path = icon_path.with_suffix(".png")
        if not png_path.exists():
            try:
                img = Image.open(icon_path)
                img.save(png_path)
            except Exception as e:
                print(f"[WARN] No se pudo convertir {icon_path} a PNG: {e}")
                return

        # Usar el PNG en Linux/macOS
        img = Image.open(png_path)
        photo = ImageTk.PhotoImage(img)
        window.tk.call('wm', 'iconphoto', window._w, photo)
        window._icon_photo = photo  # mantener referencia

def load_icon(path, size=(16, 16)):
    path = Path(path)
    if platform.system() == "Linux" and path.suffix.lower() == ".ico":
        path = ico_to_png(path, output_dir=path.parent, size=size)
    img = Image.open(path).resize(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img) 

def ico_to_png(ico_path, output_dir=None, size=(64, 64)):
    """
    Convierte un archivo .ico a .png.
    
    :param ico_path: Ruta del archivo .ico (Path o str)
    :param output_dir: Directorio donde guardar el .png (opcional, por defecto el mismo del .ico)
    :param size: Tamaño del .png generado (ancho, alto)
    :return: Ruta del archivo .png generado (Path)
    """
    ico_path = Path(ico_path)
    if not ico_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {ico_path}")

    # Si no se especifica salida, lo dejo en el mismo dir
    if output_dir is None:
        output_dir = ico_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    png_path = output_dir / (ico_path.stem + ".png")

    # Abrir, redimensionar y guardar como PNG
    img = Image.open(ico_path).convert("RGBA")
    if size:
        img.thumbnail(size)
    img.save(png_path, "PNG")

    return png_path