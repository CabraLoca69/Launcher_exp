import subprocess
import sys
import os
import shutil
from pathlib import Path

from datafiles import db, ICONS_CACHE_DIR
from icon_utils import IconUIAdapter, IconProviderFactory

if sys.platform.startswith("win"):
    import win32com.client

# RUNNERS
class GameRunner:
    def run(self, game_path):
        raise NotImplementedError

class WindowsRunner(GameRunner):
    def run(self, game_path):
        return subprocess.Popen(game_path)

class LinuxNativeRunner(GameRunner):
    def run(self, game_path):
        return subprocess.Popen([game_path])

class LinuxWineRunner(GameRunner):
    def __init__(self, wineprefix=None):
        self.wineprefix = wineprefix or os.path.expanduser("~/.wine")

    def run(self, game_path):

        game_name = os.path.splitext(os.path.basename(game_path))[0]
        steam_appid = db.get(f"global.steam_ids.{game_name}")

        if steam_appid:
            return subprocess.Popen(["steam", f"steam://rungameid/{steam_appid}"])

        env = os.environ.copy()
        env["WINEPREFIX"] = self.wineprefix
        
        return subprocess.Popen(["wine", game_path], env=env)

class LinuxSelector(GameRunner):
    def run(self, game_path):
        ext = os.path.splitext(game_path)[1].lower()
        needs_wine = ext in [".exe", ".bat", ".cmd"]

        if needs_wine:
            wineprefix = db.get("global.wineprefix", os.path.expanduser("~/.wine"))
            return LinuxWineRunner(wineprefix).run(game_path)

        return LinuxNativeRunner().run(game_path)


# EXECUTABLE DETECTOR
class ExecutableDetector:
    def is_executable(self, path: str) -> bool:
        raise NotImplementedError

class WindowsExecutableDetector(ExecutableDetector):
    def is_executable(self, path):
        return os.path.splitext(path)[1].lower() in [".exe", ".bat", ".cmd"]

class UnixExecutableDetector(ExecutableDetector):
    def is_executable(self, path):
        return os.path.isfile(path) and os.access(path, os.X_OK)


# SHORTCUTS
class ShortcutCreator:
    def create_direct_access(self, game_name, launcher_path, game_exe_path, destino_desktop=True):
        raise NotImplementedError

    def create_start_menu_shortcut(self, game_name, game_path, icon_path=None):
        raise NotImplementedError

# ---------------- WINDOWS ----------------
class WindowsShortcutCreator(ShortcutCreator):

    def create_direct_access(self, game_name, launcher_path, game_exe_path, destino_desktop=True):
        shell = win32com.client.Dispatch("WScript.Shell")

        desktop = shell.SpecialFolders("Desktop") if destino_desktop else os.getcwd()

        shortcut_path = os.path.join(
            desktop,
            f"{os.path.splitext(game_name)[0]} Cl69.lnk"
        )

        launcher_dir = os.path.dirname(launcher_path)

        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = launcher_path
        shortcut.Arguments = f'--launch "{game_name}"'
        shortcut.WorkingDirectory = launcher_dir
        shortcut.IconLocation = game_exe_path
        shortcut.save()

    def create_start_menu_shortcut(self, game_name, game_path, icon_path=None):

        try:
            launcher_exe = Path(sys.executable).resolve()
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
            shortcut.Arguments = f'--launch "{game_name}"'
            shortcut.WorkingDirectory = str(launcher_dir)
            shortcut.IconLocation = game_path

            shortcut.save()

        except Exception as e:
            print(f"Error creando Start Menu shortcut: {e}")

# ---------------- LINUX ----------------
def get_desktop_dir():
    xdg_file = Path.home() / ".config" / "user-dirs.dirs"

    if xdg_file.exists():
        for line in xdg_file.read_text().splitlines():
            if line.startswith("XDG_DESKTOP_DIR"):
                path = line.split("=")[1].strip().replace('"', "")
                return Path(path.replace("$HOME", str(Path.home())))

    return Path.home() / "Desktop"

