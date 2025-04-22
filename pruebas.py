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
from tkinter import filedialog, messagebox, ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import datetime
from PIL import Image, ImageTk


BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
launched = False
# Cargar configuración
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = {}

class DraggableNotebook(tb.Notebook):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._active = None
        self.tab_order = []
        self.img = Image.open("no_icon.ico").resize((16, 16), Image.LANCZOS)
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
        self.menu_in.add_command(label="Eliminar plataforma", command=self.remove_tab)
        self.menu_in.add_command(label="Agregar plataforma", command= lambda: self.new_platform(False))
       
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
    
    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def reload(self, reload):
        for platforms in config:
            self.add_platform(platforms, reload)

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
    
    def goto_folder(self, path_listbox): 
        selected = path_listbox.curselection()
        if selected:
            game_path_selected = path_listbox.get(selected[0])      
            if game_path_selected:
                os.startfile(game_path_selected)
            else:
                messagebox.showwarning("Atención", "No se pudo encontrar el Directorio")
        else:
            messagebox.showwarning("Atención", "Selecciona un Directorio")

    def remove_folder(self, platform_name, path_listbox, game_tree): # elimina el directorio DE LA LISTA
        selected = path_listbox.curselection()
        if selected:
            path = path_listbox.get(selected[0])
        
            for games, paths in config[platform_name]["game_list"].copy().items():
                if path in paths:
                    del config[platform_name]["game_list"][games]
        
            for platforms in config[platform_name]["platform_folders"].copy():
                if path == platforms:
                    config[platform_name]["platform_folders"].remove(path)

        
            path_listbox.delete(selected[0])
            self.update_game_list(platform_name, game_tree)
            self.save_config()
        else: 
            messagebox.showwarning("Atención", "Selecciona un directorio para eliminar de la lista")

    def update_game_list(self, platform_name, game_tree):
        game_tree.delete(*game_tree.get_children())
        
        game_tree.configure(columns=("name",))
        game_tree.column("#0", width=35, stretch=False)  # Solo para el ícono
        game_tree.column("name", anchor="w", width=200)
        game_tree.heading("name", text="Nombre del juego")
        
        game_list = config[platform_name]["game_list"]

        # Asegurate de guardar las imágenes para que no se borren
        if not hasattr(game_tree, "icon_images"):
            game_tree.icon_images = {}
            
        for name, path in game_list.items():
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

    def update_directory_list(self, platform_name, path_listbox): # recible el path_list y lo "actualiza"
        path_listbox.delete(0, tk.END)
        paths = config[platform_name]["platform_folders"]
        for path in paths:
            path_listbox.insert(tk.END, f"{path}")

    def launch_game(self, platform_name, game_tree): # lanza el ejecutable seleccionado
        if not launched:
            selected = game_tree.selection()
            if selected:
                item_id = selected[0]
                game_name = game_tree.item(item_id, "values")[0]
                game_path = config[platform_name]["game_list"].get(game_name)
                if game_path:
                    launch_game_threaded(platform_name, game_name, game_path)
                else:
                    messagebox.showwarning("Atención", "No se pudo encontrar el juego")
            else:
                messagebox.showwarning("Atención", "Selecciona un juego para lanzar")             
    
    def add_exe(self, platform_name, game_tree):
        exe = filedialog.askopenfilename(title="Selecciona un ejecutable")
        if exe:
            exe_name = os.path.splitext(os.path.basename(exe))[0]
            
            platform = config.setdefault(platform_name, {})
            game_list = platform.setdefault("game_list", {})
            
            game_list[exe_name] = exe
            self.save_config()
            self.update_game_list(platform_name, game_tree)
                
        
    def remove_exe(self, platform_name, game_tree): # elimina el ejecutable DE LA LISTA
        selected_items = game_tree.selection()
        if selected_items:
            for item_id in selected_items:
                game_name = game_tree.item(item_id, "values")[0]  # El texto del ítem (nombre del juego)
                config[platform_name]["game_list"].pop(game_name, None)
                config[platform_name].get("game_times", {}).pop(game_name, None)
                config[platform_name].get("game_total_times").pop(game_name, None)
                game_tree.delete(item_id)
                self.save_config()
        else:
            messagebox.showwarning("Atención", "Selecciona un juego para eliminar de la lista")


    def new_platform(self, reload): # agrega una pestaña nueva en el notebook con el nombre de la plataforma ingresado por el usuario
        platform_name = simpledialog.askstring("Nueva Plataforma", "Nombre de la Plataforma:")
        self.add_platform(platform_name, reload)
        if platform_name:
            if self.empty_frame.winfo_ismapped():
                self.empty_frame.pack_forget()
        
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

        
    def add_platform(self, platform_name, reload): # crea todo el notebook con las pestañas y listboxes necesarios para mostrar los juegos y directorios
        if platform_name:
            if not reload:
                folder= self.add_folder(platform_name)
            else:
                self.empty_frame.pack_forget()
                folder= True
        
            if folder:
                # Pestaña Principal
                frame = ttk.Frame(self)
                self.add(frame, text= platform_name)
                self.select(frame)

                # Configuración de layout del frame principal
                frame.rowconfigure(1, weight=1)
                frame.columnconfigure(0, weight=1)
                

                # Sub Pestañas
                notebook_sub = ttk.Notebook(frame)
                notebook_sub.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

                # pestaña juegos
                frame_games = ttk.Frame(notebook_sub)
                notebook_sub.add(frame_games, text="Juegos")

                frame_games.rowconfigure(0, weight=1)
                frame_games.columnconfigure([0, 1], weight=1)
        
                game_tree = ttk.Treeview(frame_games, show="tree", selectmode="browse", height=15)
                game_tree.grid(row=0, column=0, columnspan=2, padx=2, pady=5, sticky="nsew")
        
                game_tree.bind("<Double-Button-1>", lambda event: self.double_click_on_game_event(event, platform_name, game_tree))
                game_tree.bind("<Button-1>", lambda event: self.on_game_click(event, game_tree))
                game_tree.bind("<Button-3>", lambda event: self.on_game_right_click(event, platform_name, game_tree))
        
                btn_launch_exe = tk.Button(frame_games, text="Lanzar Juego", command= lambda: self.launch_game(platform_name, game_tree), bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'))
                btn_launch_exe.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        
                btn_remove_exe = tk.Button(frame_games, text="Eliminar Juego", command= lambda: self.remove_exe(platform_name, game_tree), bg='#f44336', fg='white', font=('Arial', 12, 'bold'))
                btn_remove_exe.grid(row=1, column=1, padx=2, pady=2, sticky="ew")

                # Pestaña de directorios
                frame_path = ttk.Frame(notebook_sub)
                notebook_sub.add(frame_path, text="Directorios")

                frame_path.rowconfigure(0, weight=1,)
                frame_path.columnconfigure([0, 1], weight=1)
        
                path_listbox = tk.Listbox(frame_path, width=60, height=15)
                path_listbox.grid(row=0, column=0, columnspan=2, padx=2, pady=5, sticky="nsew")

                path_listbox.bind("<Double-Button-1>", lambda event: self.double_click_on_path_event(event, path_listbox))
                path_listbox.bind("<Button-1>", lambda event: self.on_path_click(event, path_listbox))
                path_listbox.bind("<Button-3>", lambda event: self.on_path_right_click(event, platform_name, path_listbox, game_tree))

                btn_add_dir = tk.Button(frame_path, text="Agregar Directorio", command= lambda: self.btn_new_path(platform_name, game_tree, path_listbox), bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'))
                btn_add_dir.grid(row=1, column=0, padx=2, pady=2, sticky="ew")

                btn_remove_dir = tk.Button(frame_path, text="Eliminar Directorio", command= lambda: self.remove_folder(platform_name, path_listbox, game_tree), bg='#f44336', fg='white', font=('Arial', 12, 'bold'))
                btn_remove_dir.grid(row=1, column=1, padx=2, pady=2, sticky="ew")
        
                self.update_game_list(platform_name , game_tree)
                self.update_directory_list(platform_name, path_listbox)
        
    def remove_tab(self): # elimina una pestaña (plataforma) seleccionada de el notebook y tambien la borra de la lista junto con todo su contenido
        if self._active is not None:
            platform_name= self.tab(self._active, option="text")
            confirm = Messagebox.yesno(title="Eliminar pestaña", message=f"¿Estás seguro de que querés eliminar la pestaña '{platform_name}'?", alert=True, parent=self)
            if confirm == "Yes":
                index_to_select = self._active - 1 if self._active > 0 else 0
                self.remove_platform(platform_name)
                self.forget(self._active)
                tabs= self.tabs()
                if tabs:
                    self.select(index_to_select)
            self._active = None
        if len(self.tabs()) == 0:
            self.empty_frame.pack(fill="both", expand=True)
    
    def remove_platform(self, platform_name): # trabaja en conjunto con remove_tab, esto es lo que borra la plataforma de la lista
        del config[platform_name]
        self.save_config()
        
    def on_game_click(self, event, game_tree): 
        item_id = game_tree.identify_row(event.y) 

        if item_id:
            game_tree.selection_set(item_id) # selecciona el item clickeado
            
        else:
            # Clic fuera de cualquier ítem → prevenimos selección
            game_tree.selection_remove(game_tree.selection())
            return "break"  # Esto cancela el comportamiento por defecto

    def double_click_on_game_event(self, event, platform_name, game_tree):
        item_id = game_tree.identify_row(event.y)
        
        if item_id: 
                self.launch_game(platform_name, game_tree)
                return

        game_tree.selection_clear(0, tk.END)

    def on_game_right_click_out(self, event, platform_name, game_tree):
        game_tree.selection_remove(*game_tree.selection())  # Limpiar cualquier selección anterior
        menu= tb.Menu(self, tearoff=0) 
        menu.add_command(label="Agregar Juego", command= lambda: self.add_exe(platform_name, game_tree))
        # Obtener las coordenadas del puntero
        x, y = event.x_root, event.y_root
        # Mostrar el menú en la posición del puntero
        menu.post(x, y)        
    
    def on_game_right_click(self, event, platform_name, game_tree):
        item_id = game_tree.identify_row(event.y)
        
        if item_id:          
            # Obtener el nombre del juego desde el ítem seleccionado
            game_tree.selection_set(item_id)
            game = game_tree.item(item_id)["values"][0]
            game_exe_path = config[platform_name]["game_list"][game] 
            
            # Crea menú contextual
            menu = tb.Menu(self, tearoff=0)  # tearoff=0 evita la opción "desgarrar" el menú

            # Opciones del menú contextual
            menu.add_command(label= "Lanzar juego", command=lambda: self.launch_game(platform_name, game_tree))
            menu.add_command(label= "Crear acceso directo", command=lambda: self.create_direct_access(game, platform_name, os.path.abspath(sys.argv[0]), game_exe_path, destino_desktop=True))
            menu.add_command(label= "Eliminar juego", command=lambda: self.remove_exe(platform_name, game_tree))
    
            # Obtener las coordenadas del puntero
            x, y = event.x_root, event.y_root
            # Mostrar el menú en la posición del puntero
            menu.post(x, y)
        else:
            self.on_game_right_click_out(event, platform_name, game_tree)
                   
    def on_path_click(self, event, path_listbox):
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
    
    def double_click_on_path_event(self, event, path_listbox):
        index = path_listbox.nearest(event.y)  # Devuelve el índice más cercano al clic
        bbox = path_listbox.bbox(index)         
        if bbox:
            x, y, width, height = bbox
            if event.y >= y and event.y <= y + height:        
                path_listbox.selection_clear(0, tk.END)  # Limpiar por si acaso
                path_listbox.selection_set(index)        # Asegurar selección                
                self.goto_folder(path_listbox)
    
    def on_path_right_click_out(self, event, platform_name, game_tree, path_listbox):
        menu = tb.Menu(self, tearoff=0) 
        menu.add_command(label= "Agregar directorio", command=lambda: self.btn_new_path(platform_name, game_tree, path_listbox))
        x, y = event.x_root, event.y_root
        menu.post(x, y)
        
    def on_path_right_click(self, event, platform_name, path_listbox, game_tree):
        index = path_listbox.nearest(event.y)  # Devuelve el índice más cercano al clic
        bbox = path_listbox.bbox(index)        # Da las coordenadas del ítem
    
        if bbox:
            x, y, width, height = bbox
            bool= False
            if event.y >= y and event.y <= y + height:
                # Seleccionamos el ítem clickeado
                path_listbox.selection_clear(0, tk.END)  # Limpiar cualquier selección anterior
                path_listbox.selection_set(index)        # Seleccionar el ítem clickeado
                # Crea menú contextual
                menu = tb.Menu(self, tearoff=0)  # tearoff=0 evita la opción "desgarrar" el menú

                # Opciones del menú contextual
                menu.add_command(label= "Ir a carpeta local", command=lambda: self.goto_folder(platform_name, path_listbox))
                menu.add_command(label= "Eliminar directorio", command=lambda: self.remove_folder(platform_name, path_listbox, game_tree))
    
                # Obtener las coordenadas del puntero
                x, y = event.x_root, event.y_root
    
                # Mostrar el menú en la posición del puntero
                menu.post(x, y)
            else:
                self.on_path_right_click_out(event, platform_name, game_tree, path_listbox)
        else:
            self.on_path_right_click_out(event, platform_name, game_tree, path_listbox)

    def btn_new_path(self, platform_name, game_tree, path_listbox):
        self.add_folder(platform_name)
        self.update_game_list(platform_name, game_tree)
        self.update_directory_list(platform_name, path_listbox)    

def launch_game_threaded(platform_name, game_name, game_path):     
    def execute():   
        launched = True
        start = time.time()
        process = subprocess.Popen(game_path)
        process.wait()
        end = time.time()
        launched = False
        dur_min = (end - start) / 60
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_session = {"Start": now, "Tiempo": round(dur_min, 2)}
            
        game_times = config[platform_name].setdefault("game_times", {})
        game_times.setdefault(game_name, []).append(new_session)
            
        game_total_times= config[platform_name].setdefault("game_total_times", {})
        game_total_times.setdefault(game_name, 0.0)
        game_total_times[game_name] += round(dur_min, 2)
                 
            
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        
    thread = threading.Thread(target= execute)
    thread.start()

def extract_icon(path, size=(16, 16)):
    # Extrae ícono del archivo
    large, small = win32gui.ExtractIconEx(path, 0)
    if small:
        hicon = small[0]
    elif large:
        hicon = large[0]
    else:
        return None

    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
    hbmp = win32ui.CreateBitmap()
    hbmp.CreateCompatibleBitmap(hdc, size[0], size[1])
    hdc_mem = hdc.CreateCompatibleDC()
    hdc_mem.SelectObject(hbmp)
    win32gui.DrawIconEx(hdc_mem.GetHandleOutput(), 0, 0, hicon, size[0], size[1], 0, None, win32con.DI_NORMAL)

    bmpinfo = hbmp.GetInfo()
    bmpstr = hbmp.GetBitmapBits(True)
    image = Image.frombuffer("RGB", (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
    image = image.resize((16,16), Image.LANCZOS)
    return ImageTk.PhotoImage(image)


def main():
    if "--launch" in sys.argv and "--platform" in sys.argv:
        game_name = sys.argv[sys.argv.index("--launch") + 1]
        platform_name = sys.argv[sys.argv.index("--platform") + 1]
        game_path = config.get(platform_name, {}).get("game_list", {}).get(game_name)
        if game_path:
            if not launched:
                launch_game_threaded(platform_name, game_name, game_path)
        else:
            print("No se encontró el juego.")
    else:
        # Mostrar la interfaz
        root = tb.Window(themename="darkly")
        root.title("Game Launcher")
        root.iconbitmap("icono.ico")
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