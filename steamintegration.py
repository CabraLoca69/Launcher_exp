import requests
from datafiles import config
from helpers import Loader

class SteamIntegration:
    def __init__(self, config):
        self.api_key = config.get("steam", {}).get("api_key")
        self.steamid = config.get("steam", {}).get("steamid")

    def is_ready(self):
        return self.api_key is not None and self.steamid is not None

    def resolve_vanity_url(self, vanity_name):
        url = f"http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/?key={self.api_key}&vanityurl={vanity_name}"
        resp = requests.get(url).json()
        return resp["response"].get("steamid")

    def get_owned_games(self):
        if not self.is_ready():
            return []

        url = (
            f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
            f"?key={self.api_key}&steamid={self.steamid}&include_appinfo=1&format=json"
        )
        
        try:
            resp = requests.get(url).json()
            return resp["response"].get("games", [])
        except Exception as e:
            print("Error al obtener juegos de Steam:", e)
            return []

    def format_games(self, games):
        # Devuelve una lista con datos útiles para mostrar
        result = []
        for g in games:
            name = g["name"]
            appid = g["appid"]
            playtime = round(g.get("playtime_forever", 0) / 60, 2)
            icon_url = f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{appid}/{g['img_icon_url']}.jpg"
            result.append({"name": name, "appid": appid, "time": playtime, "icon": icon_url})
        return result
    
    def format_and_cache_games(self, games):
        """Formatea juegos, guarda en config y descarga iconos"""
        result = []
        game_list = config["steam"].setdefault("game_list",{})
        for g in games:
            name = g["name"]
            appid = g["appid"]
            playtime = round(g.get("playtime_forever", 0) / 60, 2)
            icon_url = f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{appid}/{g['img_icon_url']}.jpg"
            
            # Descargar icono localmente
            #icon_path = self.download_icon(appid, icon_url)

            # Guardar info en config (rutas relativas o absolutas, según prefieras)
            game_list[name] = {
                "playtime_hours": playtime,
                #"icon_path": icon_path,
                "appid": appid,
                "icon_url": icon_url,
            }

            result.append({
                "name": name,
                "appid": appid,
                "time": playtime,
                #"icon_local": icon_path,
                "icon_url": icon_url
            })
        Loader.save_config()
        return result
