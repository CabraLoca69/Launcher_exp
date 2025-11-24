import os
import logging
import subprocess
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
from icon_utils import get_app_icon, load_icon
from datafiles import ICONS, db

class Loader:
    def __init__(self):
        self.default_icon= load_icon(os.path.join(ICONS, "no_icon.ico"), size=(16,16))
        self.grouped = True
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

    def is_executable(self, path):
        """Devuelve True si el archivo es ejecutable en este SO"""
        if sys.platform.startswith("win"):
            return os.path.splitext(path)[1].lower() in [".exe", ".bat", ".cmd", ".sh"]
        else:  # Linux / macOS
            return os.path.isfile(path) and os.access(path, os.X_OK)

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

                    if not self.is_executable(full_path):
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

        GameLauncherController._initalized = True
        

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
                wineprefix = db.get("global.wineprefix", os.path.expanduser("~/.wine"))
                return self._run_linux_wine(game_path, wineprefix)
            else:
                return self._run_linux_native(game_path)

        else:
            raise NotImplementedError(f"SO no soportado: {sys.platform}")

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
            start_dt = datetime.now()

            # 🔹 Aquí usamos la capa modular
            process = self._run_game(game_path)
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
                while running:
                    time.sleep(300)
                    if not running:
                        break

                    self._save_playtime(platform_name, game_name, start_time, now)

            safe_thread(periodic_saver)

            try:
                process.wait()
            finally:
                with self.lock:
                    running = False
                    db.delete(f"global.actual_running.{game_name}")
                    db.delete(f"global.actual_sessions.{game_name}")
                    self._finalize_playtime(platform_name, game_name, start_time, now)                    
                    
        if db.get(f"global.actual_running.{game_name}") is None:
            safe_thread(execute, daemon= False)

# Helpers de guardado de tiempos
    def _save_playtime(self, platform_name, game_name, start_time, now):
        dur_min = (time.time() - start_time) / 60
        pcid = get_machine_id()

        with db.lock:
            # --- GAME TIMES (sessions)
            sessions_list = db.get(f"{platform_name}.game_times.{game_name}", default= [])

            if sessions_list and sessions_list[-1]["Start"] == now:
                sessions_list[-1]["Tiempo"] = round(dur_min, 2)
            else:
                sessions_list.append({"Start": now, "Tiempo": round(dur_min, 2)})

            # Solo los últimos 5
            sessions_list = sessions_list[-5:]

            # Guardar como claves child
            base = f"{platform_name}.game_times.{game_name}"
            for idx, sess in enumerate(sessions_list):
                db.set(f"{base}.{idx}", sess)

            # --- TOTAL TIMES POR PC
            current_total = db.get(f"{platform_name}.game_total_times.{game_name}.{pcid}", 0.0)

            new_total = round(current_total + dur_min, 2)
            db.set(f"{platform_name}.game_total_times.{game_name}.{pcid}", new_total)

        self.already_saved[game_name] = True

    if db.get("global.cloud_sync_enabled", default=False):
        time.sleep(2)
        call_upload()

    def _finalize_playtime(self, platform_name, game_name, start_time, now):
        dur_min = (time.time() - start_time) / 60
        pcid = get_machine_id()

        with db.lock:
            base = f"{platform_name}.game_times.{game_name}"

            # Sessions
            sessions_list = db.get(base, default= [])
            current_total = db.get(f"{platform_name}.game_total_times.{game_name}.{pcid}", 0.0)

            # Ajuste según si hubo guardado previo
            if self.already_saved.get(game_name, False):
                last_time = sessions_list[-1]["Tiempo"] if sessions_list else 0
                diff = dur_min - last_time
                if diff > 0:
                    current_total += diff
            else:
                current_total += dur_min

            # Guardar totales
            db.set(f"{platform_name}.game_total_times.{game_name}.{pcid}", round(current_total, 2))

            # Actualizar sesión final
            if sessions_list and sessions_list[-1]["Start"] == now:
                sessions_list[-1]["Tiempo"] = round(dur_min, 2)
            else:
                sessions_list.append({"Start": now, "Tiempo": round(dur_min, 2)})

            sessions_list = sessions_list[-5:]
            db.set(base,sessions_list)
            db.ensure(f"global.update_ui.{platform_name}", game_name)

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

    # Filtrar solo los que sigan vivos
    alive_running = {}
    alive_sessions = {}

    for game_name, info in actual_running.items():
        pid = info.get("pid")
        if is_process_running(pid):
            alive_running[game_name] = info
            if game_name in actual_sessions:
                alive_sessions[game_name] = actual_sessions[game_name]

    # Reemplazar ramas completas de una sola vez
    db.set("global.actual_running", alive_running)
    db.set("global.actual_sessions", alive_sessions)

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
        for name, path in sorted(game_list.items(), key=lambda item: loader.sort_key(item[0], game_times)):
            game_info = {"name": name, "path": path, "icon": get_app_icon(path) or default_icon}
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
            

