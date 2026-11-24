import os

# --------- imports internos -------
from data_access.datafiles import ICONS, store
from platform_adapters.platform_handler import PlatformHandler

FAVORITES_LIMIT = 6


class DataManager:
    def collect_platform_data(self, platform_name: str) -> dict:
        """Juegos visibles de la plataforma con su ícono, en el orden de la lista."""
        default_icon = os.path.join(ICONS, "no_icon.ico")
        icons = PlatformHandler().get("icons")
        games = [
            {
                "name": g.name,
                "path": g.path,
                "icon": icons.get_icon(g.path) or default_icon,
            }
            for g in store.list_games(platform_name)
        ]
        return {"platform": platform_name, "grouped": games}

    def toggle_favorite(
        self, platform_name: str, game_name: str, limit: int = FAVORITES_LIMIT
    ) -> tuple[bool, str]:
        game = store.get_game(platform_name, game_name)
        if game is None:
            return False, f"Juego '{game_name}' no encontrado."
        if game.favorite:
            store.set_favorite(platform_name, game_name, False)
            return True, f"Juego '{game_name}' eliminado de favoritos."
        if len(store.list_favorites(platform_name)) >= limit:
            return False, f"Solo se permiten {limit} favoritos por plataforma."
        store.set_favorite(platform_name, game_name, True)
        return True, f"Juego '{game_name}' agregado a favoritos."
