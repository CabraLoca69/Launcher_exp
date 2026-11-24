from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLineEdit, QTabWidget, QLabel, QPushButton, QScrollArea,
    QFileDialog, QTreeWidget, QTreeWidgetItem,
    QInputDialog, QApplication, QFrame, QSizePolicy, QDialog,
    QCheckBox, QMessageBox, QPlainTextEdit, QDialogButtonBox, QListWidget
)

from PySide6.QtCore import Qt, QSize, QObject, QThread, Signal, QTimer, QPoint

from PySide6.QtGui import QShortcut, QKeySequence, QIcon

import sys
import logging
from pathlib import Path
from datetime import datetime

#--------- imports internos -------
from data_access.cloudsync import call_merge, login_and_sync
from data_access.datafiles import ICONS, THEMES_DIR, store
from data_access.store import Session

from helpers.data_manager import DataManager
from helpers.file_manager import FileManager
from helpers.games_launcher import GameLauncherController
from helpers.qicon_utils import load_qicon
from helpers.safe_threading import safe_thread

from .qt_menus_renderer import QtMenuRenderer
from .qt_popups import InputDialog, ConfirmDialog, CustomPopupMenu
from .ui_handler import get_event_bus

from platform_adapters.platform_handler import PlatformHandler

LIVE_REFRESH_MS = 5000  # refresco del detalle de un juego que está corriendo
EXTERNAL_POLL_MS = 3000  # búsqueda de juegos lanzados desde accesos directos


