import os
import psutil
import ttkbootstrap as tb
from tkinter import StringVar

class AutoCloseFrame(tb.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.after(100, self.bind_click_outside)

    def bind_click_outside(self):
        self.bind_all("<Button-1>", self.check_click_outside)
        self.bind_all("<Button-3>", self.check_click_outside)

    def check_click_outside(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)

        # Ignorar widgets internos de Tk (como __tk_choosedir)
        if widget and str(widget).startswith("__tk_"):
            return

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
