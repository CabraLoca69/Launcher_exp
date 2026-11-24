# --------- imports internos -------
from .event_bus import NullEventBus, QtEventBus

_INTERFACE_CLASSES = {
    "Qt": QtEventBus,
    "None": NullEventBus,
}

_instance = None


def init_event_bus(interface: str = "None"):
    global _instance
    if interface not in _INTERFACE_CLASSES:
        raise ValueError(f"Interfaz desconocida: {interface}")
    _instance = _INTERFACE_CLASSES[interface]()
    return _instance


def get_event_bus():
    if _instance is None:
        return init_event_bus("None")  # caso --launch: no hay UI
    return _instance
