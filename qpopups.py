"""
popups.py — Equivalentes en PySide6 de los popups personalizados de tkinter.

Clases:
    BasePopup        → equivalente a AutoCloseFrame (se cierra con Escape / click afuera)
    CustomPopupMenu  → menú contextual flotante con botones
    InputDialog      → diálogo de texto con Aceptar / Cancelar
    ConfirmDialog    → diálogo de confirmación Sí / No

Diferencias clave con la versión tkinter:
    - Se usan QDialog modales en lugar de frames superpuestos con place().
      Qt maneja el "click afuera" de forma nativa en los modales sin decoración.
    - Las callbacks siguen el mismo patrón: callback(value) al cerrar.
    - CustomPopupMenu sí es flotante (QFrame sobre el widget padre), igual que antes.
"""

from PySide6.QtWidgets import (
    QDialog, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QWidget, QApplication
)
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QKeyEvent


# ===========================================================================
# BASE: lógica compartida de cierre (Escape + click afuera)
# Equivalente a AutoCloseFrame
# ===========================================================================
class BasePopup(QDialog):
    """
    Diálogo sin decoración de ventana que se cierra al presionar Escape
    o al hacer click fuera de él. Subclasear y llamar a _respond(value)
    para cerrar con un resultado.

    Args:
        parent:      widget padre (para centrado relativo)
        callback:    función llamada con el valor de cierre → callback(value)
    """

    def __init__(self, parent: QWidget = None, callback=None):
        super().__init__(parent)
        self.callback = callback

        # Sin bordes de ventana del SO → aspecto consistente con el tema
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # Click afuera cierra el diálogo
        self.setModal(True)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self._respond(None)
        else:
            super().keyPressEvent(event)

    def _respond(self, value):
        """Cerrar el diálogo y disparar el callback con `value`."""
        self.accept()
        if self.callback:
            self.callback(value)

    # Clic fuera del área del diálogo → cerrar
    def mousePressEvent(self, event):
        # En un QDialog modal FramelessWindowHint los clicks fuera
        # no llegan al widget; este handler cubre el caso de clicks
        # en el fondo semitransparente si se usa con overlay.
        if not self.rect().contains(event.pos()):
            self._respond(None)
        else:
            super().mousePressEvent(event)


# ===========================================================================
# MENÚ CONTEXTUAL FLOTANTE
# Equivalente a CustomPopupMenu — flota sobre el widget padre con place()
# ===========================================================================
class CustomPopupMenu(QFrame):
    """
    Menú flotante posicionado en coordenadas absolutas sobre el padre.
    No es modal; se cierra con Escape o click fuera.

    Uso:
        menu = CustomPopupMenu(parent, on_close_callback=mi_funcion)
        menu.add_button("Editar",    command=editar)
        menu.add_button("Eliminar",  command=eliminar)
        menu.show_at(event.globalPos())   # QPoint con coords globales
    """

    def __init__(self, parent: QWidget = None, on_close_callback=None):
        super().__init__(parent)
        self.on_close_callback = on_close_callback
        self._menu_open = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setObjectName("customPopupMenu")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)

        # Interceptar clicks globales para cerrar al hacer click afuera
        QApplication.instance().installEventFilter(self)

    def add_button(self, text: str, command, width: int = None):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        if width:
            btn.setFixedWidth(width)
        btn.clicked.connect(lambda: (command(), self._close()))
        self._layout.addWidget(btn)

    def show_at(self, global_pos: QPoint):
        """Mostrar el menú en coordenadas globales (ej: event.globalPos())."""
        if self._menu_open:
            self._close()
            return

        self.adjustSize()

        # Convertir coords globales a locales del padre
        if self.parent():
            local = self.parent().mapFromGlobal(global_pos)
        else:
            local = global_pos

        self.move(local)
        self.raise_()
        self.show()
        self._menu_open = True

    def _close(self):
        if not self._menu_open:
            return
        self._menu_open = False
        QApplication.instance().removeEventFilter(self)
        self.hide()
        if self.on_close_callback:
            self.on_close_callback()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self._close()
        else:
            super().keyPressEvent(event)

    # Cerrar si el click fue afuera del frame
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if self._menu_open:
                global_pos = event.globalPosition().toPoint()
                local = self.mapFromGlobal(global_pos)
                if not self.rect().contains(local):
                    self._close()
        return False  # no consumir el evento

# ===========================================================================
# DIÁLOGO DE TEXTO
# Equivalente a InputDialog
# ===========================================================================
class InputDialog(BasePopup):
    """
    Diálogo con un campo de texto.

    Callback recibe:
        str   → si el usuario confirmó con texto
        False → si canceló o dejó el campo vacío
        None  → si cerró con Escape / click afuera

    Uso:
        def on_input(value):
            if value:
                print("Ingresó:", value)

        dlg = InputDialog(parent, prompt="Nombre de plataforma:", callback=on_input)
        dlg.exec()
    """

    def __init__(self, parent: QWidget = None, prompt: str = "Ingrese valor:", callback=None):
        super().__init__(parent, callback)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Prompt
        lbl = QLabel(prompt)
        lbl.setObjectName("inputDialogPrompt")
        layout.addWidget(lbl)

        # Campo de texto
        self.entry = QLineEdit()
        self.entry.setObjectName("inputDialogEntry")
        self.entry.returnPressed.connect(lambda: self._respond_input(confirmed=True))
        layout.addWidget(self.entry)

        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_ok = QPushButton("Aceptar")
        btn_ok.setObjectName("btnSuccess")
        btn_ok.clicked.connect(lambda: self._respond_input(confirmed=True))

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("btnDanger")
        btn_cancel.clicked.connect(lambda: self._respond_input(confirmed=False))

        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.entry.setFocus()

    def _respond_input(self, confirmed: bool):
        if confirmed:
            value = self.entry.text().strip().title()
            value = value if value else False
        else:
            value = False
        self._respond(value)


# ===========================================================================
# DIÁLOGO DE CONFIRMACIÓN
# Equivalente a ConfirmDialog
# ===========================================================================
class ConfirmDialog(BasePopup):
    """
    Diálogo de confirmación Sí / No.

    Callback recibe:
        True  → confirmó
        False → canceló
        None  → Escape / click afuera

    Uso:
        def on_confirm(result):
            if result:
                borrar_juego()

        dlg = ConfirmDialog(
            parent,
            title="Eliminar juego",
            message="¿Estás seguro? Esta acción no se puede deshacer.",
            callback=on_confirm
        )
        dlg.exec()
    """

    def __init__(
        self,
        parent: QWidget = None,
        title: str = "Confirmar",
        message: str = "¿Estás seguro?",
        callback=None,
    ):
        super().__init__(parent, callback)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        # Título
        lbl_title = QLabel(title)
        lbl_title.setObjectName("confirmDialogTitle")
        layout.addWidget(lbl_title)

        # Mensaje
        lbl_msg = QLabel(message)
        lbl_msg.setObjectName("confirmDialogMessage")
        lbl_msg.setWordWrap(True)
        layout.addWidget(lbl_msg)

        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_yes = QPushButton("✅  Sí")
        btn_yes.setObjectName("btnSuccess")
        btn_yes.setFixedWidth(100)
        btn_yes.clicked.connect(lambda: self._respond(True))

        btn_no = QPushButton("❌  No")
        btn_no.setObjectName("btnDanger")
        btn_no.setFixedWidth(100)
        btn_no.clicked.connect(lambda: self._respond(False))

        btn_layout.addStretch()
        btn_layout.addWidget(btn_yes)
        btn_layout.addWidget(btn_no)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Enter = confirmar
        btn_yes.setDefault(True)