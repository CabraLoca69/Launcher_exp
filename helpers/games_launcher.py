import threading      
import psutil        
import logging       
import json          
import time        
from datetime import datetime  

#-------- imports internos -------
from data_access.cloudsync import call_upload
from data_access.datafiles import db
from data_access.machine_id import get_machine_id

from helpers.safe_threading import safe_thread

from interface_files.ui_handler import get_event_bus

from platform_adapters.platform_handler import PlatformHandler

class GameLauncherController:
    _instance = None
    _initialized = False
    _new_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._new_lock:
                if not cls._instance:  # doble check adentro del lock
                    SessionsCleaner().clean_orphaned_sessions()
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if GameLauncherController._initialized:
            return
        
        self.already_saved = {}
        self.lock = threading.Lock()
        self.event_bus = get_event_bus()

        GameLauncherController._initialized = True
        
    # Lógica principal
    def launch_game(self, game_name):
        def execute():
            with self.lock:
                allow_multiple = db.get("global.allow_multiple_games") or False
                if not allow_multiple:
                    logging.info("Ya hay un juego en ejecución, no se puede iniciar otro.")
                    return

            platform_name, game_path = db.resolve_game(game_name)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_time = time.time()
            last_update_time = start_time
            start_dt = datetime.now()

            # Uso el runner para lanzar el juego (retorna el proceso)
            process = PlatformHandler().get("runner").run(game_path)
            pid = process.pid

            # Guardar datos iniciales
            db.set(f"global.actual_sessions.{game_name}",{"pid": pid,"start_time": start_dt.isoformat(),}) 
            db.set(f"global.actual_running.{game_name}", {"pid": pid})
            
            db.set("global.update_timestamp", time.time())

            self.event_bus.notify_game_started(platform_name, game_name)

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
                    self.event_bus.notify_game_closed(platform_name, game_name)
                    self._finalize_playtime(platform_name, game_name, start_time, last_update_time, now)                    
                    
        if db.get(f"global.actual_running.{game_name}") is None:
            safe_thread(execute, daemon= False)

    # Helpers de guardado de tiempos
    def _update_playtime_records(self, platform_name, game_name, pcid, diff, start_time, current_time, now):
        with db.lock:
            # --- ACTUALIZAR TOTAL POR PC ---
            base_total = f"{platform_name}.game_total_times.{game_name}.{pcid}"
            current_total = db.get(base_total, 0.0)
            if diff > 0:
                current_total += diff
            db.set(base_total, round(current_total, 2))

            # --- ACTUALIZAR SESSIONS (UI) ---
            base = f"{platform_name}.game_times.{game_name}"
            sessions_list = db.get(base, default=[])
            dur_min = (current_time - start_time) / 60  # tiempo total de la sesión

            if sessions_list and sessions_list[-1]["Start"] == now:
                sessions_list[-1]["Tiempo"] = round(dur_min, 2)
            else:
                sessions_list.append({"Start": now, "Tiempo": round(dur_min, 2)})

            sessions_list = sessions_list[-5:]
            db.set(base, sessions_list)


    def _save_playtime(self, platform_name, game_name, start_time, last_update_time, now):
        current_time = time.time()
        diff = (current_time - last_update_time) / 60  # minutos desde el último update

        if diff <= 0:
            return last_update_time  

        pcid = get_machine_id()
        self._update_playtime_records(platform_name, game_name, pcid, diff, start_time, current_time, now)

        self.already_saved[game_name] = True
        return current_time


    def _finalize_playtime(self, platform_name, game_name, start_time, last_update_time, now):
        end_time = time.time()
        diff = (end_time - last_update_time) / 60  # minutos desde el último save

        pcid = get_machine_id()
        self._update_playtime_records(platform_name, game_name, pcid, diff, start_time, end_time, now)

        self.event_bus.notify_game_closed(platform_name, game_name)
        self.already_saved.pop(game_name, None)

        if db.get("global.cloud_sync_enabled", default=False):
            time.sleep(2)
            call_upload()

    def register_ui(self, platform, ui_instance):
        self.event_bus.register_ui(platform, ui_instance)

    def force_close_game(self, platform_name, game_name):
        running_info = db.get(f"global.actual_running.{game_name}")
        if running_info:
            pid = running_info.get("pid")
            if pid and psutil.pid_exists(pid):
                try:
                    psutil.Process(pid).terminate()
                    logging.info(f"Juego '{game_name}' en plataforma '{platform_name}' cerrado forzosamente.")

                except psutil.NoSuchProcess:
                    logging.warning(f"El proceso {pid} ya no existía al intentar cerrarlo.")

                except Exception as e:
                    logging.error(f"Error al cerrar el juego '{game_name}': {e}")
            else:
                logging.warning(f"No se encontró un proceso activo para el juego '{game_name}'.")
        else:
            logging.warning(f"No hay información de ejecución para el juego '{game_name}'.")

class SessionsCleaner():
    def clean_orphaned_sessions(self):
        actual_running = db.get_children("global.actual_running") or {}
        actual_sessions = db.get_children("global.actual_sessions") or {}

        alive_running = {}
        alive_sessions = {}

        for game_name, info in actual_running.items():
            pid = info.get("pid")
            if self.is_process_running(pid):
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

    def is_process_running(self, pid):
        try:
            return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
        except Exception:
            return False