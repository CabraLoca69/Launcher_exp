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
        
        # Asegura que exista la estructura base de la plataforma
        datafiles.db.ensure(platform_name, {
                    "platform_folders": [],
                    "game_list": {},
                    "favorites": [],
                    "game_times": {},
                    "game_total_times": {}
                })
        # Ahora agregamos la carpeta si no está
        folders = datafiles.db.get([platform_name, "platform_folders"])
        if folder not in folders:
            folders.append(folder)
            datafiles.db.set([platform_name, "platform_folders"], folders)

        self.scan_for_games(platform_name)
        return folder

    def is_executable(self, path):
        """Devuelve True si el archivo es ejecutable en este SO"""
        if sys.platform.startswith("win"):
            return os.path.splitext(path)[1].lower() in [".exe", ".bat", ".cmd", ".sh"]
        else:  # Linux / macOS
            return os.path.isfile(path) and os.access(path, os.X_OK)

    def scan_for_games(self, platform_name):
        ignore_keywords = [kw.lower() for kw in["vc_redist", "unins", "setup", "install", "dxsetup", "dotnet", "readme", "helper", "support", "launcher", "Launcher", "Win64"]]

        for path in datafiles.db.get([platform_name, "platform_folders"]):
            for root, _, files in os.walk(path):
                for file in files:
                    full_path = os.path.join(root, file)
                    if not self.is_executable(full_path):
                        continue
                    if any(keyword in file.lower() for keyword in ignore_keywords):
                        continue
                    key = os.path.splitext(file)[0]
                    datafiles.db.set([platform_name, "game_list", key], full_path)
        
        

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
    def launch_game(self, game_name, on_game_end=None):
        def resolve_game(game_name):
            with datafiles.db.lock:
                for platform, data in datafiles.db.data.items():
                    if platform == "global":
                        continue
                    if game_name in data.get("game_list", {}):
                        return platform, data["game_list"][game_name]
                raise ValueError(f"Juego '{game_name}' no encontrado")
        
        def execute():
            with self.lock:
                allow_multiple = datafiles.db.get("global.allow_multiple_games") or False
                if not allow_multiple and self.launched:
                    logging.info("Ya hay un juego en ejecución, no se puede iniciar otro.")
                    return
                self.launched = True

            clean_orphaned_sessions()
            platform_name, game_path = resolve_game(game_name)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_time = time.time()
            start_dt = datetime.now()

            # 🔹 Aquí usamos la capa modular
            process = self._run_game(game_path)
            pid = process.pid

            # Guardar datos iniciales
            with self.lock:
                datafiles.db.set(["global","actual_sessions", game_name],{
                    "pid": pid,
                    "start_time": start_dt.isoformat(),
                }) 
                datafiles.db.set(["global","actual_running", game_name], {"pid": pid})

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
                    if datafiles.db.get("global","cloud_sync_enabled"):
                        call_upload()
                    self._save_playtime(platform_name, game_name, start_time, now)

            save_thread = threading.Thread(target=periodic_saver, daemon=True)
            save_thread.start()

            try:
                process.wait()
            finally:
                with self.lock:
                    running = False
                    datafiles.db.delete(["global", "actual_running", game_name])
                    datafiles.db.delete(["global", "actual_sessions", game_name])
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
            game_times = datafiles.db.get([platform_name, "game_times", game_name], default=[])

            if game_times and game_times[-1]["Start"] == now:
                game_times[-1]["Tiempo"] = round(dur_min, 2)
            else:
                game_times.append({"Start": now, "Tiempo": round(dur_min, 2)})

            game_times = game_times[game_name][-5:]

            pcid = get_machine_id()
            total_times = datafiles.db.get([platform_name, "game_total_times", game_name], default={})
            if pcid not in total_times:
                total_times[pcid] = 0

            total_times[pcid] += round(dur_min, 2)
            datafiles.db.set([platform_name, "game_total_times", game_name], total_times)
            
            self.already_saved[game_name] = True

    def _finalize_playtime(self, platform_name, game_name, start_time, now):
        pcid = get_machine_id()
        dur_min = (time.time() - start_time) / 60
        
        total_times = datafiles.db.get([platform_name, "game_total_times", game_name], default={})
        total_for_pcid = total_times.get(pcid, 0.0)
        
        game_times = datafiles.db.get([platform_name, "game_times", game_name], default=[])

        if self.already_saved.get(game_name, False):
            last_time = game_times[-1]["Tiempo"] if game_times else 0
            diff = dur_min - last_time
            if diff > 0:
                total_times[pcid] = round(total_for_pcid + diff, 2)
        else:
            total_times[pcid] = round(total_for_pcid + dur_min, 2)
        
        datafiles.db.set([platform_name, "game_total_times", game_name], total_times)

        if game_times and game_times[-1]["Start"] == now:
            game_times[-1]["Tiempo"] = round(dur_min, 2)
        else:
            game_times.append({"Start": now, "Tiempo": round(dur_min, 2)})

        game_times = game_times[-5:]
        datafiles.db.set([platform_name, "game_times", game_name], game_times)
        self.already_saved.pop(game_name, None)
        if datafiles.db.get("global.cloud_sync_enabled", default=False):
            time.sleep(2)
            call_upload()

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
    actual_running = datafiles.db.get("global.actual_running", default={})
    to_remove = []

    for game_name, info in actual_running.items():
        pid = info.get("pid")
        if not is_process_running(pid):
            to_remove.append(game_name)

    for game_name in to_remove:
        datafiles.db.delete(f"global.actual_sessions.{game_name}")
        datafiles.db.delete(f"global.actual_running.{game_name}")

    # Si actual_running quedó vacío → borrar toda la rama
    if not datafiles.db.get("global.actual_running", {}):
        datafiles.db.delete("global.actual_running")

    # Si actual_sessions quedó vacío → borrar toda la rama
    if not datafiles.db.get("global.actual_sessions", {}):
        datafiles.db.delete("global.actual_sessions")

    datafiles.db.ensure("global.actual_running", {})
    datafiles.db.ensure("global.actual_sessions", {})

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

        tab_order = datafiles.db.get("global.tab_order", [])        

        for platform_name in tab_order:
            if datafiles.db.get(platform_name, None) is not None:
                all_data.append(collect_platform_data(platform_name))

        self.root.after(0, lambda: on_callback(all_data))

    threading.Thread(target=worker, daemon=True).start()

def collect_platform_data(platform_name):
    grouped = True
    default_icon = load_icon(os.path.join(datafiles.ICONS, "no_icon.ico"), size=(16,16))

    result = {
        "platform": platform_name,
        "games": [],
        "grouped": [],
        "favorites": [],
        "recent": [],
        "by_month": {}
    }

    loader = Loader()

    game_list   = datafiles.db.get([platform_name, "game_list"], {})
    game_times  = datafiles.db.get([platform_name, "game_times"], {})
    favorites   = datafiles.db.get([platform_name, "favorites"], [])

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
            

