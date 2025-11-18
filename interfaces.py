import os
import json
import psutil
import threading
import logging
import time
import sys
import platform
import datafiles
import custommenus
import shutil
import ttkbootstrap as tb
import tkinter as tk
from pathlib import Path
from machine_id import get_machine_id
from googleapiclient.discovery import build
from ttkbootstrap.toast import ToastNotification
from ttkbootstrap.dialogs import Messagebox
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
from helpers import Loader, GameLauncherController, extract_icon, reload_in_thread, collect_platform_data
from icon_utils import set_window_icon, load_icon
from cloudsync import get_drive_service
from custommenus import ConfirmDialog

if sys.platform.startswith("win"):
    import win32com.client

class SplashFrame(tb.Frame):
    def __init__(self, parent, title="Cargando..."):
        super().__init__(parent)
        self.grid(row=0, column=0, sticky="nsew")

        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        label = tb.Label(self, text=title, font=("Segoe UI", 32))
        label.pack(expand=True)

    def close(self):
        self.destroy()

class LauncherUI:
    def __init__(self):
        self.root = tb.Window(themename="darkly")
        self.root.title("CLauncher69")
        self.root.geometry("900x600")
        self.root.minsize(600, 400)
        self.grouped = True
        
        # Splash integrado
        self.splash = SplashFrame(self.root, title="Cargando Launcher...")

    def init_ui(self):
        """Inicializa la interfaz real y cierra el splash después de cargar todo."""
        # Configuración de la ventana
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)


        # Notebook de plataformas
        self.app = MainLauncherFrame(self.root)
        self.app.grid(row=0, column=0, sticky="nsew")
        
        # Manager de sesiones
        self.session_manager = SessionManager(self.root, self)
        if datafiles.config:
            reload_in_thread(self, self.start)
        
        if datafiles.config.get("tab_order") is None:
            self.app.notebook.emptyframe()
        
        # Cuando termina de cargar, cerramos el splash
        self.splash.close()
        
    def set(self):
        self.root.after(300, self.init_ui)        
        self.root.mainloop()        
    
    def start(self, all_data):
        populate_ui(all_data, self.app.notebook, False)
        self.restore_sessions()
        self.monitor_sessions()
          
    def add_session(self, game_name, process, start_time):
        self.session_manager.add_session(game_name, process, start_time)

    def monitor_sessions(self):
        def loop():
            while True:
                if os.path.exists(datafiles.FLAG_FILE):
                    try:
                        os.remove(datafiles.FLAG_FILE)  # Se procesa una sola vez
                        
                        # Releer config.json desde disco
                        Loader.load_config()

                        # Actualizar visualmente
                        self.restore_sessions()
                    except Exception as e:
                        print(f"Error al manejar el archivo de aviso: {e}")
                time.sleep(5)
        threading.Thread(target=loop, daemon=True).start()

    def restore_sessions(self):
        sessions = datafiles.config["global"].get("actual_sessions", {})
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

