import os
import json
import sys
import tkinter as tk
import ttkbootstrap as tb
import tkinter.simpledialog as simpledialog
import subprocess
import time
import threading
import win32com.client
import win32ui
import win32gui
import win32con
import logging
import psutil
from tkinter import filedialog, messagebox, ttk, StringVar, Toplevel
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import datetime
from PIL import Image, ImageTk


BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

# Carpeta de datos 
DATA_DIR = os.path.join(BASE_DIR, "data")
ICONS_CACHE_DIR = os.path.join(DATA_DIR, "icons_cache")
ICONS = os.path.join(DATA_DIR, "icons")

# Crear carpetas si no existen
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ICONS_CACHE_DIR, exist_ok=True)

# Archivos
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
NOTES_FILE = os.path.join(DATA_DIR, "notas.json")
FLAG_FILE = os.path.join(DATA_DIR, "notify_update.flag")

# Lock global para operaciones con config
config_lock = threading.Lock()

# Cargar configuración
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = {}

if os.path.exists(NOTES_FILE):
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        notas = json.load(f)
else : 
    notas = {}

if "global" not in config:
    config.setdefault("global", {}).setdefault("allow_multiple_games", False)

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
    
class LauncherUI:
    def __init__(self):
        self.root = tb.Window(themename="darkly")
        self.root.title("Game Launcher")
        self.root.iconbitmap(os.path.join(ICONS, f"icon.ico"))
        self.root.geometry("900x600")
        self.root.minsize(600, 400)

        self.root.grid_rowconfigure(0, weight=1)  # Notebook se expande
        self.root.grid_columnconfigure(0, weight=1)
        
        # Notebook de plataformas
        self.notebook = DraggableNotebook(self.root)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        
        # Manager de sesiones 
        self.session_manager = SessionManager(self.root, self)

        if config:
            self.notebook.reload()
        
    def add_session(self, game_name, process, start_time):
        self.session_manager.add_session(game_name, process, start_time)

    def restore_sessions(self):
        sessions = config["global"].get("actual_sessions", {})
        for game_name, data in sessions.items():
            pid = data["pid"]
            start_time_str = data.get("start_time")
            start_time = datetime.fromisoformat(start_time_str) if start_time_str else datetime.now()
            try:
                process = psutil.Process(pid)
                if process.is_running():
                    self.add_session(game_name, process, start_time)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    
    def monitor_sessions(self):
        def loop():
            while True:
                if os.path.exists(FLAG_FILE):
                    try:
                        os.remove(FLAG_FILE)  # Se procesa una sola vez
                    
                        # Releer config.json desde disco
                        Loader.load_config()

                        # Actualizar visualmente
                        self.restore_sessions()
                    except Exception as e:
                        print(f"Error al manejar el archivo de aviso: {e}")
                time.sleep(5)
        threading.Thread(target=loop, daemon=True).start()

    def start(self):
        self.monitor_sessions()
        if not os.path.exists(FLAG_FILE):
            self.restore_sessions()
        self.root.mainloop()

class SessionManager:
    def __init__(self, parent, ui):
        self.parent = parent
        self.launcherui = ui
        self.frame = tb.Frame(parent)
        self.sessions = {}  # Diccionario para guardar info de sesiones activas

    def add_session(self, game_name, process, start_time = None):
        if process.pid in self.sessions:
            return  # Ya se está monitoreando esta sesión
        if start_time is None:
            start_time = datetime.now()
        if not self.sessions:
            self.show()
        
        session_frame = tb.Frame(self.frame, bootstyle="secondary", padding=10)
        session_frame.pack(fill="x", pady=5)

        top_frame = tb.Frame(session_frame)
        top_frame.pack(fill="x")

        # Nombre del juego
        name_label = tb.Label(
            top_frame,
            text=f"🎮 {game_name}",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
            bootstyle="light"
        )
        name_label.pack(side="left", padx=(0, 10))
        
        # Botón de cerrar ❌
        close_btn = tb.Button(
            top_frame,
            text="❌",
            bootstyle="danger-outline",
            width=3,
            command=lambda: self.force_close(process.pid)
        )
        close_btn.pack(side="right", padx=(10, 0))
        
        # Tiempo de sesión
        time_label = tb.Label(
            top_frame,
            text="🕒 0 min",
            font=("Segoe UI", 10),
            anchor="e",
            bootstyle="light"
        )
        time_label.pack(side="right")

        # Guardar los datos de la sesión
        self.sessions[process.pid] = {
            "frame": session_frame,
            "name_label": name_label,
            "time_label": time_label,
            "start_time": start_time,
            "process": process
        }

        self.update_session(process.pid, game_name)
        self.monitor_process(process.pid)

    def update_session(self, pid, game_name):
        session = self.sessions.get(pid, game_name)
        
        elapsed = datetime.now() - session["start_time"]
        minutes = elapsed.seconds // 60
        session["time_label"].configure(text=f"🕒 {minutes} min")

        # Actualizar de nuevo en 60 segundos
        session["frame"].after(60000, lambda: self.update_session(pid, game_name))
        
    def monitor_process(self, pid):
        session = self.sessions.get(pid)

        process = session["process"]
        if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
            # El proceso terminó, eliminar la sesión
            session["frame"].destroy()
            del self.sessions[pid]
            if not self.sessions:
                self.hide()
            return

        # Volver a chequear en 2 segundos
        session["frame"].after(2000, lambda: self.monitor_process(pid))         
    
    def force_close(self, pid):
        session = self.sessions.get(pid)
        if not session:
            return

        process = session["process"]
        try:
            process.terminate()  # Mata el proceso
        except Exception as e:
            print(f"Error cerrando proceso: {e}")

        session["frame"].destroy()
        del self.sessions[pid]

        if not self.sessions:
            self.hide()
        
    def show(self):
        self.frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 5))
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_rowconfigure(1, weight=0)

    def hide(self):
        self.frame.grid_remove()
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_rowconfigure(1, weight=0)

