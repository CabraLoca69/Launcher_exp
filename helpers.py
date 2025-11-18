import os
import json
import logging
import subprocess
import threading
import psutil
import time
import sys
import datafiles
import signal
from machine_id import get_machine_id
from cloudsync import call_upload
from datetime import datetime
from PIL import Image, ImageTk
from tkinter import filedialog
from icon_utils import get_app_icon, load_icon

class Loader:
    def __init__(self):
        self.default_icon= load_icon(os.path.join(datafiles.ICONS, "no_icon.ico"), size=(16,16))
        self.grouped = True
        pass
    
    def add_folder(self, platform_name):  # agrega un directorio a la lista 
        folder = safe_askdirectory()

        # Crear la sección de la plataforma si no existe
        if platform_name not in datafiles.config:
            datafiles.config[platform_name] = {
                "platform_folders": [folder],
                "game_list": {},
                "game_times": {},
                "game_total_times": {}
            }
        else:
            # Asegurarse de que 'platform_folders' exista
            platform_data = datafiles.config[platform_name]
            if "platform_folders" not in platform_data:
                platform_data["platform_folders"] = []
            if folder not in platform_data["platform_folders"]:
                platform_data["platform_folders"].append(folder)

        self.scan_for_games(platform_name)
        return folder

    def is_executable(self, path):
        """Devuelve True si el archivo es ejecutable en este SO"""
        if sys.platform.startswith("win"):
            return os.path.splitext(path)[1].lower() in [".exe", ".bat", ".cmd", ".sh"]
        else:  # Linux / macOS
            return os.path.isfile(path) and os.access(path, os.X_OK)

    def scan_for_games(self, platform_name):
        ignore_keywords = ["vc_redist", "unins", "setup", "install", "dxsetup", "dotnet", "readme", "helper", "support", "launcher", "Launcher", "Win64"]

        for path in datafiles.config[platform_name]["platform_folders"]:
            for root, _, files in os.walk(path):
                for file in files:
                    full_path = os.path.join(root, file)
                    if not self.is_executable(full_path):
                        continue
                    if any(keyword in file.lower() for keyword in ignore_keywords):
                        continue
                    datafiles.config[platform_name]["game_list"][os.path.splitext(file)[0]] = full_path

        self.save_config()

    def sort_key(self, game_name, game_times):
        sessions = game_times.get(game_name, [])
        if sessions:
            try:
                last_played = datetime.strptime(sessions[-1]["Start"], "%Y-%m-%d %H:%M:%S")
                return (0, -last_played.timestamp())
            except ValueError:
                return (0, float('-inf'))
        return (1, game_name.lower())    

    def remove_game_icon(self, game_path):
        if not game_path:
            return

        icon_name = os.path.basename(game_path) + ".ico"  # Ej: "game.exe.ico"
        icon_path = os.path.join("icons_cache", icon_name)
        if os.path.exists(icon_path):
            os.remove(icon_path)
            
    @staticmethod
    def load_config():
        with datafiles.config_lock:
            with open(datafiles.CONFIG_FILE, "r") as f:
                loaded = json.load(f)
            datafiles.config.clear()
            datafiles.config.update(loaded)

    @staticmethod
    def save_config():
        with datafiles.config_lock:
            with open(datafiles.CONFIG_FILE, "w") as f:
                json.dump(datafiles.config, f, indent=4)

class GameLauncherController:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GameLauncherController, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.launched = False
        self.already_saved = {}
        self.lock = threading.Lock()

