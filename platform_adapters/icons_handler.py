import logging
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

# --------- imports internos -------
from data_access.datafiles import ICONS, ICONS_CACHE_DIR
from helpers.icon_utils import ico_to_png, icon_cache_name

logger = logging.getLogger(__name__)

# WINDOWS IMPORTS
if sys.platform.startswith("win"):
    import win32con
    import win32gui
    import win32ui

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
    def get_icon(self, path: str, size=(16, 16)):
        raise NotImplementedError


class WindowsIconProvider(IconProvider):
    # _______extrae iconos de un .exe _____
    def get_icon(self, path, size=(16, 16)):
        ico_path = Path(ICONS_CACHE_DIR) / f"{icon_cache_name(path)}.ico"
        ico_path.parent.mkdir(parents=True, exist_ok=True)

        if ico_path.exists():
            return ico_path

        try:
            large, small = win32gui.ExtractIconEx(path, 0)
            hicon = large[0] if large else (small[0] if small else None)

            if hicon:
                hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, size[0], size[1])

                hdc_mem = hdc.CreateCompatibleDC()
                hdc_mem.SelectObject(hbmp)

                win32gui.DrawIconEx(
                    hdc_mem.GetHandleOutput(),
                    0,
                    0,
                    hicon,
                    size[0],
                    size[1],
                    0,
                    None,
                    win32con.DI_NORMAL,
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
                    1,
                )

                image.save(ico_path, format="ICO", sizes=[size])
                win32gui.DestroyIcon(hicon)

                return ico_path

        except Exception:
            logger.warning("No se pudo extraer el ícono de %s", path, exc_info=True)

        return _fallback_icon(size)


class LinuxIconProvider(IconProvider):
    def get_icon(self, path, size=(16, 16)):
        try:
            if self.is_wine_executable(path):
                return self.get_wine_icon(path, size)
            return self.get_linux_icon(path, size)
        except Exception:
            logger.warning("No se pudo obtener el ícono de %s", path, exc_info=True)
            return _fallback_icon(size)

    # ---------------- busca el icono de un .bin y lo retorna ----------------
    def get_linux_icon(self, path, size):
        icon_path = None

        if path.endswith(".desktop") and DesktopEntry is not None:
            try:
                entry = DesktopEntry.DesktopEntry(path)
                icon_name = entry.getIcon()

                if icon_name:
                    candidates = [
                        Path.home() / ".local/share/icons" / f"{icon_name}.png",
                        Path("/usr/share/icons/hicolor/48x48/apps")
                        / f"{icon_name}.png",
                        Path("/usr/share/pixmaps") / f"{icon_name}.png",
                    ]

                    for c in candidates:
                        if c.exists():
                            icon_path = c
                            break
            except Exception:
                logger.warning("No se pudo leer %s", path, exc_info=True)

        if not icon_path:
            return _fallback_icon(size)

        return icon_path

    # ---------------- extrae el icono de un wine como si fuese un .exe ----------------
    def is_wine_executable(self, path: str) -> bool:
        return path.lower().endswith((".exe", ".bat", ".cmd"))

    def get_wine_icon(self, path: str, size):
        png = Path(ICONS_CACHE_DIR) / f"{icon_cache_name(path)}.png"
        if png.exists():
            return png

        # wrestool escribe un .ico por cada ícono del exe: en una carpeta propia,
        # así no se mezclan con los íconos cacheados de otros juegos.
        try:
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(
                    ["wrestool", "-x", "-t", "group_icon", path, "-o", tmp],
                    capture_output=True,
                    check=False,
                )
                icos = sorted(
                    Path(tmp).glob("*.ico"),
                    key=lambda f: f.stat().st_size,
                    reverse=True,
                )
                if icos:
                    Image.open(icos[0]).save(png)
                    return png
        except OSError:
            logger.warning("No se pudo extraer el ícono de %s", path, exc_info=True)

        return _fallback_icon(size)
