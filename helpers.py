import os
import json
import win32gui
import win32ui
import win32con
import logging
import subprocess
import threading
import psutil
import time
from datetime import datetime
from PIL import Image, ImageTk
from tkinter import filedialog
from datafiles import config, config_lock, CONFIG_FILE, FLAG_FILE, ICONS_CACHE_DIR, ICONS

class Loader:
    def __init__(self):
        self.img = Image.open(os.path.join(ICONS, f"no_icon.ico")).resize((16, 16), Image.LANCZOS)
        self.default_icon= ImageTk.PhotoImage(self.img)
        self.grouped = True
        pass
    
    def add_folder(self, platform_name): # agrega un directorio a la lista 
        folder = filedialog.askdirectory()
        if folder:            
            if platform_name not in config:
                config[f"{platform_name}"] = {}
                config[platform_name] = {"platform_folders" : [f"{folder}" ] , "game_list" : {} , "game_times" : {} , "game_total_times" : {}}
            else:
                if folder not in config[platform_name]["platform_folders"]:
                    config[platform_name]["platform_folders"].append(f"{folder}")
      
            self.scan_for_games(platform_name)
        
        return folder

    def scan_for_games(self, platform_name): # busca todos los ejecutables en el directorio que le llega y los agrega a la lista
        executable_extensions = [".exe", ".bat", ".sh"]
        ignore_keywords = ["vc_redist", "unins", "setup", "install", "dxsetup", "dotnet", "readme", "helper", "support", "launcher", "Launcher", "Win64"]
        for path in config[platform_name]["platform_folders"]:
            for root, _, files in os.walk(path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in executable_extensions):
                        if any(keyword in file.lower() for keyword in ignore_keywords):
                            continue    
                        config[platform_name]["game_list"][os.path.splitext(file)[0]] = os.path.join(root, file)
                        
        self.save_config()

    def update_game_list(self, platform_name, game_tree):
        def get_icon(path):
            icon = extract_icon(path) or self.default_icon
            return icon

        def insert_game(parent, name, icon):
            game_tree.icon_images[name] = icon
            base_name = os.path.splitext(name)[0]
            game_tree.insert(parent, "end", iid=name, text="", image=icon, values=(base_name,))

        game_tree.delete(*game_tree.get_children())
        game_tree.configure(columns=("name",))
        game_tree.column("#0", width=35, stretch=False)
        game_tree.column("name", anchor="w", width=200)
        game_tree.heading("name", text="Nombre del juego")

        game_list = config[platform_name]["game_list"]
        game_times = config[platform_name].get("game_times", {})
        favorites = config[platform_name].get("favorites", [])

        if not hasattr(game_tree, "icon_images"):
            game_tree.icon_images = {}

        if self.grouped:
            for name, path in sorted(game_list.items(), key=lambda item: self.sort_key(item[0], game_times)):
                icon = get_icon(path)
                insert_game("", name, icon)
        else:
            favorites_node = game_tree.insert("", "end", text="★ Favoritos", open=True)
            recent_node = game_tree.insert("", "end", text="⏱ Recientes", open=False)
            months_nodes = {}

            for name, path in game_list.items():
                icon = get_icon(path)
                last_played_str = ""

                if times := game_times.get(name):
                    try:
                        last_played = datetime.strptime(times[-1]["Start"], "%Y-%m-%d %H:%M:%S")
                        last_played_str = last_played.strftime("%Y-%m")
                    except ValueError:
                        pass

                if name in favorites:
                    insert_game(favorites_node, name, icon)
                elif last_played_str:
                    if last_played_str not in months_nodes:
                        months_nodes[last_played_str] = game_tree.insert("", "end", text=f"📆 {last_played_str}", open=False)
                    insert_game(months_nodes[last_played_str], name, icon)
                else:
                    insert_game(recent_node, name, icon)

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
        global config
        with config_lock:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)

    @staticmethod
    def save_config():
        global config
        with config_lock:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)

