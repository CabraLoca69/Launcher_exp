import os
import sys
import json
import threading
from pathlib import Path

def get_data_dir():
    if sys.platform.startswith("win"):
        base_dir = Path(os.path.dirname(os.path.abspath(sys.argv[0])))
        return base_dir / "data"
    else:
        # Linux/macOS: ~/.config/Clauncher
        return Path.home() / ".config" / "Clauncher"

DATA_DIR = get_data_dir()
ICONS_CACHE_DIR = DATA_DIR / "icons_cache"
ICONS = DATA_DIR / "icons"

# Crear carpetas si no existen
DATA_DIR.mkdir(parents=True, exist_ok=True)
ICONS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
ICONS.mkdir(parents=True, exist_ok=True)

# Archivos
CONFIG_FILE = DATA_DIR / "config.json"
NOTES_FILE = DATA_DIR / "notas.json"
FLAG_FILE = DATA_DIR / "notify_update.flag"

# Lock global para operaciones con config
config_lock = threading.Lock()

# Cargar configuración
try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    config = {}

if NOTES_FILE.exists():
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        notas = json.load(f)
else:
    notas = {}

if "global" not in config:
    config.setdefault("global", {}).setdefault("allow_multiple_games", False)