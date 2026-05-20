import os
import logging
import threading
import psutil
import time
import sys
import json
from safe_threading import safe_thread
from datetime import datetime
from tkinter import filedialog
from machine_id import get_machine_id
from cloudsync import call_upload
from icon_utils import load_icon, IconUIAdapter
from datafiles import ICONS, db
from platform_adapters.registry import CURRENT_OS, PLATFORM_METHODS

class Loader:
    def __init__(self):
        self.default_icon= load_icon(os.path.join(ICONS, "no_icon.ico"), size=(16,16))
        self.grouped = True
        #este revisa que tipo de ejecutable tenemos
        self.executable_detector = PLATFORM_METHODS[CURRENT_OS]["exedetect"]()
        pass
    
    def add_folder(self, platform_name):  # agrega un directorio a la lista 
        folder = safe_askdirectory()
        
        # Asegura que exista la estructura base de la plataforma
        db.ensure(f"{platform_name}.platform_folders", [])
        db.ensure(f"{platform_name}.favorites", [])
        
        # Ahora agregamos la carpeta si no está
        folders = db.get(f"{platform_name}.platform_folders")
        if folder not in folders:
            folders.append(folder)
            db.set(f"{platform_name}.platform_folders", folders)

        self.scan_for_games(platform_name)
        return folder

    def scan_for_games(self, platform_name):
        ignore_keywords = [
            kw.lower() for kw in [
                "vc_redist", "unins", "setup", "install", "dxsetup",
                "dotnet", "readme", "helper", "support", "launcher", "win64"
            ]
        ]

        folders = db.get(f"{platform_name}.platform_folders", [])

        for path in folders:
            if not os.path.isdir(path):
                continue

            for root, _, files in os.walk(path):
                for file in files:
                    full_path = os.path.join(root, file)

                    if not self.executable_detector.is_executable(full_path):
                        continue

                    if any(k in file.lower() for k in ignore_keywords):
                        continue

                    key = os.path.splitext(file)[0]
                    db.set(f"{platform_name}.game_list.{key}", full_path)
        
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
    _initalized = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            clean_orphaned_sessions()
            cls._instance = super(GameLauncherController, cls).__new__(cls, *args, **kwargs)
            
        return cls._instance

    def __init__(self):
        if GameLauncherController._initalized:
            return
        
        self.already_saved = {}
        self.lock = threading.Lock()
        self.ui_registry = {}
        self.update_thread_running = False
        #agrego el runner que se encarga de lanzar los programas
        self.runner = PLATFORM_METHODS[CURRENT_OS]["runner"]()

        GameLauncherController._initalized = True
        
# Lógica principal
    def launch_game(self, game_name):
        def resolve_game(game_name):
            search = f"%.game_list.{game_name}"
    
            with db.lock:
                cur = db.conn.cursor()
                cur.execute("SELECT key, value FROM config WHERE key LIKE ?", (search,))
                row = cur.fetchone()

            if not row:
                raise ValueError(f"Juego '{game_name}' no encontrado")

            key, value_json = row

            platform = key.split(".")[0]

            game_data = json.loads(value_json)

            return platform, game_data
        
        def execute():
            with self.lock:
                allow_multiple = db.get("global.allow_multiple_games") or False
                if not allow_multiple:
                    logging.info("Ya hay un juego en ejecución, no se puede iniciar otro.")
                    return

            platform_name, game_path = resolve_game(game_name)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_time = time.time()
            last_update_time = start_time
            start_dt = datetime.now()

            # Uso el runner para lanzar el juego (retorna el proceso)
            process = self.runner.run(game_path)
            pid = process.pid

            # Guardar datos iniciales
            db.set(f"global.actual_sessions.{game_name}",{"pid": pid,"start_time": start_dt.isoformat(),}) 
            db.set(f"global.actual_running.{game_name}", {"pid": pid})
            
            db.set("global.update_timestamp", time.time())

            # ---------------------------
            # Periodic saver + finalización
            # ---------------------------
            running = True
            def periodic_saver():
                nonlocal running
                nonlocal last_update_time
                while running:
                    time.sleep(60)
                    if not running:
                        if db.get("global.cloud_sync_enabled", default=False):
                            call_upload()
                        break
                    if db.get("global.cloud_sync_enabled", default=False):
                        call_upload()
                    last_update_time = self._save_playtime(platform_name, game_name, start_time, last_update_time, now)

            safe_thread(periodic_saver)

            try:
                if psutil.pid_exists(pid):
                    try:
                        psutil.Process(pid).wait()
                    except Exception as e:
                        print(f"Erro al esperar el proceso {pid} {e}")
            finally:
                with self.lock:
                    running = False
                    db.delete(f"global.actual_running.{game_name}")
                    db.delete(f"global.actual_sessions.{game_name}")
                    self._finalize_playtime(platform_name, game_name, start_time, last_update_time, now)                    
                    
        if db.get(f"global.actual_running.{game_name}") is None:
            safe_thread(execute, daemon= False)