class MainLauncherFrame(tb.Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        
        # --- Top bar fija ---
        top_bar = tb.Frame(self, bootstyle="dark")
        top_bar.pack(fill="x")

        email = (datafiles.config.get("global", {}).get("email") or "Desconocido")

        self.title_label = tb.Label(top_bar, text=f"Cuenta: {email}", font=("Segoe UI", 11, "bold"), bootstyle="inverse-dark")
        self.title_label.pack(side="left", padx=10, pady=5)

        # Botón de sincronización
        sync_btn = tb.Button(top_bar, text="☁ Sincronización", bootstyle="info-outline", command=self.open_cloud_settings)
        sync_btn.pack(side="right", padx=10, pady=5)

        # Botón de agregar plataformas
        add_btn = tb.Button(top_bar, text="🞧 Agregar plataforma", bootstyle="info-outline", command= self.ask_platform_name)
        add_btn.pack(side="right", padx=10, pady=5)

        # --- Contenido principal: tu Notebook ---
        self.notebook = DraggableNotebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

    def open_cloud_settings(self):
        self.notebook.open_cloud_settings()

    def ask_platform_name(self):
        self.notebook.ask_platform_name()

    def update_title_label(self):
        email = (datafiles.config.get("global", {}).get("email") or "Desconocido")
        self.title_label.config(text=f"Cuenta: {email}")
        
class DraggableNotebook(tb.Notebook):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.master = master
        self._active = None
        self.active_popup= None
        self.input_open = False
        self.FAVORITE_LIMIT = 5
        self.platform_trees = {}
        self.loader = Loader()
        self.default_icon= load_icon(os.path.join(datafiles.ICONS, "no_icon.ico"), size=(16,16))
        self.service = None
                        
        # este frame se usa cuando no hay tabs (plataformas)
        self.empty_frame = tb.Frame(self)
        tb.Label(self.empty_frame, text="🚫 No hay plataformas configuradas", font=("Segoe UI", 12, "bold"), bootstyle="warning").pack(pady=10)
                
        # los comandos de las pestañas
        self.bind('<ButtonPress-1>', self.on_button_press, True)
        self.bind('<B1-Motion>', self.on_mouse_move)
        self.bind('<ButtonRelease-1>', self.on_button_release)
        self.bind("<Button-3>", self.on_right_click)
        self.bind("<<NotebookTabChanged>>", self.on_tab_change)
         
    def on_button_press(self, event):
        # Cerrar menús flotantes si existen
        if hasattr(self, "menu_popup"):
            try:
                self.menu_popup.destroy()
            except:
                pass

        try:
            self._active = self.index(f"@{event.x},{event.y}")
        except tk.TclError:
            self._active = None

    def on_button_release(self, event):
        if self._active is not None:
            self.save_tab_order()
        self._active = None

    def on_mouse_move(self, event):
        if self._active is None:
            return

        try:
            index = self.index(f"@{event.x},{event.y}")
            if index != self._active:
                self.insert(index, self._active)
                self._active = index
        except tk.TclError:
            pass
    
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

    def save_tab_order(self):   
        order = [self.tab(i, "text") for i in range(self.index("end"))]
        datafiles.config.setdefault("global", {})["tab_order"] = order
        self.save_config()

    def on_tab_change(self, event):
        try:     
            selected_tab_text = self.tab(self.select(), "text")
            datafiles.config["global"]["last_selected_tab"]= selected_tab_text
            self.save_config()
        except:
            pass
            
    def save_config(self):
        Loader.save_config()

    def ask_platform_name(self):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        if not self.input_open:
            self.empty_frame.pack_forget()
            self.input_open = True
            self.input = custommenus.InputDialog(self, prompt="Nombre de la Plataforma:", callback=self.new_platform, cancel_callback= self.emptyframe).pack()

    def emptyframe(self):
        self.input_open = False 
        if not self.tabs():
            self.empty_frame.pack(fill="both", expand=True)
        elif self.empty_frame and self.tabs():
            self.empty_frame.pack_forget()
                                      
    def new_platform(self, platform_name):
        self.input_open = False
        if platform_name: 
            folder = self.loader.add_folder(platform_name)
            if folder:
                self.emptyframe()
                
                call_populate(platform_name, self)
                datafiles.config.setdefault("global", {})["tab_order"] = [self.tab(i, "text") for i in range(self.index("end"))]
                
                self.save_config()
                
                for i in self.tabs():
                    if self.tab(i, "text") == platform_name:
                        self.select(i)
                        break
    
    def call_populate(self, platform_name):
        all_data = []
        all_data.append(collect_platform_data(platform_name))
        populate_ui(all_data,self)
        self.save_tab_order()

    def confirm_remove(self):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        custommenus.ConfirmDialog(self, title="Eliminar plataforma", message= "Atencion, estas por elminar una plataforma", callback=self.remove_tab).place(relx=0.5, rely=0.5, anchor="center")
             
    def remove_tab(self, confirmed): # elimina una pestaña (plataforma) seleccionada de el notebook y tambien la borra de la lista junto con todo su contenido
        if self._active is not None:
            platform_name= self.tab(self._active, option="text")
            if confirmed:
                for game_name, game_path in datafiles.config[platform_name].get("game_list", {}).items():
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
        
        datafiles.config.setdefault("global", {})["tab_order"] = [self.tab(i, "text") for i in range(self.index("end"))]
        self.save_config()
    
    def remove_platform(self, platform_name): # trabaja en conjunto con remove_tab, esto es lo que borra la plataforma de la lista
        del datafiles.config[platform_name]
        self.save_config()

    def show_menu(self, platform_name, x_root, y_root):
        self.menu_popup = custommenus.CustomPopupMenu(self)
        
        if platform_name:  
            self.menu_popup.add_button("🗑 Eliminar plataforma", 25, "danger-outline", self.confirm_remove)
            self.menu_popup.add_button("⚙ Propiedades", 25, "info-outline", lambda: self.open_properties(self.tab(self._active, "text")))
        
        self.menu_popup.show(x_root, y_root)
  
    def open_properties(self, platform_name):
        self.menu_popup.destroy()
        def refresh_tree():
            call_populate(platform_name, self)
            return
        
        def update_tab(new_name, pre_name):
            for tab_id in self.tabs():
                if self.tab(tab_id, "text") == pre_name:
                    self.tab(tab_id, text= new_name)

            self.platform_trees[new_name] = self.platform_trees.pop(pre_name, {})                            
            return

        self.properties_window = PropertiesWindow(self, platform_name, self.platform_trees[platform_name], on_update_callback= refresh_tree, on_update_tab=update_tab)
        self.properties_window.pack()        

    def open_cloud_settings(self):
        self.empty_frame.pack_forget()
        CloudSettingsWindow(self, self.service, on_close_callback= self.on_close_cloudwdw).pack()
        
    def on_close_cloudwdw(self):
        self.emptyframe()
        self.master.update_title_label()
           
class GamePlatformFrame(ttk.Frame):
    def __init__(self, master, platform_name, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.FAVORITE_LIMIT = 5
        self.platform_name = platform_name
        self.menu = False
        self.loader = Loader()
        self.img = Image.open(os.path.join(datafiles.ICONS, f"no_icon.ico")).resize((16, 16), Image.LANCZOS)
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

        btn_clear = tb.Button(search_frame, text="📂", bootstyle="secondary", command=lambda: call_populate(self.platform_name, self.game_tree))
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
        self.game_tree.bind("<<TreeviewSelect>>", self.on_selection_change)
  
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

    def on_delete_key(self, event):
        self.confirm_remove()

    def on_selection_change(self, event):
        """Activa o desactiva el bind de Supr según haya selección o no."""
        selection = self.game_tree.selection()
        if selection:
            # Si hay algo seleccionado → bindear Supr
            self.bind_all("<Delete>", self.on_delete_key)
        else:
            # Si no hay nada → desbindear Supr
            self.unbind_all("<Delete>")

    def save_config(self):
        Loader.save_config()

    def create_direct_access(self, game_name, launcher_path, game_exe_path, destino_desktop=True):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        if sys.platform.startswith("win"):
            return self.create_direct_access_win(game_name, launcher_path, game_exe_path, destino_desktop)
        else:
            return self.create_direct_access_linux(game_name, launcher_path, game_exe_path, destino_desktop)
        
    def create_direct_access_linux(self, game_name, launcher_path, game_exe_path, destino_desktop=True):
        def get_linux_desktop_dir():
            xdg_file = Path.home() / ".config" / "user-dirs.dirs"

            if xdg_file.exists():
                with open(xdg_file, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("XDG_DESKTOP_DIR"):
                            path = line.split("=")[1].strip().replace('"', "")
                            # reemplaza $HOME por la ruta real
                            path = path.replace("$HOME", str(Path.home()))
                            return os.path.expanduser(path)

            # fallback: si el archivo no existe o no tiene la variable
            return os.path.expanduser("~/Desktop")
        
        platform = self.platform_name
        desktop_dir = get_linux_desktop_dir() if destino_desktop else os.getcwd()
        os.makedirs(desktop_dir, exist_ok=True)
        file_path = os.path.join(desktop_dir, f"{game_name}.desktop")
        
        # Asegurar que el icono esté cacheado
        if os.path.exists(game_exe_path):
            try:
                extract_icon(game_exe_path)  # fuerza caché
            except Exception as e:
                print(f"Error extrayendo icono: {e}")
        
        # Buscar en el caché si existe
        cache_icon_path = datafiles.ICONS_CACHE_DIR / f"{Path(game_exe_path).stem}.png"
        if cache_icon_path.exists():
            icon_path = cache_icon_path
        else:
            icon_path = Path("/usr/share/pixmaps/default.png")
        
        icon_target_dir = Path.home() / ".local/share/icons"
        icon_target_dir.mkdir(parents=True, exist_ok=True)
        icon_target = icon_target_dir / f"{game_name.lower().replace(' ', '_')}.png"

        try:
            if os.path.exists(icon_path):
                shutil.copy(icon_path, icon_target)
            else:
                icon_target = Path("/usr/share/pixmaps/default.png")
        except Exception as e:
            print(f"No se pudo copiar el icono: {e}")
            icon_target = Path("/usr/share/pixmaps/default.png")

        content = f"""[Desktop Entry]
        Name={game_name}
        Comment=Lanzador Cl69
        Exec="{launcher_path}" --launch "{game_name}" --platform "{platform}"
        Icon={icon_target}
        Terminal=false
        Type=Application
        """

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Dar permisos de ejecución al .desktop
        os.chmod(file_path, 0o755)
     
    def create_direct_access_win(self, game_name, launcher_path, game_exe_path, destino_desktop=True):
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

    def create_start_menu_shortcut(self, game_name, game_path, icon_path=None):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        system = platform.system()
        platform_name = self.platform_name
        
        if system == "Windows":
            try:
                from win32com.client import Dispatch

                # 📂 Menú inicio del usuario actual (no requiere admin)
                start_menu = Path(os.getenv("APPDATA")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                shortcut_path = start_menu / f"{game_name}.lnk"

                # 🔧 Crear el acceso directo
                shell = Dispatch('WScript.Shell')
                shortcut = shell.CreateShortcut(str(shortcut_path))
                shortcut.TargetPath = sys.executable  # tu launcher
                shortcut.Arguments = f'--launch "{game_name}" --platform "{platform_name}"'
                shortcut.WorkingDirectory = str(Path(game_path).parent)
                shortcut.IconLocation = game_path
                shortcut.save()

                print(f"Acceso directo creado en el menú Inicio: {shortcut_path}")

            except Exception as e:
                print(f"Error al crear el acceso directo en Windows: {e}")

        elif system == "Linux":
            # Linux usa archivos .desktop en ~/.local/share/applications
            desktop_entry_dir = Path.home() / ".local/share/applications"
            desktop_entry_dir.mkdir(parents=True, exist_ok=True)

            desktop_entry_path = desktop_entry_dir / f"{game_name.lower().replace(' ', '_')}.desktop"

            # Determina el comando (el launcher con argumentos)
            command = f'"{sys.executable}" "{Path(__file__).resolve()}" --launch "{game_name}" --platform "{platform_name}"'
            
            # Asegurar que el icono esté cacheado
            if os.path.exists(game_path):
                try:
                    extract_icon(game_path)  # fuerza caché
                except Exception as e:
                    print(f"Error extrayendo icono: {e}")

            # Buscar en el caché si existe
            cache_icon_path = datafiles.ICONS_CACHE_DIR / f"{Path(game_path).stem}.png"
            if cache_icon_path.exists():
                icon_path = cache_icon_path
            else:
                icon_path = Path("/usr/share/pixmaps/default.png")
                
            # Asegurar que el icono exista y esté en una ubicación estándar (~/.local/share/icons)
            icon_target_dir = Path.home() / ".local/share/icons"
            icon_target_dir.mkdir(parents=True, exist_ok=True)
            
            # Nombre del icono estandarizado
            icon_target = icon_target_dir / f"{game_name.lower().replace(' ', '_')}.png"
            
            try:
                # Si el ícono existe, copiarlo al destino (y reemplazar si ya existe)
                if os.path.exists(icon_path):
                    shutil.copy(icon_path, icon_target)
                else:
                    # Fallback si no hay ícono
                    icon_target = Path("/usr/share/pixmaps/default.png")
            except Exception as e:
                print(f"No se pudo copiar el icono: {e}")
                icon_target = Path("/usr/share/pixmaps/default.png")

            desktop_entry_content = f"""[Desktop Entry]
                Type=Application
                Name={game_name}
                Exec={command}
                Icon = {icon_target}
                Terminal=false
                Categories=Game;
                StartupNotify=true
                """

            desktop_entry_path.write_text(desktop_entry_content)
            os.chmod(desktop_entry_path, 0o755)
            print(f"Archivo .desktop creado: {desktop_entry_path}")
            
        else:
            print("Sistema operativo no soportado para accesos directos al inicio.")

    def launch_game(self): # lanza el ejecutable seleccionado
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        platform_name = self.platform_name
        game_tree = self.game_tree
        selected = game_tree.selection()
        gamelaunch = GameLauncherController()
        if selected:
            item_id = selected[0]
            game_name = game_tree.item(item_id, "values")[0]
            game_path = datafiles.config[platform_name]["game_list"].get(game_name)
            if game_path:
                gamelaunch.launch_game(platform_name, game_name, game_path, on_game_end=lambda: self.update_on_close(platform_name, game_name, item_id))
            else:
                messagebox.showwarning("Atención", "No se pudo encontrar el juego")
        else:
            messagebox.showwarning("Atención", "Selecciona un juego para lanzar")             

    def add_exe(self):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        platform_name = self.platform_name
        exe = filedialog.askopenfilename(title="Selecciona un ejecutable")
        if exe:
            exe_name = os.path.splitext(os.path.basename(exe))[0]
            
            platform = datafiles.config.setdefault(platform_name, {})
            game_list = platform.setdefault("game_list", {})
            
            game_list[exe_name] = exe
            self.save_config()
            call_populate(platform_name, self.game_tree)
    
    def confirm_remove(self):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        custommenus.ConfirmDialog(self, title="Eliminar juego", message= "Atencion, estas por elminar un juego", callback=self.remove_exe).place(relx=0.5, rely=0.5, anchor="center")
               
    def remove_exe(self, confirmed): # elimina el ejecutable DE LA LISTA
        platform_name = self.platform_name
        game_tree = self.game_tree
        selected_items = game_tree.selection()
        if confirmed:
            for item_id in selected_items:
                game_name = game_tree.item(item_id, "values")[0]  # El texto del ítem (nombre del juego)

                game_path = datafiles.config[platform_name]["game_list"].get(game_name)
                self.loader.remove_game_icon(game_path)
            
                datafiles.config[platform_name]["game_list"].pop(game_name, None)
                datafiles.config[platform_name].get("game_times", {}).pop(game_name, None)
                datafiles.config[platform_name].get("game_total_times").pop(game_name, None)
                if game_name in datafiles.config[platform_name].setdefault("favorites", []):
                    datafiles.config[platform_name]["favorites"].remove(game_name)
                    
                self.clean_info()
                self.show_favorites()
                game_tree.delete(item_id)
                    
            self.save_config()

    def update_on_close(self, platform_name, game_name, item_id):
        Loader.load_config()
        call_populate(platform_name, self.game_tree)
        self.show_game_details(game_name, item_id)
     
    def filter_games(self, event, search_var):
        platform_name = self.platform_name
        game_tree = self.game_tree
        search_text = search_var.get().lower()
    
        game_tree.delete(*game_tree.get_children())

        if not hasattr(game_tree, "icon_images"):
            game_tree.icon_images = {}

        if not search_text:
            call_populate(platform_name, game_tree)  # agrupado
            return

        results_parent = game_tree.insert("", "end", text="🔍 Resultados", open=True)

        game_list = datafiles.config.get(platform_name, {}).get("game_list", {})
        for game_name, game_path in game_list.items():
            if search_text in game_name.lower():
                icon = extract_icon(game_path) or self.default_icon
                game_tree.icon_images[game_name] = icon
                base_name = os.path.splitext(game_name)[0]
                game_tree.insert(results_parent, "end", iid=game_name, text="", image=icon, values=(base_name,))
  
    def goto_folder(self, game_name):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        platform_name = self.platform_name
        path= os.path.dirname(datafiles.config[platform_name]["game_list"][game_name])
        os.startfile(path)

    def change_game_directory(self, game_name):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        try:
            exe = filedialog.askopenfilename(title="Selecciona un ejecutable")

            if not exe:
                return  # El usuario canceló el diálogo

            # Verificamos que la plataforma y el juego existan en config
            if self.platform_name not in datafiles.config:
                messagebox.showerror("Error", f"La plataforma '{self.platform_name}' no existe.")
                return

            datafiles.config[self.platform_name]["game_list"][game_name] = exe
            self.save_config()    
        except Exception as e:
            logging.exception("Error al cambiar el directorio del juego")
            messagebox.showerror("Error", f"No se pudo guardar el nuevo ejecutable:\n{e}")
                
    def toggle_favorite(self, game_name):
        if hasattr(self, "menu_popup") and self.menu_popup:
            self.menu_popup.destroy()
        platform_name = self.platform_name
        favorites = datafiles.config[platform_name].setdefault("favorites", [])

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
        NotesWindow(self, game_name, datafiles.notas)

    def show_menu(self, game_name, x_root , y_root, btn_props):
        platform_name = self.platform_name
        menu = custommenus.CustomPopupMenu(self)
        self.menu_popup = menu
        
        if game_name:
            if not btn_props:
                menu.add_button("▶ Jugar",25 , "success-outline", self.launch_game)
            
            menu.add_button("★ Favoritos", 25, "warning-outline", lambda: self.toggle_favorite(game_name))
            menu.add_button("⤓ Crear acceso directo", 25, "info-outline", lambda: self.create_direct_access(
                            game_name, os.path.abspath(sys.argv[0]), datafiles.config[platform_name]["game_list"][game_name], destino_desktop=True))
            menu.add_button("📌 Añadir a inicio", 25, "info-outline", lambda: self.create_start_menu_shortcut(game_name, datafiles.config[platform_name]["game_list"][game_name], datafiles.ICONS))
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
        times_for_pc = datafiles.config.get(self.platform_name, {}).get("game_total_times", {}).get(self.game_name, {})
        total_time = 0.0
        for pcids in times_for_pc:
            total_time = total_time + times_for_pc.get(pcids, 0.0)
        sessions = list(reversed(datafiles.config.get(self.platform_name, {}).get("game_times", {}).get(self.game_name, [])))

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

        favorites = datafiles.config.get(self.platform_name, {}).get("favorites", [])
        game_list = datafiles.config.get(self.platform_name, {}).get("game_list", {})

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
                            command=self.launch_game).pack(side="right")
                    
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
        with open(datafiles.NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(self.notes_dict, f, ensure_ascii=False, indent=4)

class PropertiesWindow(custommenus.AutoCloseFrame):
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
        self.menu = custommenus.CustomPopupMenu(self, on_close_callback= self.menu_closed)
        
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
        current_value = datafiles.config["global"].get("allow_multiple_games", False)
        datafiles.config["global"]["allow_multiple_games"] = not current_value
        
        # Guardar el cambio
        Loader.save_config()
    
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
            custommenus.ConfirmDialog(self, title="Eliminar directorio", message= "Atencion, estas por elminar un directorio", callback= self.remove_folder).place(relx=0.5, rely=0.5, anchor="center")
        else: 
            self.warning_label_path.config(text="                                                              Nada que eliminar")
            self.warning_label_path.after(3000, lambda: self.warning_label_path.config(text=""))   

    def remove_folder(self, confirmed): # elimina el directorio DE LA LISTA
        if confirmed:
            path_listbox = self.path_listbox
            selected = path_listbox.curselection()
            path = path_listbox.get(selected[0])
    
            for games, paths in datafiles.config[self.platform_name]["game_list"].copy().items():
                if path in paths:
                    del datafiles.config[self.platform_name]["game_list"][games]
        
            for platforms in datafiles.config[self.platform_name]["platform_folders"].copy():
                if path == platforms:
                    datafiles.config[self.platform_name]["platform_folders"].remove(path)

        
            path_listbox.delete(selected[0])
            self.update_game_list()
            self.save_config()

    def close_menu(self):
        for widget in self.winfo_children():
            if isinstance(widget, custommenus.CustomPopupMenu) or isinstance(widget, custommenus.ConfirmDialog):
                widget.destroy()
    
    def update_directory_list(self): # recible el path_list y lo "actualiza"
        path_listbox = self.path_listbox
        path_listbox.delete(0, tk.END)
        paths = datafiles.config[self.platform_name]["platform_folders"]
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
                    datafiles.config[new_name] = datafiles.config.pop(self.platform_name, {})
                
                    try: 
                        index = datafiles.config["global"]["tab_order"].index(self.platform_name) 
                        datafiles.config["global"]["tab_order"][index] = new_name
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

class CloudSettingsWindow(custommenus.AutoCloseFrame):
    def __init__(self, parent, service=None, folder_id=None, on_close_callback=None, **kwargs):
        super().__init__(parent, on_close_callback=on_close_callback, **kwargs)
        self.on_close_callback = on_close_callback
        self.service = service
        self.folder_id = folder_id
        self.parent = parent
        
        self.build_ui()
        
        # Close on Escape
        self.bind("<Escape>", lambda e: self.destroy())

    def build_ui(self):
        # Notebook principal
        self.notebook = tb.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # === Pestaña de sincronización ===
        self.sync_tab = tb.Frame(self.notebook)
        self.notebook.add(self.sync_tab, text="☁️ Sincronización")

        # Checkbox para sincronización automática
        self.auto_sync_var = tk.BooleanVar(value=datafiles.config.get("global", {}).get("cloud_sync_enabled", False))
        chk_sync = tb.Checkbutton(self.sync_tab, text="Habilitar sincronización automática", variable=self.auto_sync_var, bootstyle="success", command=self.save_sync_setting)
        chk_sync.pack(pady=20, padx=20, anchor="w")

        # Etiqueta con info de la cuenta
        self.account_label = tb.Label(self.sync_tab, text=self.get_account_info(), bootstyle="secondary", font=("Segoe UI", 10))
        self.account_label.pack(pady=20, padx=20)

        # Botón para cambiar de cuenta
        btn_change_account = tb.Button(
        self.sync_tab, text="🔄 Cambiar cuenta", bootstyle="warning-outline", command=self.change_account)
        btn_change_account.pack(pady=10, padx=20)
        
    # === Funciones de sincronización ===
    def save_sync_setting(self):
        datafiles.config.setdefault("global", {})["cloud_sync_enabled"] = self.auto_sync_var.get()
        if not datafiles.config["global"]["email"]:
            self.recall_token(True)
            
    # === Funciones de cuenta ===
    def get_account_info(self):
        if datafiles.config["global"]["email"]:
            return datafiles.config["global"]["email"]
        return "desconocido"

    def change_account(self):
        ConfirmDialog(self, title="Deberas volver a iniciar sesion", message= "¿Estas seguro?", callback=self.recall_token).place(relx=0.5, rely=0.5, anchor="center")

    def recall_token(self, respond):
        if respond:
            self.destroy()
        if not respond:
            self.destroy()
            
        def worker():
            if respond:
                token_path = datafiles.DATA_DIR / "token.json"

                if not datafiles.config["global"]["cloud_sync_enabled"]:
                    datafiles.config.setdefault("global", {})["cloud_sync_enabled"] = True
                    # actualizar variable de Tkinter desde el hilo principal
                    self.root.after(0, lambda: self.auto_sync_var.set(True))
                
                if token_path.exists():
                    token_path.unlink()
                
                try:
                    service, creds = get_drive_service()
                except Exception:
                    return
                
                self.service = service
                self.parent.service = self.service
                datafiles.config["global"]["email"] = self.get_user_email(creds)
                Loader.save_config()

                # actualizar label en el hilo principal
                account_text = self.get_account_info()
                self.root.after(0, lambda: self.account_label.config(text=account_text))

        threading.Thread(target=worker, daemon=True).start()
            
    def get_user_email(self, creds):
        service = build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        return user_info.get("email", "desconocido")

    
def call_populate(platform_name, target):
    def worker():
        all_data = [collect_platform_data(platform_name)]
        # Una vez listo, volvés al hilo principal
        target.after(0, lambda: populate_ui(all_data, target))

    threading.Thread(target=worker, daemon=True).start()

def populate_ui(all_data, target, select_new= True):
    def fill_tree(tree, grouped):     
        """Configura y llena un Treeview con los juegos agrupados"""
        tree.delete(*tree.get_children())
        tree.configure(columns=("name",))
        tree.column("#0", width=35, stretch=False)
        tree.column("name", anchor="w", width=200)
        tree.heading("name", text="Nombre del juego")

        if not hasattr(tree, "icon_images"):
            tree.icon_images = {}
        
        for g in grouped:
            tree.icon_images[g["name"]] = g["icon"]
            tree.insert("", "end", iid=g["name"], text="", image=g["icon"], values=(g["name"],))
            
        #Favoritos
        #fav_node = tree.insert("", "end", text="★ Favoritos", open=True)
        #for g in pdata["favorites"]:
            #tree.icon_images[g["name"]] = g["icon"]
            #tree.insert(fav_node, "end", iid=g["name"], text="", image=g["icon"], values=(g["name"],))

        # Recientes
        #rec_node = tree.insert("", "end", text="⏱ Recientes", open=False)
        #for g in pdata["recent"]:
            #tree.icon_images[g["name"]] = g["icon"]
            #tree.insert(rec_node, "end", iid=g["name"], text="", image=g["icon"], values=(g["name"],))
                
        # Por mes
        #for month, juegos in pdata["by_month"].items():
            #node = tree.insert("", "end", text=f"📆 {month}", open=False)
            #for g in juegos:
                #tree.icon_images[g["name"]] = g["icon"]
                #tree.insert(node, "end", iid=g["name"], text="", image=g["icon"], values=(g["name"],))"""
            
    for pdata in all_data:
        platform_name = pdata["platform"]
        
        
        # Caso 1: target es un Treeview directo
        if isinstance(target, ttk.Treeview):
            is_tree = True
            fill_tree(target, pdata["grouped"])

        # Caso 2: target es un Notebook
        else:
            existing_tab = None
            is_tree = False
            for tab_id in target.tabs():
                if target.tab(tab_id, "text") == platform_name:
                    existing_tab = tab_id
                    break

            if existing_tab:
                platform_frame = target.nametowidget(existing_tab)
                tree = platform_frame.game_tree
                if select_new:
                    target.select(existing_tab)
            else:
                platform_frame = GamePlatformFrame(target, platform_name)
                target.add(platform_frame, text=platform_name)
                target.platform_trees[platform_name] = platform_frame.game_tree
                tree = platform_frame.game_tree
                if select_new:
                    target.select(platform_frame)
                    
                target.save_tab_order()
            
            fill_tree(tree, pdata["grouped"])
        
        if not is_tree:
            target.emptyframe()
        
        if not select_new:    
            last_tab = datafiles.config["global"].get("last_selected_tab")
            if last_tab:
                for tab_id in target.tabs():
                    if target.tab(tab_id, "text") == last_tab:
                        target.select(tab_id)
                        break