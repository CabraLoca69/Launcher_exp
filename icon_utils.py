import os
import platform
import datafiles
import subprocess
from pathlib import Path
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

def get_app_icon(path, size=(16,16), fallback_icon=None):
    system = platform.system()
    path = str(path)

    if system == "Windows":
        return ImageTk.PhotoImage(_get_windows_icon(path, size, fallback_icon))
    
    elif system == "Linux":
        if is_wine_executable(path):
            return ImageTk.PhotoImage(get_wine_icon(path, size, fallback_icon))
        else:
            try:
                return ImageTk.PhotoImage(_get_linux_icon(path, size, fallback_icon))
            except Exception:
                # fallback
                fallback_icon = os.path.join(datafiles.ICONS, "no_icon.ico")
                if fallback_icon.suffix.lower() == ".ico":
                    fallback_icon = ico_to_png(fallback_icon, size=size)
                return ImageTk.PhotoImage(Image.open(fallback_icon).resize(size, Image.LANCZOS))
    
    else:
        # MacOS u otros
        fallback_icon = os.path.join(datafiles.ICONS, "no_icon.ico")
        if fallback_icon.suffix.lower() == ".ico":
            fallback_icon = ico_to_png(fallback_icon, size=size)
        return ImageTk.PhotoImage(Image.open(fallback_icon).resize(size, Image.LANCZOS))

# ---------------- Windows ---------------- #
def _get_windows_icon(exe_path, size, fallback_icon):
    """Extrae el ícono principal de un .exe en Windows y lo convierte en PIL.Image"""
    exe_name = os.path.basename(os.path.splitext(exe_path)[0])
    ico_path = os.path.join(datafiles.ICONS_CACHE_DIR, f"{exe_name}.ico")

    if os.path.exists(ico_path):
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
            
            image.save(ico_path, format="ICO", sizes= [size])
            # Liberar recursos
            hdc_mem.DeleteDC()
            hdc.DeleteDC()
            win32gui.DestroyIcon(hicon)

            return image.resize(size, Image.LANCZOS)

    except Exception as e:
        print(f"[WARN] No se pudo extraer ícono de {exe_path}: {e}")
    if fallback_icon == None:
        fallback_icon = os.path.join(datafiles.ICONS , "no_icon.ico")
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

# ------------- Icono por defecto -------------#
def set_window_icon(window, icon_name="icon.ico"):
    """
    Configura el ícono de la ventana Tkinter de forma multiplataforma.
    - En Windows usa .ico directamente.
    - En Linux/macOS convierte a .png y usa wm iconphoto.
    """

    icon_path = Path(datafiles.ICONS) / icon_name

    if platform.system() == "Windows":
        # Tkinter soporta .ico en Windows
        window.iconbitmap(str(icon_path))
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

def is_wine_executable(path: str) -> bool:
    """
    Devuelve True si el archivo es un ejecutable de Windows que probablemente
    se ejecutará con Wine en Linux.
    """
    path = str(path)
    return path.lower().endswith((".exe", ".bat", ".cmd")) or "wine" in path.lower()

def get_wine_icon(path: str, size=(16,16), fallback_icon=None, wineprefix=None, icon_dir=datafiles.ICONS) -> Image.Image:
    """
    Extrae un icono de un ejecutable de Windows en Linux usando icotool.
    Si falla, busca el .ico cacheado desde Windows en datafiles.ICONS_CACHE_DIR.
    Finalmente, usa fallback_icon si nada de eso existe.
    """
    path = str(path)
    fallback_icon = fallback_icon or os.path.join(icon_dir, "no_icon.ico")

    icon_dir = Path(icon_dir)
    icon_dir.mkdir(parents=True, exist_ok=True)

    # Nombre final del PNG en la carpeta de icons
    icon_path = icon_dir / (Path(path).stem + ".png")

    if icon_path.exists():
        return Image.open(icon_path).convert("RGBA").resize(size, Image.LANCZOS)

    # 1️⃣ Intentamos extraer con icotool
    try:
        env = os.environ.copy()
        if wineprefix:
            env["WINEPREFIX"] = str(wineprefix)

        subprocess.run(
            ["icotool", "-x", "-o", str(icon_dir), path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=True
        )

        # icotool genera uno o más PNGs, elegimos el primero
        png_files = list(icon_dir.glob(Path(path).stem + "*.png"))
        if png_files:
            icon_path = png_files[0]
            return Image.open(icon_path).convert("RGBA").resize(size, Image.LANCZOS)
    except Exception as e:
        print(f"[get_wine_icon] icotool falló para {path}: {e}")
    
    # 2️⃣ Buscamos el .ico cacheado de Windows
    cached_icon = Path(datafiles.ICONS_CACHE_DIR) / (Path(path).stem + ".exe.ico")
    if cached_icon.exists():
        try:
            print("try wdw icon")
            png_path = ico_to_png(cached_icon, size=size, output_dir=icon_dir)
            return Image.open(png_path).convert("RGBA").resize(size, Image.LANCZOS)
        except Exception as e:
            print(f"[get_wine_icon] fallo al convertir el .ico cacheado de Windows: {e}")
            
    # 3️⃣ Fallback final
    fallback_icon = Path(icon_dir, "no_icon.ico")
    if fallback_icon.suffix.lower() == ".ico":
        fallback_icon = ico_to_png(fallback_icon, size=size, output_dir=icon_dir)
    return Image.open(fallback_icon).convert("RGBA").resize(size, Image.LANCZOS)
 
def load_icon(path, size=(16, 16)):
    """
    Carga un ícono (ico/png/jpg) y devuelve un ImageTk.PhotoImage.
    En Linux convierte automáticamente .ico a .png.
    """
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