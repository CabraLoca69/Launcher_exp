from .event_bus import TkEventBus, QtEventBus, NullEventBus
from .tk_menus_renderer import TkMenuRenderer
from .qt_menus_renderer import QtMenuRenderer

_INTERFACE_CLASSES = {
    "Tk": TkEventBus,
    "Qt": QtEventBus,
    "None": NullEventBus,
}

_MENU_RENDERER_CLASSES = {
    "Tk": TkMenuRenderer,
    "Qt": QtMenuRenderer, 
}

_instance = None
_current_interface = None  

def init_event_bus(interface: str = "None"):
    global _instance, _current_interface
    if interface not in _INTERFACE_CLASSES:
        raise ValueError(f"Interfaz desconocida: {interface}")
    _instance = _INTERFACE_CLASSES[interface]()
    _current_interface = interface
    return _instance

def get_event_bus():
    global _instance
    if _instance is None:
        return init_event_bus("None") #caso --launch, no hay UI, inicializamos NullEventBus
    return _instance

def _require_interface():
    if _current_interface is None:
        raise RuntimeError("La interfaz no fue inicializada. Llamá a init_event_bus() primero.")
    return _current_interface

def get_menu_renderer():
    interface = _require_interface()
    return _MENU_RENDERER_CLASSES[interface]()