class DraggableNotebook(tb.Notebook):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._active = None
        self.active_popup= None
        self.input_open = False
        self.FAVORITE_LIMIT = 5
        self.platform_trees = {}
        self.loader = Loader()
        self.img = Image.open(os.path.join(ICONS, f"no_icon.ico")).resize((16, 16), Image.LANCZOS)
        self.default_icon= ImageTk.PhotoImage(self.img)     
                        
        # este frame se usa cuando no hay tabs (plataformas)
        self.empty_frame = tb.Frame(self)
        tb.Label(self.empty_frame, text="🚫 No hay plataformas configuradas", font=("Segoe UI", 12, "bold"), bootstyle="warning").pack(pady=10)
        tb.Button(self.empty_frame, text="🞧 Agregar plataforma", bootstyle="info-outline", width=25, command= self.ask_platform_name).pack()
                
        # los comandos de las pestañas
        self.bind('<ButtonPress-1>', self.on_button_press, True)
        self.bind('<ButtonRelease-1>', self.on_button_release)
        self.bind('<B1-Motion>', self.on_mouse_move)
        self.bind("<Button-3>", self.on_right_click)
        self.bind("<<NotebookTabChanged>>", self.on_tab_change)
                    
        if not self.tabs():
            self.pack_emptyframe()
         
    def on_button_press(self, event):
        try:
            self.menu_popup.destroy()
            self._active = self.index("@%d,%d" % (event.x, event.y))
            return 
        except:
            pass

    def on_button_release(self, event):
        if self._active is None:
            return
        try:
            index = self.index("@%d,%d" % (event.x, event.y))
            if index != self._active:
                self.insert(index, self._active)
        except:
            self.insert(self.index("end")-1, self._active)
        
        config.setdefault("global", {})["tab_order"] = [self.tab(i, "text") for i in range(self.index("end"))]
        self.save_config()
                                   
        self._active = None

    def on_mouse_move(self, event):
        pass  # Podés agregar una animación si querés
    
    def on_right_click(self, event):        
        try:
            self._active = self.index(f"@{event.x},{event.y}")
            self.select(self._active)  # Selecciona la pestaña si se hizo clic sobre una
            tab_text = self.tab(self._active, "text")
        except tk.TclError as e:
            if "expected integer but got" in str(e):
                tab_text = None
            else:
                print(f"Error obteniendo pestaña: {e}")
                tab_text = None

        self.show_menu(tab_text, event.x_root, event.y_root)

    def on_tab_change(self, event):
        try:     
            selected_tab_text = self.tab(self.select(), "text")
            config["global"]["last_selected_tab"]= selected_tab_text
            self.save_config()
        except:
            pass
            
    def save_config(self):
        Loader.save_config()

    def reload(self):
        for platform_name in config.get("global", {}).get("tab_order", []):
            if platform_name in config:
                self.add_platform(platform_name)
        
        last_tab_text = config["global"].get("last_selected_tab")
        if not last_tab_text:
            return
        
        for tab_id in self.tabs():
            if self.tab(tab_id, "text") == last_tab_text:
                self.select(tab_id)
                break

    def ask_platform_name(self):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        if not self.input_open:
            self.empty_frame.pack_forget()
            self.input_open = True
            self.input = InputDialog(self, prompt="Nombre de la Plataforma:", callback=self.new_platform, cancel_callback= self.pack_emptyframe).pack()
                
    def pack_emptyframe(self):
        self.input_open = False 
        if not self.tabs():
            self.empty_frame.pack(fill="both", expand=True)
               
    def new_platform(self, platform_name):
        self.input_open = False
        if platform_name: 
            folder = self.loader.add_folder(platform_name)
            if folder:
                self.add_platform(platform_name)
                config.setdefault("global", {})["tab_order"] = [self.tab(i, "text") for i in range(self.index("end"))]
                self.save_config()
 
    def add_platform(self, platform_name): # crea todo el notebook con las pestañas y listboxes necesarios para mostrar los juegos y directorios
        if platform_name:
            self.empty_frame.pack_forget()
            platform_frame = GamePlatformFrame(self, platform_name)
            self.add(platform_frame, text= platform_name)
            self.select(platform_frame)
            self.platform_trees[platform_name] = platform_frame.game_tree
            self.loader.update_game_list(platform_name, self.platform_trees[platform_name])

    def confirm_remove(self):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        ConfirmDialog(self, title="Eliminar plataforma", message= "Atencion, estas por elminar una plataforma", callback=self.remove_tab).place(relx=0.5, rely=0.5, anchor="center")
             
    def remove_tab(self, confirmed): # elimina una pestaña (plataforma) seleccionada de el notebook y tambien la borra de la lista junto con todo su contenido
        if self._active is not None:
            platform_name= self.tab(self._active, option="text")
            if confirmed:
                for game_name, game_path in config[platform_name].get("game_list", {}).items():
                    self.loader.remove_game_icon(game_path)
            
                index_to_select = self._active - 1 if self._active > 0 else 0
                self.remove_platform(platform_name)
                self.forget(self._active)
                tabs= self.tabs()
                if tabs:
                    self.select(index_to_select)
            self._active = None
        if len(self.tabs()) == 0:
            self.empty_frame.pack(fill="both", expand=True)
        
        config.setdefault("global", {})["tab_order"] = [self.tab(i, "text") for i in range(self.index("end"))]
        self.save_config()
    
    def remove_platform(self, platform_name): # trabaja en conjunto con remove_tab, esto es lo que borra la plataforma de la lista
        del config[platform_name]
        self.save_config()

    def show_menu(self, platform_name, x_root, y_root):
        self.menu_popup = CustomPopupMenu(self)
        
        if platform_name:  
            self.menu_popup.add_button("🞧 Agregar plataforma", 25, "success-outline", self.ask_platform_name)
            self.menu_popup.add_button("🗑 Eliminar plataforma", 25, "danger-outline", self.confirm_remove)
            self.menu_popup.add_button("⚙ Propiedades", 25, "info-outline", lambda: self.open_properties(self.tab(self._active, "text")))
        else:
            self.menu_popup.add_button("🞧 Agregar plataforma", 25, "success-outline", self.ask_platform_name)
        
        self.menu_popup.show(x_root, y_root)
  
    def open_properties(self, platform_name):
        self.menu_popup.destroy()
        def refresh_tree():
            self.loader.update_game_list(platform_name, self.platform_trees[platform_name])
            return
        
        def update_tab(new_name, pre_name):
            for tab_id in self.tabs():
                if self.tab(tab_id, "text") == pre_name:
                    self.tab(tab_id, text= new_name)

            self.platform_trees[new_name] = self.platform_trees.pop(pre_name, {})                            
            return

        self.properties_window = PropertiesWindow(self, platform_name, self.platform_trees[platform_name], on_update_callback= refresh_tree, on_update_tab=update_tab)
        self.properties_window.pack()        