# Helpers de ejecución
    def _run_windows(self, game_path):
        """Ejecuta un juego en Windows."""
        return subprocess.Popen(game_path)

    def _run_linux_native(self, game_path):
        """Ejecuta un juego nativo en Linux."""
        return subprocess.Popen([game_path])

    def _run_linux_wine(self, game_path, wineprefix=None):
        """Ejecuta un juego de Windows en Linux con Wine."""
        env = os.environ.copy()
        if wineprefix:
            env["WINEPREFIX"] = wineprefix
        else:
            # Si no hay configurado, usamos el default de Wine (~/.wine)
            env["WINEPREFIX"] = os.path.expanduser("~/.wine")

        return subprocess.Popen(["wine", game_path], env=env)

    def _needs_wine(self, game_path):
        """Devuelve True si el juego requiere Wine (por extensión)."""
        ext = os.path.splitext(game_path)[1].lower()
        return ext in [".exe", ".bat", ".cmd"]

    def _run_game(self, game_path):
        """Decide cómo ejecutar el juego según el SO."""
        if sys.platform.startswith("win"):
            return self._run_windows(game_path)

        elif sys.platform.startswith("linux"):
            if self._needs_wine(game_path):
                wineprefix = datafiles.config["global"].get(
                    "wineprefix", os.path.expanduser("~/.wine")
                )
                return self._run_linux_wine(game_path, wineprefix)
            else:
                return self._run_linux_native(game_path)

        else:
            raise NotImplementedError(f"SO no soportado: {sys.platform}")

# Lógica principal
    def launch_game(self, platform_name, game_name, game_path, on_game_end=None):
        def execute():
            with self.lock:
                allow_multiple = datafiles.config["global"].get("allow_multiple_games", False)
                if not allow_multiple and self.launched:
                    logging.info("Ya hay un juego en ejecución, no se puede iniciar otro.")
                    return
                self.launched = True

            clean_orphaned_sessions()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_time = time.time()
            start_dt = datetime.now()

            # 🔹 Aquí usamos la capa modular
            process = self._run_game(game_path)
            pid = process.pid

            # Guardar datos iniciales
            with self.lock:
                datafiles.config["global"].setdefault("actual_sessions", {})[game_name] = {
                    "pid": pid,
                    "start_time": start_dt.isoformat(),
                }
                datafiles.config["global"].setdefault("actual_running", {})[game_name] = {"pid": pid}
                self.save_config()

            with open(datafiles.FLAG_FILE, "w") as f:
                f.write("1")

            # ---------------------------
            # Periodic saver + finalización
            # ---------------------------
            running = True
            def periodic_saver():
                while running:
                    time.sleep(300)
                    if not running:
                        break
                    if datafiles.config["global"]["cloud_sync_enabled"]:
                        call_upload()
                    self._save_playtime(platform_name, game_name, start_time, now)

            save_thread = threading.Thread(target=periodic_saver, daemon=True)
            save_thread.start()

            try:
                process.wait()
            finally:
                with self.lock:
                    running = False
                    datafiles.config["global"]["actual_running"].pop(game_name, None)
                    datafiles.config["global"]["actual_sessions"].pop(game_name, None)
                    self._finalize_playtime(platform_name, game_name, start_time, now)
                    self.launched = False
                    if on_game_end:
                        on_game_end()

        thread = threading.Thread(target=execute)
        thread.start()

# Helpers de guardado de tiempos
    def _save_playtime(self, platform_name, game_name, start_time, now):
        dur_min = (time.time() - start_time) / 60
        with self.lock:
            game_times = datafiles.config[platform_name].setdefault("game_times", {})
            game_times.setdefault(game_name, [])

            if game_times[game_name] and game_times[game_name][-1]["Start"] == now:
                game_times[game_name][-1]["Tiempo"] = round(dur_min, 2)
            else:
                game_times[game_name].append({"Start": now, "Tiempo": round(dur_min, 2)})

            game_times[game_name] = game_times[game_name][-5:]

            pcid = get_machine_id()
            game_total_times = datafiles.config[platform_name].setdefault("game_total_times", {}).setdefault(game_name, {})
            total = game_total_times.setdefault(pcid, 0.0)
            game_total_times[pcid] = total + 5
            self.already_saved[game_name] = True
            self.save_config()

    def _finalize_playtime(self, platform_name, game_name, start_time, now):
        pcid = get_machine_id()
        dur_min = (time.time() - start_time) / 60
        
        game_total_times = datafiles.config[platform_name].setdefault("game_total_times", {}).setdefault(game_name, {})
        total= game_total_times.setdefault(pcid, 0.0)
        
        times = datafiles.config[platform_name].setdefault("game_times", {})
        times.setdefault(game_name, [])

        if self.already_saved.get(game_name, False):
            dif = dur_min - times[game_name][-1]["Tiempo"]
            if dif > 0:
                game_total_times[pcid] = total + round(dif, 2)
        else:
            game_total_times[pcid] = total + round(dur_min, 2)

        
        if times[game_name] and times[game_name][-1]["Start"] == now:
            times[game_name][-1]["Tiempo"] = round(dur_min, 2)
        else:
            times[game_name].append({"Start": now, "Tiempo": round(dur_min, 2)})

        times[game_name] = times[game_name][-5:]
        self.already_saved.pop(game_name, None)
        self.save_config()
        if datafiles.config["global"]["cloud_sync_enabled"]:
            time.sleep(2)
            call_upload()

    def save_config(self):
        Loader.save_config()

