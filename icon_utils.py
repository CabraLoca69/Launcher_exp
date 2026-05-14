import os
import sys
import platform
import datafiles
import subprocess
import ctypes
from pathlib import Path
from PIL import Image, ImageTk

# WINDOWS IMPORTS
if sys.platform.startswith("win"):
    import win32com.client
    import win32gui
    import win32ui
    import win32con

# Linux-only imports
if platform.system() == "Linux":
    try:
        from xdg import DesktopEntry
    except ImportError:
        DesktopEntry = None


# ---------------- FALLBACK ----------------

def _fallback_icon(size):
    fallback = Path(datafiles.ICONS) / "no_icon.ico"

    if fallback.suffix.lower() == ".ico":
        fallback = ico_to_png(fallback, size=size)

    return Image.open(fallback).resize(size, Image.LANCZOS)


# ---------------- WINDOWS ICON ----------------
def _get_windows_icon(exe_path, size):
    exe_name = Path(exe_path).stem
    ico_path = Path(datafiles.ICONS_CACHE_DIR) / f"{exe_name}.ico"

    if ico_path.exists():
        return Image.open(ico_path).resize(size, Image.LANCZOS)

    try:
        large, small = win32gui.ExtractIconEx(exe_path, 0)
        hicon = large[0] if large else (small[0] if small else None)

        if hicon:
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, size[0], size[1])

            hdc_mem = hdc.CreateCompatibleDC()
            hdc_mem.SelectObject(hbmp)

            win32gui.DrawIconEx(
                hdc_mem.GetHandleOutput(),
                0, 0, hicon,
                size[0], size[1],
                0, None,
                win32con.DI_NORMAL
            )

            bmpinfo = hbmp.GetInfo()
            bmpstr = hbmp.GetBitmapBits(True)

            image = Image.frombuffer(
                "RGBA",
                (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                bmpstr,
                "raw",
                "BGRA",
                0,
                1
            )

            ico_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(ico_path, format="ICO", sizes=[size])

            win32gui.DestroyIcon(hicon)

            return image.resize(size, Image.LANCZOS)

    except Exception as e:
        print(f"[WARN] Windows icon error: {e}")

    return _fallback_icon(size)

# ---------------- LINUX ICON ----------------
def _get_linux_icon(path, size):
    icon_path = None

    if path.endswith(".desktop"):
        try:
            entry = DesktopEntry.DesktopEntry(path)
            icon_name = entry.getIcon()

            if icon_name:
                candidates = [
                    Path.home() / ".local/share/icons" / f"{icon_name}.png",
                    Path("/usr/share/icons/hicolor/48x48/apps") / f"{icon_name}.png",
                    Path("/usr/share/pixmaps") / f"{icon_name}.png",
                ]

                for c in candidates:
                    if c.exists():
                        icon_path = c
                        break
        except Exception:
            pass

    if not icon_path:
        return _fallback_icon(size)

    return Image.open(icon_path).resize(size, Image.LANCZOS)


# ---------------- WINE ICON ----------------

def is_wine_executable(path: str) -> bool:
    return path.lower().endswith((".exe", ".bat", ".cmd"))


def get_wine_icon(path: str, size=(16, 16)):
    icon_dir = Path(datafiles.ICONS)
    icon_dir.mkdir(parents=True, exist_ok=True)

    icon_path = icon_dir / f"{Path(path).stem}.png"

    if icon_path.exists():
        return Image.open(icon_path).resize(size, Image.LANCZOS)

    try:
        subprocess.run(
            ["icotool", "-x", "-o", str(icon_dir), path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )

        pngs = list(icon_dir.glob(f"{Path(path).stem}*.png"))
        if pngs:
            return Image.open(pngs[0]).resize(size, Image.LANCZOS)

    except Exception as e:
        print(f"[Wine icon error] {e}")

    cached = Path(datafiles.ICONS_CACHE_DIR) / f"{Path(path).stem}.exe.ico"

    if cached.exists():
        png = ico_to_png(cached)
        return Image.open(png).resize(size, Image.LANCZOS)

    return _fallback_icon(size)


# =========================================================
# ================= ICON PROVIDER =========================
# =========================================================

class IconProvider:
    def get_icon(self, path: str, size=(16, 16)):
        raise NotImplementedError


class WindowsIconProvider(IconProvider):
    def get_icon(self, path, size=(16, 16)):
        return _get_windows_icon(path, size)


class LinuxIconProvider(IconProvider):
    def get_icon(self, path, size=(16, 16)):
        if is_wine_executable(path):
            return get_wine_icon(path, size)

        try:
            return _get_linux_icon(path, size)
        except Exception:
            return _fallback_icon(size)


class IconProviderFactory:
    @staticmethod
    def create():
        if sys.platform.startswith("win"):
            return WindowsIconProvider()
        return LinuxIconProvider()

# =============== OPTIONAL UI ADAPTER =====================
from PIL import ImageTk


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