class GamePlatformFrame(ttk.Frame):
    def __init__(self, master, platform_name, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.FAVORITE_LIMIT = 5
        self.platform_name = platform_name
        self.menu = False
        self.loader = Loader()
        self.img = Image.open(os.path.join(ICONS, f"no_icon.ico")).resize((16, 16), Image.LANCZOS)
        self.default_icon= ImageTk.PhotoImage(self.img)   
        
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(1, weight=1)
        
        # Campo de búsqueda arriba del árbol de juegos
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(self, textvariable=self.search_var)
        search_entry.grid(row=0, column=0, padx=(10, 5), pady=(10, 0), sticky="ew")
        
        search_frame = tb.Frame(self)
        search_frame.grid(row=0, column=0, padx=(10, 5), pady=(10, 0), sticky="ew")

        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True)

        btn_clear = tb.Button(search_frame, text="📂", bootstyle="secondary", command=lambda: self.update_game_list(self.platform_name, self.game_tree))
        #btn_clear.pack(side="right", padx=(5, 0))
                
        # Árbol de juegos a la izquierda
        self.game_tree = ttk.Treeview(self, show="tree", selectmode="browse", height=15)
        self.game_tree.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="nsw")       
        # armar la forma de los favoritos
        # separar por mes?
        # Panel de contenido a la derecha
        self.game_info_panel = tb.Frame(self, relief="ridge", padding=10)
        self.game_info_panel.grid(row=0, column=1, rowspan=2, padx=(5, 10), pady=10, sticky="nsew")

        # Frame para el contenido del panel
        self.details_frame = tb.Frame(self.game_info_panel)
        self.details_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.show_favorites()
       
        
        # Vincular búsqueda en vivo
        search_entry.bind("<KeyRelease>", lambda event: self.filter_games(event, self.search_var))

        # binds del arbol
        self.game_tree.bind("<Double-Button-1>", lambda event: self.double_click_on_game_event(event))
        self.game_tree.bind("<Button-1>", lambda event: self.on_game_click(event))
        self.game_tree.bind("<Button-3>", lambda event: self.on_game_right_click(event))
  
    def on_game_click(self, event):
        game_tree = self.game_tree
        item_id = game_tree.identify_row(event.y) 

        if item_id:
            self.show_game_details(game_tree.item(item_id, "values")[0], item_id)
            game_tree.selection_set(item_id) # selecciona el item clickeado
            return 
        
        else:
            # Clic fuera de cualquier ítem → prevenimos selección
            game_tree.selection_remove(game_tree.selection())
            self.show_favorites()
            return None  # Esto cancela el comportamiento por defecto

    def double_click_on_game_event(self, event):
        game_tree = self.game_tree
        item_id = game_tree.identify_row(event.y)
        
        if item_id: 
                self.launch_game()
                return
   
    def on_game_right_click(self, event):
        game_tree = self.game_tree
        item_id = game_tree.identify_row(event.y) 
        x, y = event.x_root, event.y_root
        
        if item_id:          
            # Obtener el nombre del juego desde el ítem seleccionado
            game_tree.selection_set(item_id)
            game_name = game_tree.item(item_id)["values"][0]            
    
            
            # Mostrar el menú en la posición del puntero
            self.show_menu(game_name, x , y, False)
        else:
            game_tree.selection_remove(*game_tree.selection())
            self.show_menu(None, x , y, False)
   
    def save_config(self):
        Loader.save_config()

    def create_direct_access(self, game_name, launcher_path, game_exe_path, destino_desktop=True):
        platform = self.platform_name
        shell = win32com.client.Dispatch("WScript.Shell")
    
        # Ruta donde se guardará el acceso directo
        desktop = shell.SpecialFolders("Desktop") if destino_desktop else os.getcwd()
        acceso_path = os.path.join(desktop, f"{os.path.splitext(game_name)[0]} Cl69.lnk")

        # Crear acceso directo
        acceso = shell.CreateShortCut(acceso_path)
        acceso.Targetpath = launcher_path  # el .exe del launcher
        acceso.Arguments = f'--launch "{game_name}" --platform "{platform}"'
        acceso.WorkingDirectory = os.path.dirname(launcher_path)
        acceso.IconLocation = game_exe_path  # Obtiene el ícono directamente del .exe del juego
        acceso.save()      

    def launch_game(self): # lanza el ejecutable seleccionado
        platform_name = self.platform_name
        game_tree = self.game_tree
        selected = game_tree.selection()
        gamelaunch = GameLauncherController()
        if selected:
            item_id = selected[0]
            game_name = game_tree.item(item_id, "values")[0]
            game_path = config[platform_name]["game_list"].get(game_name)
            if game_path:
                gamelaunch.launch_game(platform_name, game_name, game_path, on_game_end=lambda: self.update_on_close(platform_name, game_name, item_id))
            else:
                messagebox.showwarning("Atención", "No se pudo encontrar el juego")
        else:
            messagebox.showwarning("Atención", "Selecciona un juego para lanzar")             

    def add_exe(self):
        platform_name = self.platform_name
        exe = filedialog.askopenfilename(title="Selecciona un ejecutable")
        if exe:
            exe_name = os.path.splitext(os.path.basename(exe))[0]
            
            platform = config.setdefault(platform_name, {})
            game_list = platform.setdefault("game_list", {})
            
            game_list[exe_name] = exe
            self.save_config()
            self.loader.update_game_list(platform_name, self.game_tree)
    
    def confirm_remove(self):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        ConfirmDialog(self, title="Eliminar juego", message= "Atencion, estas por elminar un juego", callback=self.remove_exe).place(relx=0.5, rely=0.5, anchor="center")
               
    def remove_exe(self, confirmed): # elimina el ejecutable DE LA LISTA
        platform_name = self.platform_name
        game_tree = self.game_tree
        selected_items = game_tree.selection()
        if confirmed:
            for item_id in selected_items:
                game_name = game_tree.item(item_id, "values")[0]  # El texto del ítem (nombre del juego)

                game_path = config[platform_name]["game_list"].get(game_name)
                self.loader.remove_game_icon(game_path)
            
                config[platform_name]["game_list"].pop(game_name, None)
                config[platform_name].get("game_times", {}).pop(game_name, None)
                config[platform_name].get("game_total_times").pop(game_name, None)
                if game_name in config[platform_name].setdefault("favorites", []):
                    config[platform_name]["favorites"].remove(game_name)
                    
                self.clean_info()
                self.show_favorites()
                game_tree.delete(item_id)
                    
            self.save_config()
        
    def update_game_list(self, platform_name, game_tree):
        self.loader.grouped = not self.loader.grouped
        self.loader.update_game_list(platform_name, game_tree) 

    def update_on_close(self, platform_name, game_name, item_id):
        self.loader.update_game_list(platform_name, self.game_tree)
        self.show_game_details(game_name, item_id)
     
    def filter_games(self, event, search_var):
        platform_name = self.platform_name
        game_tree = self.game_tree
        search_text = search_var.get().lower()
    
        game_tree.delete(*game_tree.get_children())

        if not hasattr(game_tree, "icon_images"):
            game_tree.icon_images = {}

        if not search_text:
            self.loader.grouped = True
            self.loader.update_game_list(platform_name, game_tree)  # agrupado
            return

        results_parent = game_tree.insert("", "end", text="🔍 Resultados", open=True)

        game_list = config.get(platform_name, {}).get("game_list", {})
        for game_name, game_path in game_list.items():
            if search_text in game_name.lower():
                icon = extract_icon(game_path) or self.default_icon
                game_tree.icon_images[game_name] = icon
                base_name = os.path.splitext(game_name)[0]
                game_tree.insert(results_parent, "end", iid=game_name, text="", image=icon, values=(base_name,))
  
    def goto_folder(self, game_name):
        platform_name = self.platform_name
        path= os.path.dirname(config[platform_name]["game_list"][game_name])
        os.startfile(path)

    def change_game_directory(self, game_name):
        try:
            exe = filedialog.askopenfilename(title="Selecciona un ejecutable")

            if not exe:
                return  # El usuario canceló el diálogo

            # Verificamos que la plataforma y el juego existan en config
            if self.platform_name not in config:
                messagebox.showerror("Error", f"La plataforma '{self.platform_name}' no existe.")
                return

            config[self.platform_name]["game_list"][game_name] = exe
            self.save_config()    
        except Exception as e:
            logging.exception("Error al cambiar el directorio del juego")
            messagebox.showerror("Error", f"No se pudo guardar el nuevo ejecutable:\n{e}")
                
    def toggle_favorite(self, game_name):
        platform_name = self.platform_name
        favorites = config[platform_name].setdefault("favorites", [])

        if game_name in favorites:
            favorites.remove(game_name)
        else:
            if len(favorites) >= self.FAVORITE_LIMIT:
                messagebox.showinfo("Límite alcanzado", f"Solo se permiten {self.FAVORITE_LIMIT} favoritos por plataforma.")
                return
            favorites.append(game_name)
            
        self.save_config()

    def show_favorites(self):
        self.clean_info()
        details_panel = GameDetailsPanel(self.details_frame, self.platform_name, launcher_controller=self)
        details_panel.show_favorites()
        details_panel.pack(fill="both", expand=True)
 
    def show_game_details(self, game_name, item_id):
        self.clean_info()
        details_panel = GameDetailsPanel(self.details_frame, self.platform_name, game_name, item_id, launcher_controller=self)
        details_panel.show_game_details()
        details_panel.pack(fill="both", expand=True)
           
    def open_notes_window(self, game_name):
        NotesWindow(self, game_name, notas)

    def show_menu(self, game_name, x_root , y_root, btn_props):
        platform_name = self.platform_name
        menu = CustomPopupMenu(self)
        self.menu_popup = menu
        
        if game_name:
            if not btn_props:
                menu.add_button("▶ Jugar",25 , "success-outline", self.launch_game)
            
            menu.add_button("★ Favoritos", 25, "warning-outline", lambda: self.toggle_favorite(game_name))
            menu.add_button("⤓ Crear acceso directo", 25, "info-outline", lambda: self.create_direct_access(
                            game_name, os.path.abspath(sys.argv[0]), config[platform_name]["game_list"][game_name], destino_desktop=True))
            menu.add_button("📁 Archivos locales", 25, "info-outline", lambda: self.goto_folder(game_name))
            menu.add_button("📂 Cambiar directorio", 25, "info-outline", lambda: self.change_game_directory(game_name))
            menu.add_button("🗑 Eliminar juego", 25, "danger-outline", self.confirm_remove)
            
        
        else:
            menu.add_button("＋ Agregar juego", 25, "success-outline", self.add_exe)
        
        menu.show(x_root, y_root)
  
    def clean_info(self):
        for widget in self.details_frame.winfo_children():
            widget.destroy()
        
