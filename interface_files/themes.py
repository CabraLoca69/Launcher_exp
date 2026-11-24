"""Temas de la interfaz.

Un tema es `data/themes/<id>.json` con su nombre y una paleta de colores. Todos
comparten la plantilla `data/themes/base.qss`, donde `@color` es un color de la
paleta y `@color/NN` el mismo color con NN % de opacidad.

Para agregar un tema alcanza con copiar un `.json` y cambiar los colores.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

# --------- imports internos -------
from data_access.datafiles import THEMES_DIR

logger = logging.getLogger(__name__)

DEFAULT_THEME = "cyberpunk"
COLOR_KEYS = (
    "bg",
    "sidebar",
    "surface",
    "surface_alt",
    "border",
    "text",
    "text_bright",
    "text_soft",
    "text_muted",
    "text_dim",
    "text_faint",
    "accent",
    "accent2",
    "warning",
)
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_TOKEN = re.compile(r"@([a-z_0-9]+)(?:/(\d{1,3}))?")
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


@dataclass(frozen=True)
class Theme:
    id: str
    name: str
    colors: dict[str, str]


def load_theme(path: Path) -> Theme:
    """Lee y valida un tema. Los colores van como `#RRGGBB`: la opacidad se pone en
    la plantilla (`@color/NN`), porque Qt lee 8 dígitos como `#AARRGGBB`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    colors = data.get("colors", {})
    missing = [k for k in COLOR_KEYS if k not in colors]
    if missing:
        raise ValueError(f"Al tema {path.name} le faltan colores: {missing}")
    bad = {k: v for k, v in colors.items() if not _HEX.match(str(v))}
    if bad:
        raise ValueError(f"Colores inválidos en {path.name} (usar #RRGGBB): {bad}")
    return Theme(path.stem, str(data.get("name", path.stem)), colors)


def list_themes(themes_dir: Path = THEMES_DIR) -> list[Theme]:
    """Temas válidos, por nombre. Los que tienen errores se saltean (y se loguean)."""
    themes = []
    for path in sorted(Path(themes_dir).glob("*.json")):
        try:
            themes.append(load_theme(path))
        except (OSError, ValueError) as e:
            logger.warning("Tema ignorado: %s", e)
    return sorted(themes, key=lambda t: t.name.lower())


def _rgba(hex_color: str, percent: int) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {round(min(percent, 100) * 255 / 100)})"


def render(template: str, colors: dict[str, str]) -> str:
    """Reemplaza `@color` y `@color/NN` de la plantilla por colores reales."""

    def replace(match: re.Match) -> str:
        name, alpha = match.group(1), match.group(2)
        if name not in colors:
            raise KeyError(f"La plantilla usa @{name}, que no está en la paleta")
        return colors[name] if alpha is None else _rgba(colors[name], int(alpha))

    return _TOKEN.sub(replace, _COMMENT.sub("", template))


def stylesheet(theme_id: str, themes_dir: Path = THEMES_DIR) -> str:
    """Hoja de estilos del tema; si no existe o está roto, la del tema por defecto."""
    themes_dir = Path(themes_dir)
    by_id = {t.id: t for t in list_themes(themes_dir)}
    theme = by_id.get(theme_id) or by_id.get(DEFAULT_THEME)
    if theme is None:
        logger.error("No hay temas válidos en %s", themes_dir)
        return ""
    template = (themes_dir / "base.qss").read_text(encoding="utf-8")
    return render(template, theme.colors)
