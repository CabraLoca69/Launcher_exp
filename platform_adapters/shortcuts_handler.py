import logging
import os
import shutil
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    import win32com.client

# --------- imports internos -------
from data_access.datafiles import ICONS, ICONS_CACHE_DIR
from helpers.icon_utils import icon_cache_name

logger = logging.getLogger(__name__)
_SCRIPT = Path(__file__).resolve().parent.parent / "launcher69.py"


def launcher_target() -> tuple[str, str]:
    """Programa a ejecutar y argumentos previos al `--launch`.

    Congelado, el ejecutable es el launcher. Desde el código, `sys.executable` es
    Python y hay que pasarle el script.
    """
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    return sys.executable, f'"{_SCRIPT}" '


def launch_args(platform_name: str, game_name: str) -> str:
    """Argumentos con los que un acceso directo abre el launcher para este juego."""
    prefix = launcher_target()[1]
    return f'{prefix}--launch "{game_name}" --platform "{platform_name}"'


class ShortcutCreator:
    def create_direct_access(
        self, platform_name, game_name, game_path, destino_desktop=True
    ):
        raise NotImplementedError

    def create_start_menu_shortcut(
        self, platform_name, game_name, game_path, icon_path=None
    ):
        raise NotImplementedError


# _____________________WINDOWS____________________
class WindowsShortcutCreator(ShortcutCreator):
    def create_direct_access(
        self, platform_name, game_name, game_path, destino_desktop=True
    ):
        shell = win32com.client.Dispatch("WScript.Shell")

        desktop = shell.SpecialFolders("Desktop") if destino_desktop else os.getcwd()

        shortcut_path = os.path.join(
            desktop, f"{os.path.splitext(game_name)[0]} Launcher.lnk"
        )

        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = launcher_target()[0]
        shortcut.Arguments = launch_args(platform_name, game_name)
        shortcut.IconLocation = game_path
        shortcut.save()

    def create_start_menu_shortcut(
        self, platform_name, game_name, game_path, icon_path=ICONS
    ):

        try:
            launcher_exe = Path(launcher_target()[0]).resolve()
            launcher_dir = launcher_exe.parent

            start_menu = (
                Path(os.getenv("APPDATA"))
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
            )

            start_menu.mkdir(parents=True, exist_ok=True)

            shortcut_path = start_menu / f"{game_name}.lnk"

            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(str(shortcut_path))

            shortcut.TargetPath = str(launcher_exe)
            shortcut.Arguments = launch_args(platform_name, game_name)
            shortcut.WorkingDirectory = str(launcher_dir)
            shortcut.IconLocation = game_path

            shortcut.save()

        except Exception:
            logger.exception("Error creando el acceso en el menú Inicio")


# ______________ LINUX ______________
class LinuxShortcutCreator(ShortcutCreator):
    def create_direct_access(
        self, platform_name, game_name, game_path, destino_desktop=True
    ):
        desktop_dir = self.get_desktop_dir() if destino_desktop else Path.cwd()
        desktop_dir.mkdir(parents=True, exist_ok=True)

        file_path = desktop_dir / f"{game_name}.desktop"

        icon_target = self._resolve_icon(game_name, game_path)

        content = f"""[Desktop Entry]
Name={game_name}
Comment=Lanzador Cl69
Exec="{launcher_target()[0]}" {launch_args(platform_name, game_name)}
Icon={icon_target}
Terminal=false
Type=Application"""

        file_path.write_text(content)
        os.chmod(file_path, 0o755)

    def create_start_menu_shortcut(
        self, platform_name, game_name, game_path, icon_path=ICONS
    ):

        app_dir = Path.home() / ".local/share/applications"
        app_dir.mkdir(parents=True, exist_ok=True)

        file_path = app_dir / f"{game_name.lower().replace(' ', '_')}.desktop"

        command = f'"{launcher_target()[0]}" {launch_args(platform_name, game_name)}'

        icon_target = self._resolve_icon(game_name, game_path)

        content = f"""[Desktop Entry]
Type=Application
Name={game_name}
Exec={command}
Icon={icon_target}
Terminal=false
Categories=Game;
StartupNotify=true"""

        file_path.write_text(content)
        os.chmod(file_path, 0o755)

    def get_desktop_dir(self):
        xdg_file = Path.home() / ".config" / "user-dirs.dirs"

        if xdg_file.exists():
            for line in xdg_file.read_text().splitlines():
                if line.startswith("XDG_DESKTOP_DIR"):
                    path = line.split("=")[1].strip().replace('"', "")
                    return Path(path.replace("$HOME", str(Path.home())))

        return Path.home() / "Desktop"

    def _resolve_icon(self, game_name, game_path):
        cache_icon_path = ICONS_CACHE_DIR / f"{icon_cache_name(game_path)}.png"

        if not cache_icon_path.exists():
            return Path("/usr/share/pixmaps/default.png")

        icon_dir = Path.home() / ".local/share/icons/launcher69/"
        icon_dir.mkdir(parents=True, exist_ok=True)

        target = icon_dir / f"launcher_{game_name.lower().replace(' ', '_')}.png"

        try:
            shutil.copy(cache_icon_path, target)
            return target
        except OSError:
            logger.warning(
                "No se pudo copiar el ícono %s", cache_icon_path, exc_info=True
            )
            return Path("/usr/share/pixmaps/default.png")