class GameDetailsPanel(tb.Frame):
    def __init__(self, parent, platform_name, game_name=None, item_id=None, launcher_controller=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.platform_name = platform_name
        self.game_name = game_name
        self.item_id = item_id
        self.launcher_controller = launcher_controller
        
        self.icon = None
    
    def show_game_details(self):
        self.clean_info()
        game_tree = self.launcher_controller.game_tree

        # Datos
        total_time = config.get(self.platform_name, {}).get("game_total_times", {}).get(self.game_name, 0.0)
        sessions = list(reversed(config.get(self.platform_name, {}).get("game_times", {}).get(self.game_name, [])))

        # === Barra superior ===
        top_bar = tb.Frame(self, padding=5)
        top_bar.pack(fill="x", pady=(0, 10))

        # Botón "Jugar"
        tb.Button(top_bar, text="▶ Jugar", bootstyle="success-outline", width=12,
                  command=self.launch_game).pack(side="left", padx=5, pady=5)

        # Ícono + nombre
        self.icon = game_tree.item(self.item_id, "image")
        formatted_time = f" - {round(total_time/60, 2)} horas"

        game_name_label = tk.Label(top_bar, text=f" {self.game_name}{formatted_time}",
                                   font=("Arial", 12, "bold"), image=self.icon, compound="left")
        game_name_label.image = self.icon
        game_name_label.pack(side="left", padx=10)

        # Botones derecha
        right_buttons = tb.Frame(top_bar)
        right_buttons.pack(side="right", padx=5)

        btn_props = tb.Button(right_buttons, text="⚙", width=4, bootstyle="info-outline",
                              command=self.show_props_menu)
        btn_fav = tb.Button(right_buttons, text="★", width=4, bootstyle="warning-outline",
                            command=self.toggle_favorite)
        btn_extra = tb.Button(right_buttons, text="⋯", width=4, bootstyle="info-outline",
                              command=self.open_notes)

        for btn in (btn_props, btn_fav, btn_extra):
            btn.pack(side="right", padx=2)

        # === Info sesiones ===
        info_frame = tk.Frame(self)
        info_frame.pack(fill="both", expand=True)

        tk.Label(info_frame, text="Últimas sesiones:", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 0))

        if not sessions:
            tk.Label(info_frame, text="No hay sesiones registradas").pack(anchor="w", padx=20)
        else:
            for session in sessions:
                total_time = session['Tiempo']
                hours = int(total_time // 60)
                minutes = int(total_time % 60)
                formatted_time = f"{hours} horas : {minutes} minutos"
                tk.Label(info_frame, text=f"{session['Start']} - {formatted_time}").pack(anchor="w", padx=20)

    def show_favorites(self):
        tk.Label(self, text="★ Tus Favoritos ★", font=("Arial", 14, "bold")).pack(pady=10)

        favorites = config.get(self.platform_name, {}).get("favorites", [])
        game_list = config.get(self.platform_name, {}).get("game_list", {})

        if not favorites:
            tk.Label(self, text="No tienes juegos favoritos aún.").pack(pady=20)
        else:
            for game_name in favorites:
                path = game_list.get(game_name)
                if path:
                    # Pequeña fila con ícono + nombre
                    frame = tb.Frame(self)
                    frame.pack(fill="x", padx=20, pady=5)

                    icon = extract_icon(path)  # Función que ya usás para obtener íconos
                    if icon:
                        icon_label = tk.Label(frame, image=icon)
                        icon_label.image = icon
                        icon_label.pack(side="left", padx=5)

                    tk.Label(frame, text=game_name, font=("Arial", 11)).pack(side="left", padx=5)

                    # Botón rápido de jugar
                    tb.Button(frame, text="▶", width=3, bootstyle="success-outline",
                            command=lambda name=game_name: self.launch_game(name)).pack(side="right")

    def clean_info(self):
        for widget in self.winfo_children():
            widget.destroy()

    def launch_game(self):
        self.launcher_controller.launch_game()

    def toggle_favorite(self):
        self.launcher_controller.toggle_favorite(self.game_name)

    def open_notes(self):
        self.launcher_controller.open_notes_window(self.game_name)

    def show_props_menu(self):
        x = self.winfo_rootx() + self.winfo_width() - 197
        y = self.winfo_rooty() + 40
        self.launcher_controller.show_menu(self.game_name, x, y, True)
               
class NotesWindow(tb.Toplevel):
    def __init__(self, parent, game_name, notes_dict, save_path="notas.json"):
        super().__init__(parent)
        self.title(f"Notas - {game_name}")
        self.geometry("600x400")
        self.resizable(True, True)
        self.open = True

        self.game_name = game_name
        self.notes_dict = notes_dict
        self.save_path = save_path

        # === Estilo general ===
        self.configure(padx=10, pady=10)
        
        # === TextArea con Scrollbar ===
        self.text_area = tk.Text(self, wrap="word", font=("Segoe UI", 11), relief="solid", bd=1)
        self.text_area.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        # Cargar notas previas
        nota_existente = self.notes_dict.get(self.game_name, "")
        self.text_area.insert("1.0", nota_existente)
        
        self.periodic_save()
        self.protocol("WM_DELETE_WINDOW", self.save_and_close)

    def save_and_close(self):
        texto = self.text_area.get("1.0", "end").strip()
        self.notes_dict[self.game_name] = texto
        self.open = False
        self.save_notes()
        self.destroy()
    
    def periodic_save(self):
       if open:
           self.save_notes()
           self.after(300000, self.periodic_save)
        
    def save_notes(self):
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(self.notes_dict, f, ensure_ascii=False, indent=4)

class AutoCloseFrame(tb.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.after(100, self.bind_click_outside)

    def bind_click_outside(self):
        self.bind_all("<Button-1>", self.check_click_outside)
        self.bind_all("<Button-3>", self.check_click_outside)

    def check_click_outside(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        if not widget or not self._is_child_of(widget, self):
            if self.should_close(widget):
                self.on_close(event)

    def should_close(self, widget):
        # logica para decidir cerrar
        return True

    def on_close(self, event=None):
        # comportamiento al cerrar
        self.destroy()

    def _is_child_of(self, widget, parent):
        while widget:
            if widget == parent:
                return True
            widget = widget.master
        return False

class PropertiesWindow(AutoCloseFrame):
    def __init__(self, parent, platform_name, game_tree, on_update_callback=None, on_update_tab=None ):
        super().__init__(parent)
        self.platform_name = platform_name
        self.game_tree = game_tree
        self.on_update_callback = on_update_callback
        self.on_update_tab = on_update_tab
        self.loader = Loader()
        
        self.build_ui()

    def build_ui(self):
        # Top bar con botón cerrar
        top_bar = tb.Frame(self, bootstyle="secondary")
        top_bar.pack(fill="x", padx=5, pady=5)

        close_button = tb.Button(top_bar, text="✕", bootstyle="danger-outline", width=3, command= self.destroy)
        close_button.pack(side="right")

        # Notebook
        self.notebook = tb.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Close on escape
        self.bind("<Escape>", self.destroy)
        
        # Pestaña de directorios
        self.frame_path = tb.Frame(self.notebook)
        self.notebook.add(self.frame_path, text="📁 Directorios")

        self.frame_path.rowconfigure(0, weight=1)
        self.frame_path.columnconfigure([0, 1], weight=1)

        # Scrollbar + Listbox
        scrollbar = tb.Scrollbar(self.frame_path, orient="vertical")
        self.path_listbox = tk.Listbox(self.frame_path, height=12, width=60, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.path_listbox.yview)

        self.path_listbox.grid(row=0, column=0, columnspan=2, padx=(0, 0), pady=5, sticky="nsew")
        scrollbar.grid(row=0, column=2, sticky="ns")

        self.path_listbox.bind("<Double-Button-1>", lambda event: self.double_click_on_path_event(event))
        self.path_listbox.bind("<Button-1>", lambda event: self.on_path_click(event))
        self.path_listbox.bind("<Button-3>", lambda event: self.on_path_right_click(event))
        
        # Label de advertencia debajo de la fila
        self.warning_label_path = tb.Label(self.frame_path, text="", font=("Segoe UI", 9), bootstyle="danger", justify="center")
        self.warning_label_path.grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky="ew")

        # Botones
        btn_add_dir = tb.Button(self.frame_path, text="➕ Agregar Directorio", bootstyle="success-outline", command=self.btn_new_path)
        btn_add_dir.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        btn_remove_dir = tb.Button(self.frame_path, text="🗑 Eliminar Directorio", bootstyle="danger-outline", command=self.confirm_remove)
        btn_remove_dir.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        # === Pestaña para renombrar plataforma ===
        self.platform_tab = tb.Frame(self.notebook)
        self.notebook.add(self.platform_tab, text="📝 Nombre")
        
        self.rename_frame = tb.Frame(self.platform_tab)
        self.rename_frame.pack(pady=30, padx=20)

        # Fila con el label, input y botón
        input_row = tb.Frame(self.rename_frame)
        input_row.pack(fill="x")

        rename_label = tb.Label(input_row, text="Renombrar pestaña:", font=("Segoe UI", 10, "bold"))
        rename_label.pack(side="left", padx=(0, 10))

        self.tab_name_var = tk.StringVar(value=self.platform_name)
        self.entry_tab_name = tb.Entry(input_row, textvariable=self.tab_name_var, width=30)
        self.entry_tab_name.pack(side="left")

        btn_save_name = tb.Button(input_row, text="💾 Guardar", bootstyle="info-outline", command=self.update_tab_name)
        btn_save_name.pack(side="left", padx=10)

        # Label de advertencia debajo de la fila
        self.warning_label = tb.Label(self.rename_frame, text="", font=("Segoe UI", 9), bootstyle="danger", justify="center")
        self.warning_label.pack(pady=(5, 0), anchor="center", fill="x")
        
        self.update_game_list()
        self.update_directory_list()
      
    def on_path_click(self, event):
        path_listbox = self.path_listbox
        index = path_listbox.nearest(event.y)
        bbox = path_listbox.bbox(index)
        if bbox:
            x, y, width, height = bbox
            if y <= event.y <= y + height:
                path_listbox.selection_clear(0, tk.END)  # Limpiar por si acaso
                path_listbox.selection_set(index)  
            # Clic válido, dejamos que Tkinter seleccione el ítem
                return
            else: 
                self.close_menu()
        # Clic fuera de cualquier ítem → prevenimos selección
        path_listbox.selection_clear(0, tk.END)
        return "break"  # Esto cancela el comportamiento por defecto
    
    def double_click_on_path_event(self, event):
        path_listbox = self.path_listbox
        index = path_listbox.nearest(event.y)  # Devuelve el índice más cercano al clic
        bbox = path_listbox.bbox(index)         
        if bbox:
            x, y, width, height = bbox
            if event.y >= y and event.y <= y + height:        
                path_listbox.selection_clear(0, tk.END)  # Limpiar por si acaso
                path_listbox.selection_set(index)        # Asegurar selección                
                self.goto_folder()

    def on_path_right_click(self, event):
        path_listbox = self.path_listbox
        index = path_listbox.nearest(event.y)  # Devuelve el índice más cercano al clic
        bbox = path_listbox.bbox(index)        # Da las coordenadas del ítem
        self.menu = CustomPopupMenu(self, on_close_callback= self.menu_closed)
        
        if bbox:
            x, y, width, height = bbox
            if event.y >= y and event.y <= y + height:
                # Seleccionamos el ítem clickeado
                path_listbox.selection_clear(0, tk.END)  # Limpiar cualquier selección anterior
                path_listbox.selection_set(index)        # Seleccionar el ítem clickeado
                
                self.menu.add_button("📂 Ir a carpeta local", 20, "secondary", command= self.goto_folder)
                self.menu.add_button("🗑️ Eliminar directorio",20, "secondary", command= self.confirm_remove)
    
                # Obtener las coordenadas del puntero
                x, y = event.x_root, event.y_root
    
                # Mostrar el menú en la posición del puntero
                self.menu.show(x, y)
            else:
                self.on_path_right_click_out(event)
        else:
            self.on_path_right_click_out(event)
  
    def on_path_right_click_out(self, event):
        self.menu.add_button("➕ Agregar Directorio", 25, "secondary", command= self.btn_new_path)
        x, y = event.x_root, event.y_root
        self.menu.show(x, y)

    def save_config(self):
        Loader.save_config()
 
    def menu_closed(self, event):
        if event:
            super().check_click_outside(event)
  
    def toggle_multiple_games(self):
        # Cambiar el valor de allow_multiple_games en el config
        current_value = config["global"].get("allow_multiple_games", False)
        config["global"]["allow_multiple_games"] = not current_value
        
        # Guardar el cambio
        with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
    
    def btn_new_path(self):
        self.close_menu()
        self.loader.add_folder(self.platform_name)
        self.update_directory_list()
        self.update_game_list()

    def goto_folder(self):
        path_listbox = self.path_listbox 
        selected = path_listbox.curselection()
        if selected:
            game_path_selected = path_listbox.get(selected[0])      
            if game_path_selected:
                self.close_menu()
                os.startfile(game_path_selected)
            else:
                messagebox.showwarning("Atención", "No se pudo encontrar el Directorio")
        else:
            messagebox.showwarning("Atención", "Selecciona un Directorio")

    def confirm_remove(self):
        path_listbox = self.path_listbox
        selected = path_listbox.curselection()
        if selected:
            if hasattr(self, "menu") and self.menu:
                self.menu.destroy()
            ConfirmDialog(self, title="Eliminar directorio", message= "Atencion, estas por elminar un directorio", callback= self.remove_folder).place(relx=0.5, rely=0.5, anchor="center")
        else: 
            self.warning_label_path.config(text="                                                              Nada que eliminar")
            self.warning_label_path.after(3000, lambda: self.warning_label_path.config(text=""))   

    def remove_folder(self, confirmed): # elimina el directorio DE LA LISTA
        if confirmed:
            path_listbox = self.path_listbox
            selected = path_listbox.curselection()
            path = path_listbox.get(selected[0])
    
            for games, paths in config[self.platform_name]["game_list"].copy().items():
                if path in paths:
                    del config[self.platform_name]["game_list"][games]
        
            for platforms in config[self.platform_name]["platform_folders"].copy():
                if path == platforms:
                    config[self.platform_name]["platform_folders"].remove(path)

        
            path_listbox.delete(selected[0])
            self.update_game_list()
            self.save_config()

    def close_menu(self):
        for widget in self.winfo_children():
            if isinstance(widget, CustomPopupMenu) or isinstance(widget, ConfirmDialog):
                widget.destroy()
    
    def update_directory_list(self): # recible el path_list y lo "actualiza"
        path_listbox = self.path_listbox
        path_listbox.delete(0, tk.END)
        paths = config[self.platform_name]["platform_folders"]
        for path in paths:
            path_listbox.insert(tk.END, f"{path}")

    def update_game_list(self):
        if self.on_update_callback:
            self.on_update_callback()

    def update_tab_name(self):
        if self.on_update_tab :
            if self.tab_name_var.get().strip():
                try:
                    new_name = self.tab_name_var.get().strip().capitalize()
                except:
                    new_name = self.tab_name_var.get().strip()
                
                if new_name:
                    config[new_name] = config.pop(self.platform_name, {})
                
                    try: 
                        index = config["global"]["tab_order"].index(self.platform_name) 
                        config["global"]["tab_order"][index] = new_name
                    except:
                        pass
                
                    pre_name = self.platform_name
                    self.platform_name = new_name
                    self.warning_label.config(text="")  # Oculta la advertencia si está todo bien
                
                    self.save_config()
                    self.on_update_tab(new_name, pre_name)
                    return
            else: 
                self.warning_label.config(text="                                              No podés dejar el nombre vacío.")
                self.warning_label.after(3000, lambda: self.warning_label.config(text=""))
                self.lift()
                return

class CustomPopupMenu(AutoCloseFrame):    
    def __init__(self, parent, on_close_callback=None):
        super().__init__(parent, bootstyle="secondary", relief="raised", borderwidth=1)
        self.on_close_callback = on_close_callback
        self.parent = parent
        self.buttons = []        
        self._menu_open = False

    def add_button(self, text, width, bootstyle, command):
        btn = tb.Button(self, text=text, width=width, bootstyle=bootstyle, command=command)
        btn.pack(fill="x", padx=5, pady=2)
        self.buttons.append(btn)

    def show(self, x_root, y_root):
        if self._menu_open:
            self.destroy()
        
        self.parent.update_idletasks()

        x_win = self.parent.winfo_rootx()
        y_win = self.parent.winfo_rooty()
        relative_x = x_root - x_win
        relative_y = y_root - y_win

        self.place(x=relative_x, y=relative_y)
        self.lift()

        self._menu_open = True

    def on_close(self, event):
        self._menu_open = False
        self.destroy()
        self.parent.unbind_all("<Button-1>")
        self.parent.unbind_all("<Button-3>")
        if self.on_close_callback:
            self.on_close_callback(event)

class InputDialog(AutoCloseFrame):
    def __init__(self, parent, prompt="Ingrese valor:", callback=None, cancel_callback=None):
        super().__init__(parent, padding=10)
        self.callback = callback
        self.cancel_callback = cancel_callback
        self.input_var = StringVar()

        tb.Label(self, text=prompt, font=("Segoe UI", 11), bootstyle="light").pack(padx=10, pady=(5, 5), anchor="w")

        entry = tb.Entry(self, textvariable=self.input_var, font=("Segoe UI", 10))
        entry.pack(padx=10, pady=5, fill="x")
        entry.focus()

        btn_frame = tb.Frame(self)
        btn_frame.pack(pady=(10, 0))

        tb.Button(btn_frame, text="Aceptar", bootstyle="success-outline", command=lambda:self._respond(True)).pack(side="left", padx=5)
        tb.Button(btn_frame, text="Cancelar", bootstyle="danger-outline", command=lambda:self._respond(False)).pack(side="left", padx=5)

        self.bind_all("<Return>", lambda e: self._respond(True))
        self.bind_all("<Escape>", lambda e: self._respond(False))

    def _respond(self, confirmed):
        if confirmed:
            value = self.input_var.get().strip().title()
            if value and self.callback:
                self.callback(value)
            self.destroy()
        
        if not confirmed:
            if self.cancel_callback:
                self.cancel_callback()
            self.destroy()
            
    def on_close(self, event=None):
        if self.cancel_callback:
                self.cancel_callback()
        self.destroy()

class ConfirmDialog(AutoCloseFrame):
    def __init__(self, parent, title="Confirmar", message="¿Estás seguro?", callback=None):
        super().__init__(parent, padding=20)
        self.callback = callback
        
        # Título
        tb.Label(self, text=title, font=("Segoe UI", 12, "bold"), bootstyle="warning").pack(pady=(0, 10))

        # Mensaje
        tb.Label(self, text=message, font=("Segoe UI", 10), wraplength=300).pack(pady=(0, 15))

        # Botones
        btn_frame = tb.Frame(self)
        btn_frame.pack()

        tb.Button(btn_frame, text="✅ Sí", bootstyle="success", width=10,
                  command=lambda:self._respond(True)).pack(side="left", padx=5)

        tb.Button(btn_frame, text="❌ No", bootstyle="danger-outline", width=10,
                  command=lambda:self._respond(False)).pack(side="left", padx=5)

        self.bind_all("<Return>", lambda e: self._respond(True))
        self.bind_all("<Escape>", lambda e: self._respond(False))
        
    def _respond(self, confirmed):
        self.destroy()
        if self.callback:
            self.callback(confirmed)
                   
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

def main():
    if "--launch" in sys.argv and "--platform" in sys.argv:
        game_name = sys.argv[sys.argv.index("--launch") + 1]
        platform_name = sys.argv[sys.argv.index("--platform") + 1]
        game_path = config.get(platform_name, {}).get("game_list", {}).get(game_name)
        launcher_controler = GameLauncherController()
        if game_path:
            launcher_controler.launch_game(platform_name, game_name, game_path)
        else:
            print("No se encontró el juego.")
            
    else:
        clean_orphaned_sessions()
        launcherui = LauncherUI()
        launcher_controler = GameLauncherController()
        launcherui.start()
        
        #steam = SteamIntegration(config)
        #if steam.is_ready():
        #    games = steam.get_owned_games()
        #    formatted = steam.format_games(games)
        #    steam.format_and_cache_games(games)
        #    for game in formatted[:10]:
        #        print(f"🎮 {game['name']} ({game['appid']}) - {game['time']} hs")
        #        print(f"🖼 Icono: {game['icon']}")
        #else:
        #    print("⚠ No se configuró Steam correctamente.")
        
            

                

if __name__ == "__main__":
    main()

# implementar boton save en NotesWindow
# intentar coordinar con una nube? que pasa si juego desde otra pc??
# tratar de integrar ia (para boludear)