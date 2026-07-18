from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLineEdit, QTabWidget, QLabel, QPushButton, QScrollArea,
    QFileDialog, QTreeWidget, QTreeWidgetItem,
    QInputDialog, QApplication, QFrame, QSizePolicy, QDialog,
    QCheckBox
)

from PySide6.QtCore import Qt, QSize, QObject, QThread, Signal, QTimer

from PySide6.QtGui import QShortcut, QKeySequence

import sys
from pathlib import Path
import logging

from data_access.datafiles import DATA_DIR, THEMES_DIR, TOKEN_PATH, db
from data_access.cloudsync import login_and_sync, call_merge

from helpers.safe_threading import safe_thread
from helpers.file_manager import FileManager
from helpers.data_manager import DataManager
from helpers.games_launcher import GameLauncherController
from helpers.qicon_utils import load_qicon

from platform_adapters.platform_handler import PlatformHandler

from .qt_popups import InputDialog, ConfirmDialog, CustomPopupMenu


# Panel de favoritos
class FavoritesPanel(QWidget):
    """
    Muestra los juegos favoritos de la plataforma con ícono, nombre,
    horas totales y botón de play rápido.
    Se refresca llamando a refresh() (ej: al marcar/desmarcar favorito).
    """
 
    def __init__(self, platform_name: str, parent=None):
        super().__init__(parent)
        self.platform_name = platform_name
        self.setObjectName("favoritesPanel")
 
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(0)
 
        # Título
        title = QLabel("★  Tus Favoritos")
        title.setObjectName("favoritesPanelTitle")
        root.addWidget(title)
 
        # Área scrolleable para las filas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
 
        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(0, 12, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()
 
        scroll.setWidget(self._container)
        root.addWidget(scroll, stretch=1)
 
        self.refresh()
 
    # ------------------------------------------------------------------
    def refresh(self):
        """Limpiar y repoblar la lista de favoritos."""
        # Borrar filas anteriores (respetando el stretch final)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
 
        favorites = db.get(f"{self.platform_name}.favorites", default=[]) or []
        game_list = db.get_children(f"{self.platform_name}.game_list") or {}
 
        if not favorites:
            lbl = QLabel("No tenés juegos favoritos aún.")
            lbl.setObjectName("emptyHint")
            lbl.setAlignment(Qt.AlignCenter)
            self._list_layout.insertWidget(0, lbl)
            return
 
        for i, game_name in enumerate(favorites):
            path = game_list.get(game_name)
            if not path:
                continue
            row = self._build_row(game_name, path)
            self._list_layout.insertWidget(i, row)
 
    # ------------------------------------------------------------------
    def _build_row(self, game_name: str, path: str) -> QWidget:
        row = QWidget()
        row.setObjectName("favoriteRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)
 
        # Ícono
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        icon_label.setScaledContents(True)
        qicon_Path = PlatformHandler().get("icons").get_icon(path) #lo cachea, si ya existe devuelve el path al cacheado
        qicon = load_qicon(qicon_Path)
        if qicon and not qicon.isNull():
            icon_label.setPixmap(qicon.pixmap(24, 24))

        layout.addWidget(icon_label)
 
        # Nombre
        name_lbl = QLabel(game_name)
        name_lbl.setObjectName("favoriteGameName")
        layout.addWidget(name_lbl)
 
        layout.addStretch()
 
        # Horas totales
        times = db.get_children(
            f"{self.platform_name}.game_total_times.{game_name}"
        ) or {}
        total_minutes = sum(times.values())
        hours_lbl = QLabel(f"{round(total_minutes / 60, 2)} hs")
        hours_lbl.setObjectName("favoriteGameHours")
        layout.addWidget(hours_lbl)
 
        # Botón play
        btn_play = QPushButton("▶")
        btn_play.setObjectName("btnPlaySmall")
        btn_play.setFixedWidth(32)
        # Captura del nombre en el closure
        btn_play.clicked.connect(lambda _=False, n=game_name: self._launch(n))
        layout.addWidget(btn_play)
 
        return row
 
    def _launch(self, game_name: str):
        GameLauncherController().launch_game(game_name)

# Panel de detalles de un juego (panel derecho)
class GameDetailPanel(QWidget):
    def __init__(self, platform_name: str, parent=None):
        super().__init__(parent)
        self.platform_name = platform_name
        self.current_game = None
        self.parent = parent #es una pestaña
        db.ensure(f"{platform_name}.favorites", [])
        self.setObjectName("gameDetailPanel")
 
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
 
        # ── Barra superior ──────────────────────────────────────────────
        self.top_bar = QWidget()
        self.top_bar.setObjectName("detailTopBar")
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(10)
 
        self.btn_play = QPushButton("▶  Jugar")
        self.btn_play.setObjectName("btnPlay")
        self.btn_play.setFixedWidth(110)
        self.btn_play.clicked.connect(self._launch_game)
        top_layout.addWidget(self.btn_play)
 
        # Ícono + nombre + tiempo
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setScaledContents(True)
        top_layout.addWidget(self.icon_label)
 
        self.name_label = QLabel()
        self.name_label.setObjectName("gameNameLabel")
        top_layout.addWidget(self.name_label)
 
        top_layout.addStretch()
 
        # Botones derecha
        self.btn_notes    = QPushButton("⋯")
        self.btn_favorite = QPushButton("★")
        self.btn_settings = QPushButton("⚙")
        for btn in (self.btn_notes, self.btn_favorite, self.btn_settings):
            btn.setFixedWidth(36)
            btn.setObjectName("btnIconAction")
            top_layout.addWidget(btn)
 
        self.btn_notes.clicked.connect(self._open_notes)
        self.btn_favorite.clicked.connect(self._toggle_favorites)
        self.btn_settings.clicked.connect(self._show_props_menu)
 
        root_layout.addWidget(self.top_bar)
 
        # ── Separador ───────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("detailSeparator")
        root_layout.addWidget(sep)
 
        # ── Área de sesiones (scrolleable) ──────────────────────────────
        self.sessions_label = QLabel("Últimas sesiones:")
        self.sessions_label.setObjectName("sectionTitle")
        self.sessions_label.setContentsMargins(16, 12, 0, 4)
        root_layout.addWidget(self.sessions_label)
 
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
 
        self.sessions_container = QWidget()
        self.sessions_layout = QVBoxLayout(self.sessions_container)
        self.sessions_layout.setContentsMargins(20, 4, 20, 12)
        self.sessions_layout.setSpacing(4)
        self.sessions_layout.addStretch()
 
        scroll.setWidget(self.sessions_container)
        root_layout.addWidget(scroll, stretch=1)
 
    # ------------------------------------------------------------------
    # API pública: actualizar el panel con un juego nuevo
    # ------------------------------------------------------------------
    def show_game(self, game_name: str, icon: QIcon = None):
        self.current_game = game_name
 
        # Tiempo total
        times = db.get_children(
            f"{self.platform_name}.game_total_times.{game_name}"
        ) or {}
        total_minutes = sum(times.values())
        hours = round(total_minutes / 60, 2)
        time_str = f"  —  {hours} hs" if total_minutes else ""
 
        # Nombre + tiempo
        self.name_label.setText(f"{game_name}{time_str}")
 
        # Ícono
        if icon and not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(24, 24))
        else:
            self.icon_label.clear()
 
        # Sesiones
        sessions = db.get(
            f"{self.platform_name}.game_times.{game_name}", default=[]
        ) or []
        self._populate_sessions(sessions)
 
    # ------------------------------------------------------------------
    # Poblar lista de sesiones
    # ------------------------------------------------------------------
    def _populate_sessions(self, sessions: list):
        # Limpiar sesiones anteriores (sin tocar el stretch del final)
        while self.sessions_layout.count() > 1:
            item = self.sessions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
 
        if not sessions:
            empty = QLabel("Sin sesiones registradas")
            empty.setObjectName("emptyHint")
            self.sessions_layout.insertWidget(0, empty)
            return
 
        for i, session in enumerate(reversed(sessions)):  # últimas 20
            row = self._build_session_row(i, session)
            self.sessions_layout.insertWidget(i, row)
 
    def _build_session_row(self, index: int, session) -> QWidget:
        row = QWidget()
        row.setObjectName("sessionRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 4, 8, 4)
 
        total_time = session['Tiempo']
        hours = int(total_time // 60)
        minutes = int(total_time % 60)
        formatted = f"{hours} horas : {minutes} minutos"
 
        lbl_date = QLabel(f"{session['Start']}")
        lbl_date.setObjectName("sessionDate")
 
        lbl_dur = QLabel(f"{formatted}")
        lbl_dur.setObjectName("sessionDuration")
        lbl_dur.setAlignment(Qt.AlignRight)
 
        layout.addWidget(lbl_date)
        layout.addStretch()
        layout.addWidget(lbl_dur)
 
        return row
 
    # ------------------------------------------------------------------
    # Acciones de los botones (stubs — conectar con tu lógica)
    # ------------------------------------------------------------------
    def _launch_game(self):
        if self.current_game:
            GameLauncherController().launch_game(self.current_game)
            pass
 
    def _open_notes(self):
        pass
 
    def _toggle_favorites(self):
        game_name = self.current_game
        platform_name = self.platform_name
        favorites = db.get(f"{platform_name}.favorites", False)

        if game_name in favorites:
            new_favs = [g for g in favorites if g != game_name]
            db.set(f"{platform_name}.favorites", new_favs)

        else:
            new_favs = favorites + [game_name]
            db.set(f"{platform_name}.favorites", new_favs)
        
        self.parent.favorites_panel.refresh()
 
    def _show_props_menu(self):
        pass
 
#arbol deseleccionable
class ClearableTreeWidget(QTreeWidget):
    cleared = Signal()  # se emite cuando el usuario hace click en vacío
 
    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None:
            self.clearSelection()
            self.setCurrentItem(None)
            self.cleared.emit()
        super().mousePressEvent(event)

# Tab de una plataforma: sidebar + panel derecho con QStackedWidget
class PlatformTab(QWidget):
    def __init__(self, platform_name: str, parent=None):
        super().__init__(parent)
        self.platform_name = platform_name
        self.file_manager = FileManager()
 
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
 
        sidebar = self._build_sidebar()
        sidebar.setFixedWidth(260)
 
        # Stack: 0 = favoritos, 1 = detalle de juego
        self.right_stack = QStackedWidget()
        self.detail_panel = GameDetailPanel(platform_name, self)
        self.favorites_panel = FavoritesPanel(platform_name)
        self.right_stack.addWidget(self.favorites_panel)  # 0
        self.right_stack.addWidget(self.detail_panel)      # 1
 
        layout.addWidget(sidebar)
        layout.addWidget(self.right_stack)
 
        self.games_tree.itemClicked.connect(self._on_game_clicked)
        self.games_tree.itemDoubleClicked.connect(self._on_game_double_clicked)
        self.games_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.games_tree.customContextMenuRequested.connect(self._on_game_right_click)

        supr_shortcut = QShortcut(QKeySequence("Delete"), self.games_tree)
        supr_shortcut.activated.connect(self._delete_selected_item)
 
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
 
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar juegos...")
        self.search_bar.textChanged.connect(self._filter_games)
        layout.addWidget(self.search_bar)
 
        self.games_tree = ClearableTreeWidget() 
        self.games_tree.cleared.connect(lambda: self.right_stack.setCurrentIndex(0))
        self.games_tree.setHeaderLabels(["Juegos"])
        self.games_tree.setColumnCount(1)
        self.games_tree.setIndentation(16)
        self.games_tree.setIconSize(QSize(20, 20))
        layout.addWidget(self.games_tree)
 
        return sidebar
    
    def _on_game_clicked(self, item: QTreeWidgetItem, _col: int):
        self.detail_panel.show_game(item.text(0), item.icon(0))
        self.right_stack.setCurrentIndex(1)

    def _on_game_double_clicked(self, item:QTreeWidgetItem, _col: int):
        GameLauncherController().launch_game(item.text(0))

    def _on_game_right_click(self, pos):
        game = self.games_tree.itemAt(pos)
        if game is None:
            return  # click derecho en espacio vacío, no mostrar nada

        # opcional: seleccionar el item antes de mostrar el menú,
        # para que quede claro sobre cuál vas a actuar
        self.games_tree.setCurrentItem(game)

        game_name = game.text(0)
        global_pos = self.games_tree.viewport().mapToGlobal(pos)

        menu = CustomPopupMenu(self, on_close_callback=None)
        menu.add_button("Jugar",          command=lambda: self._on_game_double_clicked(item, 0))
        menu.add_button("Abrir carpeta",  command=lambda: self._open_game_folder(game_name))
        menu.add_button("Eliminar",       command=self._delete_selected_item)
        
        menu.show_at(global_pos, offset_x=2, offset_y=84)
   
    # ------------------------------------------------------------------
    def fill_games(self, games: list):
        self.games_tree.clear()
        self._all_games = games
        for game in games:
            self._add_game_item(game)
 
    def _add_game_item(self, game: dict):
        item = QTreeWidgetItem([game["name"]])
        if game.get("icon"):
            item.setIcon(0, load_qicon(game["icon"]))
        self.games_tree.addTopLevelItem(item)
    
    def _delete_selected_item(self):
        removed = False
        item = self.games_tree.currentItem()
        if item is None:
            return
        
        platform_name = self.platform_name
        game_name = item.text(0)

        parent = item.parent()
        if parent is None:
            index = self.games_tree.indexOfTopLevelItem(item)
            self.games_tree.takeTopLevelItem(index)
            removed = True
        else:
            parent.removeChild(item)
            removed = True 

        if removed:
            game_path = db.get(f"{platform_name}.game_list.{game_name}")
            self.file_manager.remove_game_icon(game_path)
            
            db.delete(f"{platform_name}.game_list.{game_name}")
            db.delete(f"{platform_name}.game_times.{game_name}")
            db.delete(f"{platform_name}.game_total_times.{game_name}")
            favorites = db.get(f"{platform_name}.favorites", [])
            if game_name in favorites:
                favorites.remove(game_name)
                db.set(f"{platform_name}.favorites", favorites)
        
        self.right_stack.setCurrentIndex(0)

        QTimer.singleShot(0, self.games_tree.clearSelection)
        QTimer.singleShot(0, lambda: self.games_tree.setCurrentItem(None))

    def _filter_games(self, text: str):
        text = text.lower().strip()
        for i in range(self.games_tree.topLevelItemCount()):
            item = self.games_tree.topLevelItem(i)
            item.setHidden(text not in item.text(0).lower())
 
# clouding
class CloudSettingsWindow(QDialog):
    login_finished = Signal(bool)  # ok, email

    def __init__(self, parent, on_close_callback=None):
        super().__init__(parent)
        self.setObjectName("cloudSettingsWindow")
        self.setWindowTitle("Configuración de nube")
        self.parent_window = parent
        self.on_close_callback = on_close_callback

        self.login_finished.connect(self._on_login_finished)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.chk_sync = QCheckBox("Habilitar sincronización automática")
        self.chk_sync.setChecked(db.get("global.cloud_sync_enabled", default=False))
        self.chk_sync.toggled.connect(self._toggle_clouding)
        layout.addWidget(self.chk_sync)

        self.account_label = QLabel(self._get_account_info())
        self.account_label.setObjectName("cloudAccountLabel")
        layout.addWidget(self.account_label)

        self.btn_change_account = QPushButton("🔄 Cambiar cuenta")
        self.btn_change_account.clicked.connect(self._change_account)
        layout.addWidget(self.btn_change_account)

    # ------------------------------------------------------------------
    def _toggle_clouding(self, checked):
        db.set("global.cloud_sync_enabled", checked)
        if checked and db.get("global.email") is None:
            self._confirm("Serás redirigido al navegador", "¿Estás seguro?", self._recall_token)

    def _change_account(self):
        title = "Deberás volver a iniciar sesión" if db.get("global.email") is not None \
            else "Serás redirigido al navegador"
        self._confirm(title, "¿Estás seguro?", self._recall_token)

    def _confirm(self, title, message, callback):
        dlg = ConfirmDialog(self, title=title, message=message, callback=callback)
        dlg.exec()

    # ------------------------------------------------------------------
    def _recall_token(self, respond: bool):
        if not respond:
            return
        
        self.chk_sync.setEnabled(False) # bloqueamos mientras corre el login
        self.btn_change_account.setEnabled(False)

        def worker():
            if not db.get("global.cloud_sync_enabled"):
                db.set("global.cloud_sync_enabled", True)
            
            try:
                loged_in = login_and_sync(force_new_account=True)

            except Exception:
                logging.exception("Fallo el login/merge de cloud")  
                self.login_finished.emit(False)
                return
            
            self.login_finished.emit(loged_in)

        safe_thread(worker)

    def _on_login_finished(self, ok: bool):
        self.chk_sync.setEnabled(True) #login terminado, desbloqueamos
        self.btn_change_account.setEnabled(True)
        if not ok:
            return
        self.account_label.setText(self._get_account_info())
        self.parent_window.update_title_label()
        self.accept()
    
    def _get_account_info(self):
        return db.get("global.email") 

# Ventana principal
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CLauncher69 - V2")
        self.setMinimumSize(1200, 700)
        self.file_manager = FileManager()
 
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
 
        root_layout.addWidget(self._build_header())
 
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        # --- click derecho sobre las pestañas ---
        self.tab_widget.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab_widget.tabBar().customContextMenuRequested.connect(self._on_tab_context_menu)

        self.empty_label = QLabel("Agregá una plataforma para empezar →")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 18px; color: #666;")
 
        root_layout.addWidget(self.empty_label)
        root_layout.addWidget(self.tab_widget)
        self.tab_widget.hide()
 
        self.setCentralWidget(root)
 
        tab_order = db.get("global.tab_order", default=[]) or []
        if tab_order:
            self.empty_label.setText("Cargando plataformas...")
            reload_with_thread(self, self._on_reload_finished)
 
    # ------------------------------------------------------------------
    def _on_reload_finished(self, all_data: list):
        for data in all_data:
            self._add_platform_tab(data)
 
    def _add_platform_tab(self, data: dict):
        tab = PlatformTab(data["platform"])
        tab.fill_games(data["grouped"])
        self.tab_widget.addTab(tab, data["platform"])
 
        if self.tab_widget.isHidden():
            self.empty_label.hide()
            self.tab_widget.show()
 
    # ------------------------------------------------------------------
    def _build_header(self):
        header = QWidget()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(15, 8, 15, 8)
 
        email = db.get("global.email", default="Desconocido") or "Desconocido"
        self.account_label = QLabel(f"Cuenta: {email}")
        layout.addWidget(self.account_label)
        layout.addStretch()
 
        self.btn_add_platform = QPushButton("Agregar Plataforma")
        self.btn_add_platform.clicked.connect(self.add_platform)
        self.btn_sync = QPushButton("Cloud")
        self.btn_sync.clicked.connect(self._open_cloud_settings)
        layout.addWidget(self.btn_add_platform)
        layout.addWidget(self.btn_sync)
 
        return header
 
    def update_title_label(self):
        email = db.get("global.email")
        self.account_label.setText(f"Cuenta: {email}")
    # ------------------------------------------------------------------
    def add_platform(self):
        result = ask_platform_folder(self)
        if not result:
            return
 
        platform_name, folder = result
        self.file_manager.add_folder(platform_name, folder)
 
        tab_order = db.get("global.tab_order", default=[]) or []
        if platform_name not in tab_order:
            tab_order.append(platform_name)
            db.set("global.tab_order", tab_order)
 
        data = DataManager().collect_platform_data(platform_name)
        self._add_platform_tab(data)
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
 
    def _open_cloud_settings(self):
        dlg = CloudSettingsWindow(self)
        dlg.show()

    # ------------------------------------------------------------------
    def _on_tab_close_requested(self, index: int):
        platform_name = self.tab_widget.tabText(index)
        dlg = ConfirmDialog(
            self,
            title=f"Eliminar {platform_name}",
            message=f"¿Borrar la plataforma '{platform_name}' y todos sus datos?",
            callback=lambda confirmed: self._remove_tab(index, platform_name, confirmed)
        )
        dlg.exec()
 
    def _remove_tab(self, index: int, platform_name: str, confirmed):
        if not confirmed:
            return
 
        game_list = db.get(f"{platform_name}.game_list", default={}) or {}
        for game_path in game_list.values():
            self.file_manager.remove_game_icon(game_path)
 
        db.delete_prefix(platform_name)
        self.tab_widget.removeTab(index)
 
        tab_order = [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]
        db.set("global.tab_order", tab_order)
 
        if self.tab_widget.count() == 0:
            self.tab_widget.hide()
            self.empty_label.show()

    def _on_tab_context_menu(self, pos):
        tab_bar = self.tab_widget.tabBar()
        index = tab_bar.tabAt(pos)  # -1 si clickeaste en espacio vacío de la barra

        if index == -1:
            return  # click derecho fuera de cualquier pestaña, ignorar

        platform_name = self.tab_widget.tabText(index)
        global_pos = tab_bar.mapToGlobal(pos)  # convertir coords locales -> globales

        menu = CustomPopupMenu(self, on_close_callback=None)
        menu.add_button("Renombrar", command=lambda: self._rename_tab(index))
        menu.add_button("Cerrar",    command=lambda: self._on_tab_close_requested(index))
        menu.add_button("Recargar",  command=lambda: self._reload_tab(index))
        menu.show_at(global_pos)
 
# ===========================================================================
# Helpers
# ===========================================================================
def ask_platform_folder(window):
    platform_name, ok = QInputDialog.getText(
        window, "Nombre de la biblioteca", "Ingrese un nombre:"
    )
    if not ok or not platform_name.strip():
        return None
 
    folder = QFileDialog.getExistingDirectory(
        window, "Seleccionar carpeta de juegos", "", QFileDialog.ShowDirsOnly
    )
    if not folder:
        return None
 
    return platform_name.strip(), folder
 
# Worker: carga todas las plataformas guardadas en un hilo separado
class ReloadWorker(QObject):
    finished = Signal(list)   # emite all_data cuando termina
    progress = Signal(str)    # emite mensajes de estado opcionales

    def run(self):
        all_data = []
        tab_order = db.get("global.tab_order", default=[]) or []

        for platform_name in tab_order:
            self.progress.emit(f"Cargando {platform_name}...")
            data = DataManager().collect_platform_data(platform_name)
            all_data.append(data)

        self.finished.emit(all_data)

def reload_with_thread(ui, on_callback):
    ui.worker_thread = QThread()
    ui.worker = ReloadWorker()
    ui.worker.moveToThread(ui.worker_thread)

    ui.worker_thread.started.connect(ui.worker.run)
    ui.worker.finished.connect(on_callback)
    ui.worker.finished.connect(ui.worker_thread.quit)
    ui.worker.finished.connect(ui.worker.deleteLater)
    ui.worker_thread.finished.connect(ui.worker_thread.deleteLater)

    ui.worker_thread.start()

# Entry point
class QtLauncherUI:
    def launch_ui():
        app = QApplication(sys.argv)
        themes_path = Path(THEMES_DIR) / "theme_cyberpunk.qss"
        with open(themes_path, "r") as f:
            app.setStyleSheet(f.read())
        w = MainWindow()
        w.show()
        sys.exit(app.exec())