import os
import sys
import platform
import subprocess
import ctypes
from pathlib import Path
from PIL import Image, ImageTk

from data_access.datafiles import ICONS, ICONS_CACHE_DIR
from helpers.icon_utils import ico_to_png

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

def _fallback_icon(size):
    fallback = Path(ICONS) / "no_icon.ico"

    if fallback.suffix.lower() == ".ico":
        fallback = ico_to_png(fallback, size=size)

    return fallback

class IconProvider:
    def set_window_icon(self, window, icon_name="icon.ico"):
        raise NotImplementedError
        
    def get_icon(self, path: str, size=(16, 16)):
        raise NotImplementedError

class WindowsIconProvider(IconProvider):
    #____ ICONO DE LA VENTANA ______
    def set_window_icon(self, window, icon_name="icon.ico"):
        icon_path = Path(ICONS) / icon_name
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
    
    #_______extrae iconos de un .exe _____
    def get_icon(self, path, size=(16, 16)):
        exe_name = Path(exe_path).stem
        ico_path = Path(ICONS_CACHE_DIR) / f"{exe_name}.ico"
        ico_path.parent.mkdir(parents=True, exist_ok=True)

        if ico_path.exists():
            return ico_path

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

                image.save(ico_path, format="ICO", sizes=[size])
                win32gui.DestroyIcon(hicon)

                return ico_path

        except Exception as e:
            print(f"[WARN] Windows icon error: {e}")

        return _fallback_icon(size)

class LinuxIconProvider(IconProvider):
    #____ ICONO DE LA VENTANA ______
    def set_window_icon(self, window, icon_name="icon.ico"):
        icon_path = Path(ICONS) / icon_name
        
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

    def get_icon(self, path, size=(16, 16)):
        if self.is_wine_executable(path):
            return self.get_wine_icon(path, size)

        try:
            return self.get_linux_icon(path, size)
        except Exception:
            return _fallback_icon(size)

    # ---------------- busca el icono de un .bin y lo retorna ----------------
    def get_linux_icon(self, path, size):
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

        return ico_path

    # ---------------- extrae el icono de un wine como si fuese un .exe ----------------
    def is_wine_executable(self, path: str) -> bool:
        return path.lower().endswith((".exe", ".bat", ".cmd"))

    def get_wine_icon(self, path: str, size):
        icon_dir = Path(ICONS_CACHE_DIR)
        icon_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(path).stem

        fixed_ico = icon_dir / f"{stem}.ico"       
        fixed_png = icon_dir / f"{stem}.png"     

        #Si ya exist el icono, devolverlo
        if fixed_png.exists():
            return fixed_png

        try:
            # extraer todos los iconos
            subprocess.run(
                ["wrestool", "-x", "-t", "group_icon", path, "-o", icon_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            ico_files = list(icon_dir.glob(f"{stem}*.ico"))

            if ico_files:
                ico_files.sort(key=lambda f: f.stat().st_size, reverse=True)

                best_ico = ico_files[0] 
                best_ico.rename(fixed_ico)

                for extra in ico_files[1:]:
                    extra.unlink(missing_ok=True)

                img = Image.open(fixed_ico)
                img.save(fixed_png)

                return fixed_png

        except Exception as e:
            print(f"[Wine icon error] {e}")

        # fallback: si ya existe un .ico fijo viejo
        if fixed_ico.exists():
            img = Image.open(fixed_ico)
            img.save(fixed_png)
            return fixed_png

        return _fallback_icon(size)




