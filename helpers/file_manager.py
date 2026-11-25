import glob
import logging
import os

# --------- imports internos -------
from data_access.datafiles import ICONS_CACHE_DIR, store
from helpers.icon_utils import icon_cache_name
from platform_adapters.platform_handler import PlatformHandler

logger = logging.getLogger(__name__)

IGNORE_KEYWORDS = (
    "vc_redist",
    "unins",
    "setup",
    "install",
    "dxsetup",
    "report",
    "dotnet",
    "readme",
    "helper",
    "support",
    "launcher",
    "win64",
)


class FileManager:
    def add_platform(self, platform_name: str, folder: str) -> None:
        """Crea la plataforma (o la vuelve a mostrar) y escanea su primera carpeta."""
        store.add_platform(platform_name)
        self.add_folder(platform_name, folder)

    def add_folder(self, platform_name: str, folder: str) -> str:
        """Agrega la carpeta y muestra sus juegos, también los que estaban ocultos."""
        store.add_folder(platform_name, folder)
        self._scan_folder(platform_name, folder, revive=True)
        return folder

    def add_game(self, platform_name: str, exe_path: str) -> tuple[bool, str]:
        name = PlatformHandler().get("exedetect").game_name(exe_path)
        if not store.add_game(platform_name, name, exe_path):
            return False, f"Ya existe un juego llamado '{name}' en esta plataforma."
        return True, name

    def delete_game(self, platform_name: str, game_name: str) -> None:
        """Oculta el juego (sus horas se conservan) y borra su ícono cacheado."""
        game = store.get_game(platform_name, game_name)
        if game:
            self.remove_game_icon(game.path)
        store.hide_game(platform_name, game_name)

    def delete_folder(self, platform_name: str, folder_path: str) -> list[str]:
        prefix = os.path.join(folder_path, "")  # con separador: /PC no incluye /PC2
        removed = [
            g.name for g in store.list_games(platform_name) if g.path.startswith(prefix)
        ]
        for name in removed:
            self.delete_game(platform_name, name)
        store.remove_folder(platform_name, folder_path)
        return removed

    def delete_platform(self, platform_name: str) -> None:
        for game in store.list_games(platform_name):
            self.remove_game_icon(game.path)
        store.hide_platform(platform_name)

    def rename_platform(self, old_name: str, new_name: str) -> bool:
        return store.rename_platform(old_name, new_name)

    def scan_for_games(self, platform_name: str) -> None:
        """Busca juegos nuevos en todas las carpetas. Los que se borraron siguen ocultos."""
        for folder in store.list_folders(platform_name):
            self._scan_folder(platform_name, folder, revive=False)

    def _scan_folder(self, platform_name: str, folder: str, revive: bool) -> None:
        if not os.path.isdir(folder):
            return
        detector = PlatformHandler().get("exedetect")
        for root, _, files in os.walk(folder):
            for file in files:
                full_path = os.path.join(root, file)
                if not detector.is_executable(full_path):
                    continue
                if any(k in file.lower() for k in IGNORE_KEYWORDS):
                    continue
                store.upsert_game(
                    platform_name, detector.game_name(file), full_path, revive
                )

    def remove_game_icon(self, game_path: str) -> None:
        if not game_path:
            return
        pattern = os.path.join(ICONS_CACHE_DIR, icon_cache_name(game_path) + ".*")
        for icon_file in glob.glob(pattern):
            try:
                os.remove(icon_file)
            except OSError as e:
                logger.warning("No se pudo eliminar %s: %s", icon_file, e)
