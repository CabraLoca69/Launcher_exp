"""Reglas de las claves de la DB.

Las claves son caminos separados por '.' (`plataforma.game_list.<juego>`), así que
un segmento nunca puede contener un '.': la DB no podría distinguir el juego
`Game.v2` de un hijo `v2` dentro de `Game`.
"""

from pathlib import Path


def key_segment(name: str) -> str:
    """Convierte un texto en un segmento de clave válido."""
    return name.replace(".", "_")


def game_name_from_path(path: str) -> str:
    """Nombre del juego (y segmento de clave) para un ejecutable."""
    return key_segment(Path(path).stem)


def is_valid_platform_name(name: str) -> bool:
    """Una plataforma es la raíz de sus claves: no puede estar vacía ni tener '.'."""
    return bool(name.strip()) and "." not in name