# label de sesiones, abajo en el mainwindow
class SessionsBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sessions = {}  # game_name -> dict con widgets + start_time
        self.layout_ = QVBoxLayout(self)
        self.hide()  # arranca oculta, como en tk

        bus = get_event_bus()
        bus.game_started.connect(self.add_session)
        bus.game_closed.connect(lambda platform, game_name: self.remove_session(game_name))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_labels)
        self.timer.start(60000)  # cada 60s, como el tk viejo

    def add_session(self, platform_name, game_name):
        if game_name in self.sessions:
            return

        frame = QFrame()
        frame.setObjectName("sessionBarFrame")
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(10)

        name_label = QLabel(f"🎮 {game_name}")
        name_label.setObjectName("sessionBarName")
        frame_layout.addWidget(name_label)

        frame_layout.addStretch()

        time_label = QLabel("🕒 0 min")
        time_label.setObjectName("sessionBarTime")
        frame_layout.addWidget(time_label)

        close_btn = QPushButton("❌")
        close_btn.setObjectName("btnCloseSession")  # reusa el estilo que ya tenés para acciones destructivas
        close_btn.setFixedWidth(30)
        close_btn.clicked.connect(lambda: self.force_close(game_name))
        frame_layout.addWidget(close_btn)

        self.layout_.addWidget(frame)

        session = store.open_session_for(platform_name, game_name)
        start_time = datetime.fromisoformat(session.started_at) if session else datetime.now()

        self.sessions[game_name] = {
            "platform": platform_name,
            "start_time": start_time,
            "time_label": time_label,
            "frame": frame,
        }

        if len(self.sessions) == 1:
            self.show()

        self._update_labels()

    def remove_session(self, game_name):
        session = self.sessions.pop(game_name, None)
        if session:
            session["frame"].deleteLater()
        if not self.sessions:
            self.hide()

    def _update_labels(self):
        for game_name, session in self.sessions.items():
            elapsed = datetime.now() - session["start_time"]
            minutes = int(elapsed.total_seconds() // 60)
            session["time_label"].setText(f"🕒 {minutes} min")

    def force_close(self, game_name):
        platform = self.sessions[game_name]["platform"]
        GameLauncherController().force_close_game(platform, game_name)

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
 
        favorites = store.list_favorites(self.platform_name)
 
        if not favorites:
            lbl = QLabel("No tenés juegos favoritos aún.")
            lbl.setObjectName("emptyHint")
            lbl.setAlignment(Qt.AlignCenter)
            self._list_layout.insertWidget(0, lbl)
            return
 
        for i, game in enumerate(favorites):
            self._list_layout.insertWidget(i, self._build_row(game.name, game.path))
 
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
        hours = store.total_seconds(self.platform_name, game_name) / 3600
        hours_lbl = QLabel(f"{round(hours, 2)} hs")
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
        GameLauncherController().launch_game(game_name, self.platform_name)

# Panel de detalles de un juego (panel derecho)
class GameDetailPanel(QWidget):
    context_menu_requested = Signal(QPoint, bool)
    toggle_favorites = Signal(str)  # game_name

    def __init__(self, platform_name: str, parent=None):
        super().__init__(parent)
        self.platform_name = platform_name
        self.current_game = None
        self.parent = parent #es una pestaña
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

        self._icon: QIcon | None = None
        # Mientras el juego mostrado corre, refresca horas y sesiones
        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._refresh_if_running)
        self._live_timer.start(LIVE_REFRESH_MS)

    def _refresh_if_running(self):
        if self.current_game and store.open_session_for(self.platform_name, self.current_game):
            self.show_game(self.current_game, self._icon)
 
    # ------------------------------------------------------------------
    # API pública: actualizar el panel con un juego nuevo
    # ------------------------------------------------------------------
    def show_game(self, game_name: str, icon: QIcon | None = None):
        self.current_game = game_name
        self._icon = icon
 
        # Tiempo total
        total_s = store.total_seconds(self.platform_name, game_name)
        time_str = f"  —  {round(total_s / 3600, 2)} hs" if total_s else ""
 
        # Nombre + tiempo
        self.name_label.setText(f"{game_name}{time_str}")
 
        # Ícono
        if icon and not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(24, 24))
        else:
            self.icon_label.clear()
 
        # Sesiones
        self._populate_sessions(store.recent_sessions(self.platform_name, game_name))
 
    # ------------------------------------------------------------------
    # Poblar lista de sesiones
    # ------------------------------------------------------------------
    def _populate_sessions(self, sessions: list[Session]):
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
 
        for i, session in enumerate(sessions):  # ya vienen de la más nueva a la más vieja
            row = self._build_session_row(i, session)
            self.sessions_layout.insertWidget(i, row)
 
    def _build_session_row(self, index: int, session: Session) -> QWidget:
        row = QWidget()
        row.setObjectName("sessionRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 4, 8, 4)
 
        hours, minutes = divmod(session.duration_s // 60, 60)
        formatted = f"{hours} horas : {minutes} minutos"
 
        lbl_date = QLabel(_session_label(session))
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
            GameLauncherController().launch_game(self.current_game, self.platform_name)
 
    def _open_notes(self):
        game = store.get_game(self.platform_name, self.current_game or "")
        if game is None:
            return
        store.set_notes(self.platform_name, game.name, NotesDialog.ask(self, game.name, game.notes))
 
    def _toggle_favorites(self):
        self.toggle_favorites.emit(self.current_game)
        
    def _show_props_menu(self):
        global_pos = self.btn_settings.mapToGlobal(
            self.btn_settings.rect().bottomLeft())

        self.context_menu_requested.emit(global_pos, True)
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
        GameLauncherController().register_ui(self.platform_name, self)
 
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
        supr_shortcut.activated.connect(self._confirm_remove_selected)
        for key in ("Return", "Enter"):
            QShortcut(QKeySequence(key), self.games_tree).activated.connect(self._launch_selected)

        self.detail_panel.context_menu_requested.connect(
            lambda global_pos, btn_props: self.show_game_menu(
            self.detail_panel.current_game, global_pos, btn_props, offset_x=-143, offset_y=84))

        self.detail_panel.toggle_favorites.connect(self.toggle_favorite)
 
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
        self.launch_game(item.text(0))

    def _on_game_right_click(self, pos, btn_props = False):
        game = self.games_tree.itemAt(pos)
        if game is None:
            game_name = None
        else:
            self.games_tree.setCurrentItem(game)
            game_name = game.text(0)
            self._on_game_clicked(game, 0) 
        
        global_pos = self.games_tree.viewport().mapToGlobal(pos)
        self.show_game_menu(game_name, global_pos)
   
    # ------------------------------------------------------------------
    def show_game_menu(self, game_name, global_pos, btn_props=False, offset_x=2, offset_y=84):
        menu = CustomPopupMenu(self, on_close_callback=None)
        options = PlatformHandler().get("menu-options").get_options(game_name, btn_props, self)
        QtMenuRenderer().build(menu, options)
        menu.show_at(global_pos, offset_x=offset_x, offset_y=offset_y)

    def update_on_close(self, game_name, platform_name):
        """Al cerrar un juego: reordena la lista (último jugado arriba), refresca
        favoritos y muestra el detalle del juego con las horas nuevas."""
        self.refresh_games()
        self.favorites_panel.refresh()
        item = self._find_item_by_name(game_name)
        if item is None:
            logging.warning(f"No se encontró el item del juego {game_name} tras el cierre")
            return

        self.games_tree.setCurrentItem(item)
        self._on_game_clicked(item, 0)

    def toggle_favorite(self, game_name):
        toggle, msg = DataManager().toggle_favorite(self.platform_name, game_name)
        if not toggle:
            QMessageBox.warning(self, "Favorito", msg)
            return
        self.favorites_panel.refresh()

    # ------------------------------------------------------------------

    def refresh_games(self):
        """Vuelve a leer la lista de juegos, conservando búsqueda y selección."""
        current = self.games_tree.currentItem()
        selected = current.text(0) if current else None
        self.fill_games(DataManager().collect_platform_data(self.platform_name)["grouped"])
        self._filter_games(self.search_bar.text())
        item = self._find_item_by_name(selected) if selected else None
        if item:
            self.games_tree.setCurrentItem(item)

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
            self.file_manager.delete_game(platform_name, game_name)
            self.favorites_panel.refresh()
        
        self.right_stack.setCurrentIndex(0)

        QTimer.singleShot(0, self.games_tree.clearSelection)
        QTimer.singleShot(0, lambda: self.games_tree.setCurrentItem(None))

    def _filter_games(self, text: str):
        text = text.lower().strip()
        for i in range(self.games_tree.topLevelItemCount()):
            item = self.games_tree.topLevelItem(i)
            item.setHidden(text not in item.text(0).lower())

    def _find_item_by_name(self, game_name):
        for i in range(self.games_tree.topLevelItemCount()):
            item = self.games_tree.topLevelItem(i)
            if item.text(0) == game_name:
                return item
        return None

    def launch_game(self, game_name):
        GameLauncherController().launch_game(game_name, self.platform_name)

    def _launch_selected(self):
        item = self.games_tree.currentItem()
        if item is not None:
            self.launch_game(item.text(0))

    def _confirm_remove_selected(self):
        if self.games_tree.currentItem() is not None:
            self.confirm_remove()
    
    def confirm_remove(self):
        dlg = ConfirmDialog(self, title="Eliminar juego",
                            message="El juego deja de mostrarse. Sus horas jugadas se conservan.",
                            callback=self._on_confirm)
        dlg.exec()
    
    def _on_confirm(self, value):
        if value:
            self._delete_selected_item()
    
    def add_exe(self):
        exe_path, _ = QFileDialog.getOpenFileName(
            self, "Selecciona un ejecutable", "", _exe_filter())
        if not exe_path:
            return  # el usuario cancelo el dialogo

        success, result = self.file_manager.add_game(self.platform_name, exe_path)
        if not success:
            QMessageBox.warning(self, "Juego duplicado.", result)
            return

        game_name = result
        icon = PlatformHandler().get("icons").get_icon(exe_path)
        game_data = {'icon': icon, 'name': game_name, 'path': exe_path}

        # actualizo el árbol sin recargar todo desde cero
        self._add_game_item(game_data)
        self._all_games.append(game_data)

    def change_game_directory(self, game_name):
        try:
            exe_path, _ = QFileDialog.getOpenFileName(
                self, "Selecciona un ejecutable", "", _exe_filter())
            if not exe_path:
                return # El usuario canceló el diálogo

            store.set_game_path(self.platform_name, game_name, exe_path)

        except Exception as e:
            logging.exception("Error al cambiar el directorio del juego")
            QMessageBox.critical(self, "Error", f"No se pudo guardar el nuevo ejecutable:\n{e}")
    
    def ask_steam_id(self, game_name):
        dlg = InputDialog(self, prompt="Ingresar Steam ID",
                          callback=lambda value: value and store.set_steam_appid(self.platform_name, game_name, value))
        dlg.exec()

    def _game_path(self, game_name):
        game = store.get_game(self.platform_name, game_name)
        return game.path if game else None

    def gotofolder(self, game_name):
        PlatformHandler().get("paths").goto_folder(self._game_path(game_name))

    def create_direct_access(self, game_name):
        PlatformHandler().get("shortcut").create_direct_access(
            self.platform_name, game_name, self._game_path(game_name))

    def create_start_menu_shortcut(self, game_name):
        PlatformHandler().get("shortcut").create_start_menu_shortcut(
            self.platform_name, game_name, self._game_path(game_name))


class SettingsWindow(QDialog):
    login_finished = Signal(bool)  # ok, email

    def __init__(self, parent, on_close_callback=None):
        super().__init__(parent)
        self.setObjectName("cloudSettingsWindow")
        self.setWindowTitle("Configuración")
        self.parent_window = parent
        self.on_close_callback = on_close_callback

        self.login_finished.connect(self._on_login_finished)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.chk_sync = QCheckBox("Habilitar sincronización automática")
        self.chk_sync.setChecked(store.get_setting("cloud_sync_enabled", False))
        self.chk_sync.toggled.connect(self._toggle_clouding)
        layout.addWidget(self.chk_sync)

        self.account_label = QLabel(self._get_account_info())
        self.account_label.setObjectName("cloudAccountLabel")
        layout.addWidget(self.account_label)

        self.btn_change_account = QPushButton("🔄 Cambiar cuenta")
        self.btn_change_account.clicked.connect(self._change_account)
        layout.addWidget(self.btn_change_account)

        self.chk_multiple = QCheckBox("Permitir varios juegos abiertos a la vez")
        self.chk_multiple.setChecked(store.get_setting("allow_multiple_games", True))
        self.chk_multiple.toggled.connect(
            lambda checked: store.set_setting("allow_multiple_games", checked))
        layout.addWidget(self.chk_multiple)

    # ------------------------------------------------------------------
    def _toggle_clouding(self, checked):
        store.set_setting("cloud_sync_enabled", checked)
        if checked and store.get_setting("email") is None:
            self._confirm("Serás redirigido al navegador", "¿Estás seguro?", self._recall_token)

    def _change_account(self):
        title = "Deberás volver a iniciar sesión" if store.get_setting("email") is not None \
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
            store.set_setting("cloud_sync_enabled", True)
            
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
        return store.get_setting("email") or "Sin cuenta"

# Ventana principal
class MainWindow(QMainWindow):
    cloud_merged = Signal()

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
        self.tab_widget.tabBar().tabMoved.connect(lambda *_: self._save_tab_order())
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
 
        if store.list_platforms():
            self.empty_label.setText("Cargando plataformas...")
            self._start_reload(callback = self._on_reload_finished)
        
        self.sessions_bar = SessionsBar()
        root_layout.addWidget(self.sessions_bar)

        # Juegos lanzados desde accesos directos mientras la UI está abierta
        self._external_timer = QTimer(self)
        self._external_timer.timeout.connect(get_event_bus().watch_external)
        self._external_timer.start(EXTERNAL_POLL_MS)

        # Con cloud activado, al abrir se traen los datos de la nube y se refresca
        self.cloud_merged.connect(self._refresh_all_tabs)
        if store.get_setting("cloud_sync_enabled", False):
            call_merge(callback=self.cloud_merged.emit)
 
    # ------------------------------------------------------------------

    def _start_reload(self, callback = None):
        reload_with_thread(self, callback)

    def _on_reload_finished(self, all_data: list):
        for data in all_data:
            self._add_platform_tab(data)
        last = store.get_setting("last_selected_tab")
        names = [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]
        if last in names:
            self.tab_widget.setCurrentIndex(names.index(last))
        # Recién ahora: agregar pestañas también dispara currentChanged
        self.tab_widget.currentChanged.connect(self._remember_tab)

    def _remember_tab(self, index: int):
        if index >= 0:
            store.set_setting("last_selected_tab", self.tab_widget.tabText(index))

    def _refresh_all_tabs(self):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            tab.refresh_games()
            tab.favorites_panel.refresh()
 
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
 
        email = store.get_setting("email") or "Desconocido"
        self.account_label = QLabel(f"Cuenta: {email}")
        layout.addWidget(self.account_label)
        layout.addStretch()
 
        self.btn_add_platform = QPushButton("Agregar Plataforma")
        self.btn_add_platform.clicked.connect(self.add_platform)
        self.btn_sync = QPushButton("⚙ Configuración")
        self.btn_sync.clicked.connect(self._open_settings)
        layout.addWidget(self.btn_add_platform)
        layout.addWidget(self.btn_sync)
 
        return header
 
    def update_title_label(self):
        email = store.get_setting("email")
        self.account_label.setText(f"Cuenta: {email}")
    # ------------------------------------------------------------------
    def add_platform(self):
        result = ask_platform_folder(self)
        if not result:
            return
 
        platform_name, folder = result
        if platform_name in store.list_platforms():
            QMessageBox.warning(self, "Plataforma existente", f"Ya existe '{platform_name}'.")
            return
        self.file_manager.add_platform(platform_name, folder)
 
        data = DataManager().collect_platform_data(platform_name)
        self._add_platform_tab(data)
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
 
    def _open_settings(self):
        dlg = SettingsWindow(self)
        dlg.show()

    # ------------------------------------------------------------------
    def _on_tab_close_requested(self, index: int):
        platform_name = self.tab_widget.tabText(index)
        dlg = ConfirmDialog(
            self,
            title=f"Eliminar {platform_name}",
            message=f"¿Quitar '{platform_name}'? Sus juegos dejan de mostrarse; las horas jugadas se conservan.",
            callback=lambda confirmed: self._remove_tab(index, platform_name, confirmed)
        )
        dlg.exec()
 
    def _remove_tab(self, index: int, platform_name: str, confirmed):
        if not confirmed:
            return
 
        self.file_manager.delete_platform(platform_name)
        self.tab_widget.removeTab(index)
        self._save_tab_order()
 
        if self.tab_widget.count() == 0:
            self.tab_widget.hide()
            self.empty_label.show()

    def _on_tab_context_menu(self, pos):
        tab_bar = self.tab_widget.tabBar()
        index = tab_bar.tabAt(pos)  # -1 si clickeaste en espacio vacío de la barra

        if index == -1:
            return  # click derecho fuera de cualquier pestaña, ignorar

        global_pos = tab_bar.mapToGlobal(pos)  # convertir coords locales -> globales

        menu = CustomPopupMenu(self, on_close_callback=None)
        menu.add_button("⚙ Propiedades", command=lambda: self._open_properties(index))
        menu.add_button("⟳ Recargar", command=lambda: self._reload_tab(index))
        menu.add_button("🗑 Eliminar plataforma", command=lambda: self._on_tab_close_requested(index))
        menu.show_at(global_pos)

    def _save_tab_order(self):
        store.reorder_platforms(
            [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())])

    def _replace_tab(self, index: int, platform_name: str):
        """Reconstruye la pestaña con los datos actuales de la DB."""
        data = DataManager().collect_platform_data(platform_name)
        tab = PlatformTab(platform_name)
        tab.fill_games(data["grouped"])
        old_tab = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        old_tab.deleteLater()
        self.tab_widget.insertTab(index, tab, platform_name)
        self.tab_widget.setCurrentIndex(index)

    def _open_properties(self, index: int):
        platform_name = self.tab_widget.tabText(index)
        dlg = PlatformPropertiesDialog(self, platform_name)
        dlg.exec()
        if dlg.changed:
            self._replace_tab(index, dlg.platform_name)

    def _reload_tab(self, index: int):
        platform_name = self.tab_widget.tabText(index)
        self.file_manager.scan_for_games(platform_name)
        self._replace_tab(index, platform_name)
 
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
 
def _exe_filter() -> str:
    """En Linux los binarios nativos no tienen extensión: primero "Todos"."""
    exes = "Ejecutables (*.exe *.bat *.cmd)"
    every = "Todos los archivos (*)"
    return f"{exes};;{every}" if sys.platform.startswith("win") else f"{every};;{exes}"


class PlatformPropertiesDialog(QDialog):
    """Directorios de la plataforma (agregar, quitar, abrir) y renombrarla."""

    def __init__(self, parent, platform_name: str):
        super().__init__(parent)
        self.platform_name = platform_name
        self.changed = False  # si hay que reconstruir la pestaña al cerrar
        self.file_manager = FileManager()
        self.setWindowTitle(f"Propiedades — {platform_name}")
        self.resize(560, 360)

        tabs = QTabWidget(self)
        QVBoxLayout(self).addWidget(tabs)

        # Directorios
        dirs = QWidget()
        dirs_layout = QVBoxLayout(dirs)
        self.folder_list = QListWidget()
        self.folder_list.itemDoubleClicked.connect(lambda _: self._open_folder())
        dirs_layout.addWidget(self.folder_list)
        buttons = QHBoxLayout()
        for text, slot in (("➕ Agregar", self._add_folder), ("🗑 Quitar", self._remove_folder),
                           ("📂 Abrir", self._open_folder)):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            buttons.addWidget(btn)
        dirs_layout.addLayout(buttons)
        tabs.addTab(dirs, "📁 Directorios")

        # Nombre
        name = QWidget()
        name_layout = QHBoxLayout(name)
        self.name_edit = QLineEdit(platform_name)
        save = QPushButton("💾 Guardar")
        save.clicked.connect(self._rename)
        name_layout.addWidget(QLabel("Nombre:"))
        name_layout.addWidget(self.name_edit)
        name_layout.addWidget(save)
        tabs.addTab(name, "📝 Nombre")

        self._load_folders()

    def _load_folders(self):
        self.folder_list.clear()
        self.folder_list.addItems(store.list_folders(self.platform_name))

    def _selected_folder(self) -> str | None:
        item = self.folder_list.currentItem()
        return item.text() if item else None

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Agregar carpeta de juegos", "")
        if folder:
            self.file_manager.add_folder(self.platform_name, folder)
            self.changed = True
            self._load_folders()

    def _remove_folder(self):
        folder = self._selected_folder()
        if folder is None:
            return
        answer = QMessageBox.question(
            self, "Quitar directorio",
            f"¿Quitar '{folder}'? Sus juegos dejan de mostrarse; las horas se conservan.")
        if answer == QMessageBox.StandardButton.Yes:
            self.file_manager.delete_folder(self.platform_name, folder)
            self.changed = True
            self._load_folders()

    def _open_folder(self):
        folder = self._selected_folder()
        if folder:
            PlatformHandler().get("paths").goto_folder(folder)

    def _rename(self):
        new = self.name_edit.text().strip()
        if not new or new == self.platform_name:
            return
        if store.has_running_games(self.platform_name):
            QMessageBox.information(
                self, "Renombrar", "Cerrá los juegos de esta plataforma antes de renombrarla.")
            return
        if not self.file_manager.rename_platform(self.platform_name, new):
            QMessageBox.warning(self, "Renombrar", f"Ya existe una plataforma '{new}'.")
            return
        self.platform_name = new
        self.changed = True
        self.setWindowTitle(f"Propiedades — {new}")


def _session_label(session: Session) -> str:
    if session.kind == "month":
        return f"{session.started_at[:7]}  ({session.sessions_count} sesiones)"
    if session.kind == "legacy":
        return "Total antes del historial detallado"
    return session.started_at.replace("T", " ")[:16]


class NotesDialog(QDialog):
    """Editor de notas de un juego."""

    def __init__(self, parent, game_name: str, notes: str):
        super().__init__(parent)
        self.setWindowTitle(f"Notas — {game_name}")
        self.resize(420, 320)
        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit(notes)
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @classmethod
    def ask(cls, parent, game_name: str, notes: str) -> str:
        """Devuelve el texto al cerrar el editor (se guarda siempre, como en Tk)."""
        dlg = cls(parent, game_name, notes)
        dlg.exec()
        return dlg.editor.toPlainText()


# Worker: carga todas las plataformas guardadas en un hilo separado
class ReloadWorker(QObject):
    finished = Signal(list)   # emite all_data cuando termina
    progress = Signal(str)    # emite mensajes de estado opcionales

    def run(self):
        all_data = []
        for platform_name in store.list_platforms():
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
        if sys.platform.startswith("win"):
            # Agrupa la ventana con el ícono propio en la barra de tareas
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Launcher69.App")
        app = QApplication(sys.argv)
        app.setWindowIcon(load_qicon(Path(ICONS) / "icon.ico", size=None))
        themes_path = Path(THEMES_DIR) / "theme_cyberpunk.qss"
        with open(themes_path, "r") as f:
            app.setStyleSheet(f.read())
        w = MainWindow()
        w.show()
        sys.exit(app.exec())