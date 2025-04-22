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
from tkinter import filedialog, messagebox, ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import datetime
from PIL import Image, ImageTk


BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
os.makedirs("icons_cache", exist_ok=True)
config_lock = threading.Lock()

# Cargar configuración
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = {}

if "global" not in config:
    config.setdefault("global", {}).setdefault("allow_multiple_games", False)

class loader:
    def __init__(self):
        self.img = Image.open("icons/no_icon.ico").resize((16, 16), Image.LANCZOS)
        self.default_icon= ImageTk.PhotoImage(self.img)
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
        game_tree.delete(*game_tree.get_children())
        
        game_tree.configure(columns=("name",))
        game_tree.column("#0", width=35, stretch=False)  # Solo para el ícono
        game_tree.column("name", anchor="w", width=200)
        game_tree.heading("name", text="Nombre del juego")
        
        game_list = config[platform_name]["game_list"]

        def sort_key(game_name):
            sessions = config[platform_name]["game_times"].get(game_name, [])
            if sessions:
                # Extrae la fecha de la última sesión
                try:
                    last_played = datetime.strptime(sessions[-1]["Start"], "%Y-%m-%d %H:%M:%S")
                    return (0, -last_played.timestamp())
                except ValueError:
                    return (0, float('-inf'))  # fallback si el formato está mal
            else:
                return (1, game_name.lower())  # los no jugados se ordenan alfabéticamente

        ordered_games = sorted(game_list.items(), key=lambda item: sort_key(item[0]), reverse=False)
        
        # Asegurate de guardar las imágenes para que no se borren
        if not hasattr(game_tree, "icon_images"):
            game_tree.icon_images = {}
            
        for name, path in ordered_games:
            icon = extract_icon(path)
            if icon:
                game_tree.icon_images[name] = icon
                base_name = os.path.splitext(name)[0]
                game_tree.insert("", "end", iid=name, text="", image=icon, values=(base_name,))
            if not icon:
                icon = self.default_icon
                game_tree.icon_images[name] = icon
                base_name = os.path.splitext(name)[0]
                game_tree.insert("", "end", iid=name, text="", image=icon, values=(base_name,))    

    def remove_game_icon(self, game_path):
        if not game_path:
            return

        icon_name = os.path.basename(game_path) + ".ico"  # Ej: "game.exe.ico"
        icon_path = os.path.join("icons_cache", icon_name)
        if os.path.exists(icon_path):
            os.remove(icon_path)
    
    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)    

