from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLineEdit, QListWidget, QTabBar, QLabel, QPushButton,
    QFrame, QFileDialog, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction

from pathlib import Path
from helpers import Loader, collect_platform_data
from qicon_utils import load_qicon


from PySide6.QtWidgets import QApplication
from datafiles import THEMES_DIR, db
import sys


class NewLauncherUI():
    def launch_ui():
        app = QApplication(sys.argv)
        themes_path = Path(THEMES_DIR) / "theme_dark.qss"

        with open(themes_path, "r") as f:
            app.setStyleSheet(f.read())

        w = MainWindow()
        w.show()
    
        sys.exit(app.exec())

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CLauncher69 - V2")
        self.setMinimumSize(1200, 700)
        self.loader = Loader()

        # === ROOT CENTRAL WIDGET ===
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header + TabBar + Main content
        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_tabbar())
        root_layout.addWidget(self._build_body())

        self.setCentralWidget(root)

    # --------------------------------------------------------------
    # HEADER
    # --------------------------------------------------------------
    def _build_header(self):
        header = QWidget()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(15, 8, 15, 8)

        # Left side
        email = db.get("global.email", default= "Desconocido") or "Desconocido"
        self.account_label = QLabel(f"Cuenta: {email}")
        layout.addWidget(self.account_label)

        layout.addStretch()

        # Right side buttons
        self.btn_add_platform = QPushButton("Agregar Plataforma")
        self.btn_add_platform.clicked.connect(self.add_platform)
        self.btn_sync = QPushButton("Cloud")

        layout.addWidget(self.btn_add_platform)
        layout.addWidget(self.btn_sync)

        return header

    # --------------------------------------------------------------
    # TAB BAR
    # --------------------------------------------------------------
    def _build_tabbar(self):
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(10, 5, 10, 5)

        self.tab_bar = QTabBar(movable=True)
        self.tab_bar.setTabsClosable(False)
        self.tab_bar.setExpanding(False)

        # Dummy tabs (vos reemplazás con DB)
        self.tab_bar.addTab("Steam")
        self.tab_bar.addTab("GOG")
        self.tab_bar.addTab("Custom")

        layout.addWidget(self.tab_bar)
        return wrapper

    # --------------------------------------------------------------
    # MAIN BODY: Sidebar + Content Panel
    # --------------------------------------------------------------
    def _build_body(self):
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left Sidebar
        sidebar = self._build_sidebar()
        sidebar.setFixedWidth(260)

        # Right content panel
        self.panel_right = self._build_right_panel()

        layout.addWidget(sidebar)
        layout.addWidget(self.panel_right)

        return body

    # --------------------------------------------------------------
    # SIDEBAR: search bar + list
    # --------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("Juegos")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Search
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar juegos...")
        layout.addWidget(self.search_bar)

        # Games tree (reemplazo del Listbox / Treeview de Tkinter)
        self.games_tree = QTreeWidget()
        self.games_tree.setHeaderLabels(["Juegos"])
        self.games_tree.setColumnCount(1)
        self.games_tree.setIndentation(16)
        self.games_tree.setIconSize(QSize(20, 20))  # Opcional, ajustable
        layout.addWidget(self.games_tree)

        return sidebar

    def add_platform(self):
        platform_name = "PC"   # Ejemplo. Después lo hacés dinámico.

        folder = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de juegos",
            "",
            QFileDialog.ShowDirsOnly
        )

        if not folder:
            return

        # Backend
        self.loader.add_folder(platform_name, folder)

        # Obtenemos datos listos para UI
        data = collect_platform_data(platform_name)

        # Repoblar el árbol
        self.fill_games_tree(data)

    def fill_games_tree(self, data):
        """
        data = {
            "platform": "PC",
            "grouped": [ {name, path, icon}, ... ]
        }
        """
        self.games_tree.clear()

        for game in data["grouped"]:
            item = QTreeWidgetItem([game["name"]])
            if game["icon"]:
                qicon = load_qicon(game["icon"])
                item.setIcon(0, qicon)

            self.games_tree.addTopLevelItem(item)

    # --------------------------------------------------------------
    # RIGHT PANEL (dynamic)
    # --------------------------------------------------------------
    def _build_right_panel(self):
        panel = QWidget()
        panel.setObjectName("rightPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)

        placeholder = QLabel("Panel de contenido (Favoritos / Detalles)")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("font-size: 22px; color: #888;")

        layout.addWidget(placeholder)

        return panel

def ask_platform_folder(self, platform):
    folder = QFileDialog.getExistingDirectory(
        self,
        "Seleccionar carpeta de juegos",
        "",
        QFileDialog.ShowDirsOnly
    )

    if not folder:
        return

    # Llamar al backend
    loader = Loader()
    loader.add_folder(platform, folder)

    # Volver a llenar la UI
    data = collect_platform_data(platform)
    self.fill_games_tree(data)