def safe_askdirectory():
    try:
        folder = filedialog.askdirectory()
        return folder
    except KeyError as e:
        if "__tk_choosedir" in str(e):
            print("⚠️ El diálogo nativo de directorios no está disponible, usando alternativa.")
            folder = filedialog.askopenfilename(mustexist=True, title="Seleccione una carpeta")
            if folder:
                import os
                return os.path.dirname(folder)
            return None
        else:
            raise

def clean_orphaned_sessions():
    actual_running = datafiles.config["global"].get("actual_running", {})
    to_remove = []

    # Si hay algo registrado como corriendo, verificar si realmente lo está
    for game_name, info in actual_running.items():
        pid = info.get("pid")
        if not is_process_running(pid):
            to_remove.append(game_name)

    for game_name in to_remove:
        datafiles.config["global"]["actual_sessions"].pop(game_name, None)
        actual_running.pop(game_name, None)

    # Si actual_running quedó vacío, borrar actual_sessions completamente
    if not actual_running:
        datafiles.config["global"].pop("actual_sessions", None)

    if to_remove or not actual_running:
        datafiles.config["global"].setdefault("actual_sessions", {})
        datafiles.config["global"].setdefault("actual_running", {})
        Loader.save_config()

def is_process_running(pid):
    try:
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except Exception:
        return False

def extract_icon(path): 
    return get_app_icon(path)

def reload_in_thread(self, on_callback):
    def worker():
        all_data = []
        for platform_name in datafiles.config.get("global", {}).get("tab_order", []):
            if platform_name in datafiles.config:
                all_data.append(collect_platform_data(platform_name))
                                
        # ya tenemos todo, ahora actualizar UI en mainloop
        self.root.after(0, lambda: on_callback(all_data))

    threading.Thread(target=worker, daemon=True).start()

def collect_platform_data(platform_name):
    grouped = True
    default_icon= load_icon(os.path.join(datafiles.ICONS, "no_icon.ico"), size=(16,16))
    """Prepara datos de una plataforma (sin tocar widgets)."""
    result = {
        "platform": platform_name,
        "games": [],
        "grouped": [],
        "favorites": [],
        "recent": [],
        "by_month": {}
    }
    loader = Loader()
    game_list = datafiles.config[platform_name]["game_list"]
    game_times = datafiles.config[platform_name].get("game_times", {})
    favorites = datafiles.config[platform_name].get("favorites", [])

    if grouped:
        for name, path in sorted(game_list.items(), key=lambda item: loader.sort_key(item[0], game_times)):
            game_info = {"name": name, "path": path, "icon": extract_icon(path) or default_icon}
            result["grouped"].append(game_info)
    return result
                
    """for name, path in game_list.items():
        game_info = {"name": name, "path": path, "icon": extract_icon(path) or default_icon}
        if name in favorites:
            result["favorites"].append(game_info)
        elif (times := game_times.get(name)):
            try:
                last_played = datetime.strptime(times[-1]["Start"], "%Y-%m-%d %H:%M:%S")
                key = last_played.strftime("%Y-%m")
                result["by_month"].setdefault(key, []).append(game_info)
            except ValueError:
                result["recent"].append(game_info)
        else:
            result["recent"].append(game_info)"""
            