class DraggableNotebook(tb.Notebook):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._active = None
        self.FAVORITE_LIMIT = 5
        self.platform_trees = {}
        self.loader = loader()
        self.img = Image.open("icons/no_icon.ico").resize((16, 16), Image.LANCZOS)
        self.default_icon= ImageTk.PhotoImage(self.img)     
                        
        # este frame se usa cuando no hay tabs (plataformas)
        self.empty_frame = tb.Frame(self)
        tb.Label(self.empty_frame, text="No hay plataformas configuradas").pack(pady=10)
        tb.Button(self.empty_frame, text="Agregar directorio", command=lambda: self.new_platform(False)).pack()
                
        # los comandos de las pestañas
        self.bind('<ButtonPress-1>', self.on_button_press, True)
        self.bind('<ButtonRelease-1>', self.on_button_release)
        self.bind('<B1-Motion>', self.on_mouse_move)
        self.bind("<Button-3>", self.on_right_click)
        
        # las opciones del click derecho sobre una pestaña
        self.menu_in = tk.Menu(self, tearoff=0)
        self.menu_in.add_command(label="Agregar plataforma", command= lambda: self.new_platform(False))
        self.menu_in.add_command(label="Eliminar plataforma", command=self.remove_tab)
        self.menu_in.add_command(label="Propiedades", command= lambda: self.open_properties(self.tab(self._active, "text")))
        
       
        # las opciones del click derecho fuera de una pestaña
        self.menu_out = tk.Menu(self, tearoff=0)
        self.menu_out.add_command(label="Agregar plataforma", command= lambda: self.new_platform(False))
      
        if not self.tabs():
            self.empty_frame.pack(fill="both", expand=True)

    def on_button_press(self, event):
        try:
            self._active = self.index("@%d,%d" % (event.x, event.y))
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
            self.select(self._active)  # Opcional: seleccionarla al hacer clic derecho
            
            
            self.menu_in.tk_popup(event.x_root, event.y_root)
        except:
            self.menu_out.tk_popup(event.x_root, event.y_root)    
    
    def open_properties(self, platform_name):        
        name_changed = False
        def refresh_tree():
            self.loader.update_game_list(platform_name, self.platform_trees[platform_name])
            return
        
        def update_tab(new_name, pre_name):
            for tab_id in self.tabs():
                if self.tab(tab_id, "text") == pre_name:
                    self.tab(tab_id, text= new_name)

            self.platform_trees[new_name] = self.platform_trees.pop(pre_name, {})
                                        
            return
            

        PropertiesWindow(self, platform_name, on_update_callback= refresh_tree, on_update_tab=update_tab )
    
    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def reload(self, reload):
        for platforms in config.get("global", {}).get("tab_order", []):
            if platforms in config:
                self.add_platform(platforms, reload)

    def new_platform(self, reload): # agrega una pestaña nueva en el notebook con el nombre de la plataforma ingresado por el usuario
        platform_name = simpledialog.askstring("Nueva Plataforma", "Nombre de la Plataforma:")
        platform_name = platform_name.capitalize()
        self.add_platform(platform_name, reload)
        if platform_name:
            if self.empty_frame.winfo_ismapped():
                self.empty_frame.pack_forget()
        config.setdefault("global", {})["tab_order"] = [self.tab(i, "text") for i in range(self.index("end"))]
        self.save_config()
 
    def add_platform(self, platform_name, reload): # crea todo el notebook con las pestañas y listboxes necesarios para mostrar los juegos y directorios
        if platform_name:
            if not reload:
                folder= self.loader.add_folder(platform_name)
            else:
                self.empty_frame.pack_forget()
                folder= True
        
            if folder:
                platform_frame = GamePlatformFrame(self, platform_name)
                self.add(platform_frame, text= platform_name)
                self.select(platform_frame)
                self.platform_trees[platform_name] = platform_frame.game_tree
                self.loader.update_game_list(platform_name, self.platform_trees[platform_name])
             
    def remove_tab(self): # elimina una pestaña (plataforma) seleccionada de el notebook y tambien la borra de la lista junto con todo su contenido
        if self._active is not None:
            platform_name= self.tab(self._active, option="text")
            confirm = Messagebox.yesno(title="Eliminar pestaña", message=f"¿Estás seguro de que querés eliminar la pestaña '{platform_name}'?", alert=True, parent=self)
            if confirm == "Yes":
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