# Helpers de guardado de tiempos
    def _save_playtime(self, platform_name, game_name, start_time, last_update_time, now):
        pcid = get_machine_id()
        current_time = time.time()

        # Diferencia exacta en minutos desde la última actualización
        diff = (current_time - last_update_time) / 60  

        if diff <= 0:
            return last_update_time  # No sumes nada raro

        with db.lock:
            # --- ACTUALIZAR TOTAL POR PC ---
            base_total = f"{platform_name}.game_total_times.{game_name}.{pcid}"
            current_total = db.get(base_total, 0.0)
            new_total = round(current_total + diff, 2)
            db.set(base_total, new_total)

            # --- ACTUALIZAR SESSIONS (UI) ---
            base = f"{platform_name}.game_times.{game_name}"

            sessions_list = db.get(base, default=[])
            dur_min = (current_time - start_time) / 60  # tiempo total de la sesion

            if sessions_list and sessions_list[-1]["Start"] == now:
                sessions_list[-1]["Tiempo"] = round(dur_min, 2)
            else:
                sessions_list.append({"Start": now, "Tiempo": round(dur_min, 2)})

            sessions_list = sessions_list[-5:]
            db.set(base, sessions_list)

        self.already_saved[game_name] = True

        return current_time

    def _finalize_playtime(self, platform_name, game_name, start_time, last_update_time, now):
        pcid = get_machine_id()
        end_time = time.time()

        # Minutos finales desde el último save
        diff = (end_time - last_update_time) / 60

        with db.lock:
            base_total = f"{platform_name}.game_total_times.{game_name}.{pcid}"
            current_total = db.get(base_total, 0.0)

            if diff > 0:
                current_total += diff

            db.set(base_total, round(current_total, 2))

            # --- Sessions UI ---
            base = f"{platform_name}.game_times.{game_name}"
            sessions_list = db.get(base, default=[])

            dur_min = (end_time - start_time) / 60

            if sessions_list and sessions_list[-1]["Start"] == now:
                sessions_list[-1]["Tiempo"] = round(dur_min, 2)
            else:
                sessions_list.append({"Start": now, "Tiempo": round(dur_min, 2)})

            sessions_list = sessions_list[-5:]
            db.set(base, sessions_list)

            db.set(f"global.update_ui.{platform_name}", game_name)

        self.already_saved.pop(game_name, None)

        if db.get("global.cloud_sync_enabled", default=False):
            time.sleep(2)
            call_upload()

    def update_watcher(self):
        while True:
            time.sleep(2)

            for platform_name, ui in list(self.ui_registry.items()):
                game_name = db.get(f"global.update_ui.{platform_name}")
                if not game_name:
                    continue

                db.delete(f"global.update_ui.{platform_name}")

                try:
                    ui.update_on_close(game_name, platform_name)
                except Exception as e:
                    logging.error(f"Error updating UI for {platform_name}: {e}")

    def register_ui(self, platform, ui_instance):
        self.ui_registry[platform] = ui_instance
        if not self.update_thread_running:
            self.update_thread_running = True
            safe_thread(self.update_watcher)

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
    actual_running = db.get_children("global.actual_running") or {}
    actual_sessions = db.get_children("global.actual_sessions") or {}

    alive_running = {}
    alive_sessions = {}

    for game_name, info in actual_running.items():
        pid = info.get("pid")
        if is_process_running(pid):
            alive_running[game_name] = info
            if game_name in actual_sessions:
                alive_sessions[game_name] = actual_sessions[game_name]

    # Primero borrar todas las claves viejas
    db.delete_prefix("global.actual_running")
    db.delete_prefix("global.actual_sessions")

    # Volver a crear las ramas desde cero
    for game_name, info in alive_sessions.items():
        db.set(f"global.actual_sessions.{game_name}", info)

    for game_name, info in alive_running.items():
        db.set(f"global.actual_running.{game_name}", info)

def is_process_running(pid):
    try:
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except Exception:
        return False

def reload_in_thread(self, on_callback):
    def worker():
        all_data = []

        tab_order = db.get("global.tab_order", [])        

        for platform_name in tab_order:
            all_data.append(collect_platform_data(platform_name))

        self.root.after(0, lambda: on_callback(all_data))

    safe_thread(worker)

def collect_platform_data(platform_name):
    grouped = True
    default_icon = load_icon(os.path.join(ICONS, "no_icon.ico"), size=(16,16))

    result = {
        "platform": platform_name,
        "games": [],
        "grouped": [],
        "favorites": [],
        "recent": [],
        "by_month": {}
    }

    loader = Loader()

    game_list   = db.get_children(f"{platform_name}.game_list")
    game_times  = db.get_children(f"{platform_name}.game_times")
    favorites   = db.get_children(f"{platform_name}.favorites")

    if grouped:
        icons = PLATFORM_METHODS[CURRENT_OS]["icons"]()
        icons = IconUIAdapter(icons)
        for name, path in sorted(game_list.items(), key=lambda item: loader.sort_key(item[0], game_times)):
            game_info = {"name": name, "path": path, "icon": icons.get_icon(path) or default_icon}
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
            