class GameLauncherController:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GameLauncherController, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.launched = False  # Indicador de si hay un juego lanzado
        self.lock = threading.Lock()  # Lock para sincronizar el acceso

    def launch_game(self, platform_name, game_name, game_path, on_game_end=None):
        def execute():
            with self.lock:
                allow_multiple = config["global"].get("allow_multiple_games", False)

                if not allow_multiple:
                    if self.launched:
                        logging.info("Ya hay un juego en ejecución, no se puede iniciar otro.")
                        return

                # Marcar que el juego está lanzado
                self.launched = True

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_time = time.time()
            start_dt = datetime.now()
            with open(FLAG_FILE, "w") as f:
                f.write("1")
            

            # Lanza el juego en un proceso nuevo
            process = subprocess.Popen(game_path)
                    
            pid = process.pid
            with self.lock:
                config["global"].setdefault("actual_sessions", {})[game_name] = {"pid": pid, "start_time": start_dt.isoformat()}
                config["global"].setdefault("actual_running", {})[game_name] = {"pid": pid}
                self.save_config()

            # Hilo de guardado periódico cada 5 minutos
            running = True
            

            def periodic_saver():
                while running:
                    time.sleep(300)  # 5 minutos
                    if not running:
                        break
                    
                    # Guardado periódico (cada 5 min aprox)
                    dur_min = (time.time() - start_time) / 60
                    
                    with self.lock:
                        game_times = config[platform_name].setdefault("game_times", {})
                        game_times.setdefault(game_name, [])

                        # Si hay al menos una sesión previa y la última tiene el mismo "Start"
                        if game_times[game_name] and game_times[game_name][-1]["Start"] == now:
                            game_times[game_name][-1]["Tiempo"] = round(dur_min, 2)
                        else:
                            # Solo para casos donde no se haya creado antes la sesión (primera vez)
                            game_times[game_name].append({"Start": now, "Tiempo": round(dur_min, 2)})

                        game_times[game_name] = game_times[game_name][-5:]  # mantener los últimos 5
                    
                        # También actualizamos el total aproximado (acumulado estimado)
                        game_total_times = config[platform_name].setdefault("game_total_times", {})
                        game_total_times.setdefault(game_name, 0.0)
                        game_total_times[game_name] += 5

                        self.save_config()

            save_thread = threading.Thread(target=periodic_saver, daemon=True)
            save_thread.start()
                    
            try:
                process.wait()
            finally:
                with self.lock:
                    running = False  # Detiene el guardado periódico
                    config["global"]["actual_running"].pop(game_name, None) #lo elimina de los procesos corriendo ("se cerro correctamente")
        
                    # Intentar eliminar la sesión activa
                    config["global"]["actual_sessions"].pop(game_name, None)

                    # Guardado final más preciso
                    dur_min = (time.time() - start_time) / 60
                    game_times = config[platform_name].setdefault("game_times", {})
                    game_times.setdefault(game_name, [])
                
                    # Si hay al menos una sesión previa y la última tiene el mismo "Start"
                    if game_times[game_name] and game_times[game_name][-1]["Start"] == now:
                        game_times[game_name][-1]["Tiempo"] = round(dur_min, 2)
                    else:
                        # Solo para casos donde no se haya creado antes la sesión (primera vez)
                        game_times.setdefault(game_name, []).append({"Start": now, "Tiempo": round(dur_min, 2)})
                
                    game_times[game_name] = game_times[game_name][-5:]

                    game_total_times = config[platform_name].setdefault("game_total_times", {})
                    game_total_times.setdefault(game_name, 0.0)
                    game_total_times[game_name] += round(dur_min, 2)
                
                    self.save_config()
                    #reseteamos el estado del launched al cerrar el juego
                    self.launched = False

                    if on_game_end:
                        on_game_end()

        # Ejecutamos la lógica de lanzamiento del juego en un hilo separado
        thread = threading.Thread(target=execute)
        thread.start()

    def save_config(self):
        Loader.save_config()

def clean_orphaned_sessions():
    actual_running = config["global"].get("actual_running", {})
    to_remove = []

    # Si hay algo registrado como corriendo, verificar si realmente lo está
    for game_name, info in actual_running.items():
        pid = info.get("pid")
        if not is_process_running(pid):
            to_remove.append(game_name)

    for game_name in to_remove:
        config["global"]["actual_sessions"].pop(game_name, None)
        actual_running.pop(game_name, None)

    # Si actual_running quedó vacío, borrar actual_sessions completamente
    if not actual_running:
        config["global"].pop("actual_sessions", None)

    if to_remove or not actual_running:
        config["global"].setdefault("actual_sessions", {})
        config["global"].setdefault("actual_running", {})
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

def is_process_running(pid):
    try:
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except Exception:
        return False

def extract_icon(path, size=(16, 16)): 
    try:
        ico_path = os.path.join(ICONS_CACHE_DIR, f"{os.path.basename(path)}.ico")
        
        if os.path.exists(ico_path):
            return ImageTk.PhotoImage(Image.open(ico_path).resize((16, 16), Image.LANCZOS))
        
        large, small = win32gui.ExtractIconEx(path, 0)
        if small:
            hicon = small[0]
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, 32, 32)
            hdc = hdc.CreateCompatibleDC()
            hdc.SelectObject(hbmp)
            win32gui.DrawIconEx(hdc.GetHandleOutput(), 0, 0, hicon, 32, 32, 0, None, win32con.DI_NORMAL)
            hbmp.SaveBitmapFile(hdc, ico_path)
            win32gui.DestroyIcon(hicon)

            return ImageTk.PhotoImage(Image.open(ico_path).resize((16, 16), Image.LANCZOS))
        
    except Exception as e:
        print("Error extrayendo ícono:", e)
    
    return None