class GamePlatformFrame(ttk.Frame):
    def __init__(self, master, platform_name, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.platform_name = platform_name
        self.loader = loader()
        self.img = Image.open("icons/no_icon.ico").resize((16, 16), Image.LANCZOS)
        self.default_icon= ImageTk.PhotoImage(self.img)   
        
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(1, weight=1)
        
        # Campo de búsqueda arriba del árbol de juegos
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(self, textvariable=self.search_var)
        search_entry.grid(row=0, column=0, padx=(10, 5), pady=(10, 0), sticky="ew")
                
        # Árbol de juegos a la izquierda
        self.game_tree = ttk.Treeview(self, show="tree", selectmode="browse", height=15)
        self.game_tree.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="nsw")       
        
        # Panel de contenido a la derecha
        self.game_info_panel = ttk.Frame(self, relief="ridge", padding=10)
        self.game_info_panel.grid(row=0, column=1, rowspan=2, padx=(5, 10), pady=10, sticky="nsew")
                
        # Ejemplo de contenido por defecto (como la portada de Steam)
        info_panel = ttk.Label(self.game_info_panel, text="Selecciona un juego para ver los detalles", anchor="center")
        info_panel.pack(expand=True)
                
        # Vincular búsqueda en vivo
        search_entry.bind("<KeyRelease>", lambda event: self.filter_games(event, platform_name, self.search_var))

        # binds del arbol
        self.game_tree.bind("<Double-Button-1>", lambda event: self.double_click_on_game_event(event, platform_name))
        self.game_tree.bind("<Button-1>", lambda event: self.on_game_click(event, platform_name))
        self.game_tree.bind("<Button-3>", lambda event: self.on_game_right_click(event, platform_name))

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def create_direct_access(self, game_name, platform, launcher_path, game_exe_path, destino_desktop=True):
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

    def launch_game(self, platform_name): # lanza el ejecutable seleccionado
        game_tree = self.game_tree
        selected = game_tree.selection()
        gamelaunch = GameLauncherController()
        if selected:
            item_id = selected[0]
            game_name = game_tree.item(item_id, "values")[0]
            game_path = config[platform_name]["game_list"].get(game_name)
            if game_path:
                gamelaunch.launch_game(platform_name, game_name, game_path, on_game_end=lambda: self.loader.update_game_list(platform_name, self))
            else:
                messagebox.showwarning("Atención", "No se pudo encontrar el juego")
        else:
            messagebox.showwarning("Atención", "Selecciona un juego para lanzar")             
    
    def add_exe(self, platform_name):
        exe = filedialog.askopenfilename(title="Selecciona un ejecutable")
        if exe:
            exe_name = os.path.splitext(os.path.basename(exe))[0]
            
            platform = config.setdefault(platform_name, {})
            game_list = platform.setdefault("game_list", {})
            
            game_list[exe_name] = exe
            self.save_config()
            self.loader.update_game_list(platform_name, self.game_tree)
            
    def toggle_favorite(self, platform_name, game_name):
        favorites = config[platform_name].setdefault("favoritos", [])

        if game_name in favorites:
            favorites.remove(game_name)
        else:
            if len(favorites) >= self.FAVORITE_LIMIT:
                messagebox.showinfo("Límite alcanzado", f"Solo se permiten {self.FAVORITE_LIMIT} favoritos por plataforma.")
                return
            favorites.append(game_name)
            print(f"{game_name} added to favorites.")

        self.save_config()
                     
    def remove_exe(self, platform_name): # elimina el ejecutable DE LA LISTA
        game_tree = self.game_tree
        selected_items = game_tree.selection()
        if selected_items:
            for item_id in selected_items:
                game_name = game_tree.item(item_id, "values")[0]  # El texto del ítem (nombre del juego)

                game_path = config[platform_name]["game_list"].get(game_name)
                self.loader.remove_game_icon(game_path)
                
                config[platform_name]["game_list"].pop(game_name, None)
                config[platform_name].get("game_times", {}).pop(game_name, None)
                config[platform_name].get("game_total_times").pop(game_name, None)
                
                game_tree.delete(item_id)
                
            self.save_config()
        else:
            messagebox.showwarning("Atención", "Selecciona un juego para eliminar de la lista")
            
    def filter_games(self, event, platform_name, search_var):
        game_tree = self.game_tree
        search_text = search_var.get().lower()
        
        game_tree.delete(*game_tree.get_children())

        if not search_text:  # si está vacío, actualizá normalmente
            self.loader.update_game_list(platform_name, game_tree)
            return
        
        if not hasattr(game_tree, "icon_images"):
            game_tree.icon_images = {}
        
        game_list = config.get(platform_name, {}).get("game_list", {})
        for game_name, game_path in game_list.items():
            if search_text in game_name.lower():
                icon = extract_icon(game_path)
                if icon:
                    game_tree.icon_images[game_name] = icon
                    base_name = os.path.splitext(game_name)[0]
                    game_tree.insert("", "end", iid=game_name, text="", image=icon, values=(base_name,))
                if not icon:
                    icon = self.default_icon
                    game_tree.icon_images[game_name] = icon
                    base_name = os.path.splitext(game_name)[0]
                    game_tree.insert("", "end", iid=game_name, text="", image=icon, values=(base_name,)) 

    def on_game_click(self, event, platform_name):
        game_tree = self.game_tree
        item_id = game_tree.identify_row(event.y) 

        if item_id:
            game_tree.selection_set(item_id) # selecciona el item clickeado
            
        else:
            # Clic fuera de cualquier ítem → prevenimos selección
            game_tree.selection_remove(game_tree.selection())
            return "break"  # Esto cancela el comportamiento por defecto

    def double_click_on_game_event(self, event, platform_name):
        game_tree = self.game_tree
        item_id = game_tree.identify_row(event.y)
        
        if item_id: 
                self.launch_game(platform_name)
                return

    def on_game_right_click_out(self, event, platform_name):
        game_tree = self.game_tree
        game_tree.selection_remove(*game_tree.selection())  # Limpiar cualquier selección anterior
        menu= tb.Menu(self, tearoff=0) 
        menu.add_command(label="Agregar Juego", command= lambda: self.add_exe(platform_name))
        # Obtener las coordenadas del puntero
        x, y = event.x_root, event.y_root
        # Mostrar el menú en la posición del puntero
        menu.post(x, y)        
    
    def on_game_right_click(self, event, platform_name):
        game_tree = self.game_tree
        item_id = game_tree.identify_row(event.y)
        
        if item_id:          
            # Obtener el nombre del juego desde el ítem seleccionado
            game_tree.selection_set(item_id)
            game = game_tree.item(item_id)["values"][0]
            game_exe_path = config[platform_name]["game_list"][game] 
            
            # Crea menú contextual
            menu = tb.Menu(self, tearoff=0)  # tearoff=0 evita la opción "desgarrar" el menú

            # Opciones del menú contextual
            menu.add_command(label= "Lanzar juego", command=lambda: self.launch_game(platform_name))
            menu.add_command(label= "Crear acceso directo", command=lambda: self.create_direct_access(game, platform_name, os.path.abspath(sys.argv[0]), game_exe_path, destino_desktop=True))
            menu.add_command(label= "Eliminar juego", command=lambda: self.remove_exe(platform_name))
    
            # Obtener las coordenadas del puntero
            x, y = event.x_root, event.y_root
            # Mostrar el menú en la posición del puntero
            menu.post(x, y)
        else:
            self.on_game_right_click_out(event, platform_name)
               
