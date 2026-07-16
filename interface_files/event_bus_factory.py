# event_bus_factory.py
from .event_bus import TkEventBus, QtEventBus

_INTERFACE_CLASSES = {
    "Tk": TkEventBus,
    "Qt": QtEventBus,
}

_instance = None

def init_event_bus(interface: str):
    global _instance
    if interface not in _INTERFACE_CLASSES:
        raise ValueError(f"Interfaz desconocida: {interface}")
    _instance = _INTERFACE_CLASSES[interface]()
    return _instance

def get_event_bus():
    if _instance is None:
        raise RuntimeError("El event bus no fue inicializado. Llamá a init_event_bus() primero.")
    return _instance