class LinuxShortcutCreator(ShortcutCreator):

    def create_direct_access(self, game_name, launcher_path, game_exe_path, destino_desktop=True):

        desktop_dir = get_desktop_dir() if destino_desktop else Path.cwd()
        desktop_dir.mkdir(parents=True, exist_ok=True)

        file_path = desktop_dir / f"{game_name}.desktop"

        icon_target = self._resolve_icon(game_exe_path, game_name)

        content = f"""[Desktop Entry]
                        Name={game_name}
                        Comment=Lanzador Cl69
                        Exec="{launcher_path}" --launch "{game_name}"
                        Icon={icon_target}
                        Terminal=false
                        Type=Application"""

        file_path.write_text(content)
        os.chmod(file_path, 0o755)

    def create_start_menu_shortcut(self, game_name, game_path, icon_path=None):

        app_dir = Path.home() / ".local/share/applications"
        app_dir.mkdir(parents=True, exist_ok=True)

        file_path = app_dir / f"{game_name.lower().replace(' ', '_')}.desktop"

        #OJO ACA PUEDE NO FUNCIONAR EL ACCESO DIRECTO
        command = f'"{sys.executable}" "{Path(__file__).resolve()}" --launch "{game_name}"'

        icon_target = self._resolve_icon(game_path, game_name)

        content = f"""[Desktop Entry]
                    Type=Application
                    Name={game_name}
                    Exec={command}
                    Icon={icon_target}
                    Terminal=false
                    Categories=Game;
                    StartupNotify=true
                    """

        file_path.write_text(content)
        os.chmod(file_path, 0o755)

    def _resolve_icon(self, game_exe_path, game_name):

        try:
            if os.path.exists(game_exe_path):
                icons = IconUIAdapter(IconProviderFactory.create())
                icons.get_icon(game_exe_path)
                
        except Exception:
            pass

        cache_icon_path = ICONS_CACHE_DIR / f"{Path(game_exe_path).stem}.png"

        if not cache_icon_path.exists():
            return Path("/usr/share/pixmaps/default.png")

        icon_dir = Path.home() / ".local/share/icons"
        icon_dir.mkdir(parents=True, exist_ok=True)

        target = icon_dir / f"{game_name.lower().replace(' ', '_')}.png"

        try:
            shutil.copy(cache_icon_path, target)
            return target
        except Exception:
            return Path("/usr/share/pixmaps/default.png")

#Submenus 
class MenuCreator:
    def create_menu(self, menu, game_name, btn_props, frame):
        raise NotImplementedError

class BaseMenuCreator(MenuCreator):
    def add_common_buttons(self, menu, game_name, btn_props, frame, platform_name):
        if game_name:
            menu.add_button("★ Favoritos", 25, "warning-outline",
                            lambda: frame.toggle_favorite(game_name))

            menu.add_button("⤓ Crear acceso directo", 25, "info-outline",
                            lambda: frame.create_direct_access(
                                game_name,
                                os.path.abspath(sys.argv[0]),
                                db.get(f"{platform_name}.game_list.{game_name}"),
                                destino_desktop=True))

            menu.add_button("📌 Añadir a inicio", 25, "info-outline",
                            lambda: frame.create_start_menu_shortcut(
                                game_name,
                                db.get(f"{platform_name}.game_list.{game_name}"),
                                ICONS))

            menu.add_button("📁 Archivos locales", 25, "info-outline",
                            lambda: frame.goto_folder(game_name))

            menu.add_button("📂 Cambiar directorio", 25, "info-outline",
                            lambda: frame.change_game_directory(game_name))

            menu.add_button("🗑 Eliminar juego", 25, "danger-outline",
                            frame.confirm_remove)

        else:
            menu.add_button("＋ Agregar juego", 25, "success-outline", frame.add_exe)

        return menu

class WindowsMenuCreator(BaseMenuCreator):
    def create_menu(self, menu, game_name, btn_props, frame):
        if not btn_props:
                menu.add_button("▶ Jugar", 25, "success-outline", frame.launch_game)
        return self.add_common_buttons(menu, game_name, btn_props, frame, platform_name="windows")

class LinuxMenuCreator(BaseMenuCreator):
    def create_menu(self, menu, game_name, btn_props, frame):
        if not btn_props:
                menu.add_button("▶ Jugar", 25, "success-outline", frame.launch_game)
        if game_name:
            menu.add_button("Steam ID", 25, "info-outline",
                            lambda: frame.ask_steam_id(game_name))

        return self.add_common_buttons(menu, game_name, btn_props, frame, platform_name="linux")