class PropertiesWindow(tk.Toplevel):
    def __init__(self, parent, platform_name, on_update_callback=None, on_update_tab=None):
        super().__init__(parent)
        self.title(f"Properties")
        self.geometry("400x300")
        self.resizable(False, False)
        self.platform_name = platform_name
        self.on_update_callback = on_update_callback
        self.on_update_tab = on_update_tab
        self.loader = loader()
        
        self.build_ui()

    def build_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        
        self.frame_path = ttk.Frame(self)
        self.notebook.add(self.frame_path, text="Directorios")

        self.frame_path.rowconfigure(0, weight=1,)
        self.frame_path.columnconfigure([0, 1], weight=1)
        
        self.path_listbox = tk.Listbox(self.frame_path, width=60, height=15)
        self.path_listbox.grid(row=0, column=0, columnspan=2, padx=2, pady=5, sticky="nsew")

        self.path_listbox.bind("<Double-Button-1>", lambda event: self.double_click_on_path_event(event))
        self.path_listbox.bind("<Button-1>", lambda event: self.on_path_click(event))
        self.path_listbox.bind("<Button-3>", lambda event: self.on_path_right_click(event))

        btn_add_dir = tk.Button(self.frame_path, text="Agregar Directorio", command= lambda: self.btn_new_path(), bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'))
        btn_add_dir.grid(row=1, column=0, padx=2, pady=2, sticky="ew")

        btn_remove_dir = tk.Button(self.frame_path, text="Eliminar Directorio", command= lambda: self.remove_folder(), bg='#f44336', fg='white', font=('Arial', 12, 'bold'))
        btn_remove_dir.grid(row=1, column=1, padx=2, pady=2, sticky="ew")
        
        self.platform_tab = ttk.Frame(self)
        self.notebook.add(self.platform_tab, text = "Pestaña")

        self.rename_frame = ttk.Frame(self.platform_tab)
        self.rename_frame.pack(pady=20, padx=10)
        
        tk.Label(self.rename_frame, text="Rename:").pack(side="left", padx=(0, 10))

        self.tab_name_var = tk.StringVar(value=self.platform_name)
        entry_tab_name = ttk.Entry(self.rename_frame, textvariable= self.tab_name_var, width=30)
        entry_tab_name.pack(side="left")
        
        btn_save_name = ttk.Button(self.rename_frame, text="Save", command= self.update_tab_name)
        btn_save_name.pack(side="left", padx=10)
        
        self.update_game_list()
        self.update_directory_list()
        
    def on_path_click(self, event):
        path_listbox = self.path_listbox
        index = path_listbox.nearest(event.y)
        bbox = path_listbox.bbox(index)

        if bbox:
            x, y, width, height = bbox
            if y <= event.y <= y + height:
            # Clic válido, dejamos que Tkinter seleccione el ítem
                return
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
    
    def on_path_right_click_out(self, event):
        menu = tb.Menu(self, tearoff=0) 
        menu.add_command(label= "Agregar directorio", command=self.btn_new_path)
        x, y = event.x_root, event.y_root
        menu.post(x, y)

    def toggle_multiple_games(self):
        # Cambiar el valor de allow_multiple_games en el config
        current_value = config["global"].get("allow_multiple_games", False)
        config["global"]["allow_multiple_games"] = not current_value

        # Guardar el cambio
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        print(f"Permitir múltiples juegos: {not current_value}")
    
    def btn_new_path(self):
        self.loader.add_folder(self.platform_name)
        self.update_directory_list()
        self.update_game_list()
    
    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    
    def on_path_right_click(self, event):
        path_listbox = self.path_listbox
        index = path_listbox.nearest(event.y)  # Devuelve el índice más cercano al clic
        bbox = path_listbox.bbox(index)        # Da las coordenadas del ítem
    
        if bbox:
            x, y, width, height = bbox
            if event.y >= y and event.y <= y + height:
                # Seleccionamos el ítem clickeado
                path_listbox.selection_clear(0, tk.END)  # Limpiar cualquier selección anterior
                path_listbox.selection_set(index)        # Seleccionar el ítem clickeado
                # Crea menú contextual
                menu = tb.Menu(self, tearoff=0)  # tearoff=0 evita la opción "desgarrar" el menú

                # Opciones del menú contextual
                menu.add_command(label= "Ir a carpeta local", command= self.goto_folder)
                menu.add_command(label= "Eliminar directorio", command= self.remove_folder)
    
                # Obtener las coordenadas del puntero
                x, y = event.x_root, event.y_root
    
                # Mostrar el menú en la posición del puntero
                menu.post(x, y)
            else:
                self.on_path_right_click_out(event)
        else:
            self.on_path_right_click_out(event)

    def goto_folder(self):
        path_listbox = self.path_listbox 
        selected = path_listbox.curselection()
        if selected:
            game_path_selected = path_listbox.get(selected[0])      
            if game_path_selected:
                os.startfile(game_path_selected)
            else:
                messagebox.showwarning("Atención", "No se pudo encontrar el Directorio")
        else:
            messagebox.showwarning("Atención", "Selecciona un Directorio")

    def remove_folder(self): # elimina el directorio DE LA LISTA
        path_listbox = self.path_listbox
        selected = path_listbox.curselection()
        if selected:
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
        else: 
            messagebox.showwarning("Atención", "Selecciona un directorio para eliminar de la lista")
        
        # Close on escape
        self.bind("<Escape>", lambda e: self.destroy())

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
        if self.on_update_tab:
            new_name = self.tab_name_var.get().strip().capitalize()
            if new_name:
                config[new_name] = config.pop(self.platform_name, {})
                
                try: 
                    index = config["global"]["tab_order"].index(self.platform_name) 
                    config["global"]["tab_order"][index] = new_name
                except:
                    pass
                
                pre_name = self.platform_name
                self.platform_name = new_name
                
                self.save_config()
            self.on_update_tab(new_name, pre_name)
            
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
            # Usamos el lock para asegurarnos de que no se modifique el estado de launched de forma concurrente
            with self.lock:
                allow_multiple = config["global"].get("allow_multiple_games", False)

                if not allow_multiple:
                    if self.launched:
                        logging.info("Ya hay un juego en ejecución, no se puede iniciar otro.")
                        return

                # Marcar que el juego está lanzado
                self.launched = True

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start = time.time()

            # Lanza el juego en un proceso nuevo
            process = subprocess.Popen(game_path)
            process.wait()

            end = time.time()
            dur_min = (end - start) / 60  # Tiempo transcurrido en minutos

            # Guardamos los tiempos en la configuración
            new_session = {"Start": now, "Tiempo": round(dur_min, 2)}
            game_times = config[platform_name].setdefault("game_times", {})
            game_times.setdefault(game_name, []).append(new_session)
            game_times[game_name] = game_times[game_name][-5:]

            game_total_times = config[platform_name].setdefault("game_total_times", {})
            game_total_times.setdefault(game_name, 0.0)
            game_total_times[game_name] += round(dur_min, 2)

            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)

            # Reseteamos el estado de launched después de que el juego haya terminado
            with self.lock:
                self.launched = False

            if on_game_end:
                on_game_end()

        # Ejecutamos la lógica de lanzamiento del juego en un hilo separado
        thread = threading.Thread(target=execute)
        thread.start()

def extract_icon(path, size=(16, 16)):
    os.makedirs("icons_cache", exist_ok=True)
    try:
        ico_path = f"icons_cache/{os.path.basename(path)}.ico"
        
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
                
                launcher_controler.launch_game_threaded(platform_name, game_name, game_path)
        else:
            print("No se encontró el juego.")
    else:
        # Mostrar la interfaz
        root = tb.Window(themename="darkly")
        root.title("Game Launcher")
        root.iconbitmap("icons/icon.ico")
        root.geometry("900x600")
        root.minsize(600, 400)
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        notebook = DraggableNotebook(root)
        notebook.grid(row=0, column=0, sticky="nsew")
        
        # Recargo mis datos guardados en config si es que existen
        if config:
            notebook.reload(True)
            
        root.mainloop()

if __name__ == "__main__":
    main()