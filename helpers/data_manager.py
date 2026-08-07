import os

#--------- imports internos -------
from data_access.datafiles import ICONS, db

from .file_manager import FileManager
from .safe_threading import safe_thread

from platform_adapters.platform_handler import PlatformHandler

_favorites_limit= 6

class DataManager():
    def __init__(self):
        self.grouped = True

    def reload_in_thread(self, ui, on_callback):
        def worker():
            all_data = []

            tab_order = db.get("global.tab_order", [])        

            for platform_name in tab_order:
                all_data.append(self.collect_platform_data(platform_name))

            ui.root.after(0, lambda: on_callback(all_data))

        safe_thread(worker)

    def collect_platform_data(self, platform_name):
        grouped = True
        default_icon = os.path.join(ICONS, "no_icon.ico")
    
        result = {
            "platform": platform_name,
            "games": [],
            "grouped": [],
            "favorites": [],
            "recent": [],
            "by_month": {}
        }

        game_list   = db.get_children(f"{platform_name}.game_list")
        game_times  = db.get_children(f"{platform_name}.game_times")
        favorites   = db.get_children(f"{platform_name}.favorites")

        if grouped:
            icons = PlatformHandler().get("icons")
            for name, path in sorted(game_list.items(), key=lambda item: FileManager().sort_key(item[0], game_times)):
                game_info = {"name": name, "path": path, "icon": icons.get_icon(path) or default_icon}
                result["grouped"].append(game_info)

        return result

    def toggle_favorite(self, platform_name, game_name, limit = _favorites_limit):
        favorites = db.get(f"{platform_name}.favorites", [])
        if game_name in favorites:
            db.set(f"{platform_name}.favorites", [g for g in favorites if g != game_name])
            return True, f"Juego '{game_name}' eliminado de favoritos."
        
        if len(favorites) >= limit:
            return False, f"Solo se permiten {limit} favoritos por plataforma."

        db.set(f"{platform_name}.favorites", favorites + [game_name])
        return True,f"Juego '{game_name}' agregado a favoritos."