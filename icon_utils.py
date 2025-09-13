import os
import platform
from PIL import Image, ImageTk

# Windows-only imports
if platform.system() == "Windows":
    import win32gui
    import win32ui
    import win32con

# Linux-only imports
if platform.system() == "Linux":
    try:
        from xdg import DesktopEntry
    except ImportError:
        DesktopEntry = None

def get_app_icon(path, size=(64, 64), fallback_icon="default.png"):
    """
    Devuelve SIEMPRE un ImageTk.PhotoImage (Tkinter).
    En Windows extrae el ícono incrustado en .exe.
    En Linux busca icono desde .desktop o usa un fallback.
    """

    system = platform.system()

    if system == "Windows":
        image = _get_windows_icon(path, size, fallback_icon)
    elif system == "Linux":
        image = _get_linux_icon(path, size, fallback_icon)
    else:
        image = Image.open(fallback_icon).resize(size, Image.LANCZOS)

    return ImageTk.PhotoImage(image)


# ---------------- Windows ---------------- #
def _get_windows_icon(exe_path, size, fallback_icon):
    """Extrae el ícono principal de un .exe en Windows y lo convierte en PIL.Image"""
    try:
        large, small = win32gui.ExtractIconEx(exe_path, 0)
        hicon = large[0] if large else (small[0] if small else None)

        if hicon:
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, size[0], size[1])

            hdc_mem = hdc.CreateCompatibleDC()
            hdc_mem.SelectObject(hbmp)
            win32gui.DrawIconEx(hdc_mem.GetHandleOutput(), 0, 0, hicon,
                                size[0], size[1], 0, None, win32con.DI_NORMAL)

            bmpinfo = hbmp.GetInfo()
            bmpstr = hbmp.GetBitmapBits(True)

            # Convertir a PIL.Image
            image = Image.frombuffer(
                'RGBA',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRA', 0, 1
            )

            # Liberar recursos
            hdc_mem.DeleteDC()
            hdc.DeleteDC()
            win32gui.DestroyIcon(hicon)

            return image.resize(size, Image.LANCZOS)

    except Exception as e:
        print(f"[WARN] No se pudo extraer ícono de {exe_path}: {e}")

    return Image.open(fallback_icon).resize(size, Image.LANCZOS)


# ---------------- Linux ---------------- #
def _get_linux_icon(path, size, fallback_icon):
    """Obtiene icono desde .desktop o usa fallback en Linux"""
    icon_path = None

    if path.endswith(".desktop") and DesktopEntry:
        try:
            entry = DesktopEntry.DesktopEntry(path)
            icon_name = entry.getIcon()

            if icon_name:
                # Ruta absoluta
                if os.path.isabs(icon_name) and os.path.exists(icon_name):
                    icon_path = icon_name
                else:
                    # Buscar en rutas comunes
                    possible_paths = [
                        os.path.join(os.path.expanduser("~/.local/share/icons"), icon_name + ".png"),
                        os.path.join("/usr/share/icons/hicolor/48x48/apps", icon_name + ".png"),
                        os.path.join("/usr/share/pixmaps", icon_name + ".png"),
                    ]
                    for p in possible_paths:
                        if os.path.exists(p):
                            icon_path = p
                            break
        except Exception as e:
            print(f"[WARN] No se pudo leer .desktop {path}: {e}")

    if not icon_path:
        icon_path = fallback_icon

    return Image.open(icon_path).resize(size, Image.LANCZOS)