import os
import sys
import json
import threading
from pathlib import Path

# ------------------------------
# Directorios de datos
# ------------------------------
def get_data_dir():
    """Devuelve la carpeta principal de datos según el sistema."""
    if sys.platform.startswith("win"):
        base_dir = Path(os.path.dirname(os.path.abspath(sys.argv[0])))
        return base_dir / "data"
    else:
        return Path.home() / ".config" / "Clauncher"

DATA_DIR = get_data_dir()
ICONS_CACHE_DIR = DATA_DIR / "icons_cache"
ICONS = DATA_DIR / "icons"

# Crear carpetas si no existen
DATA_DIR.mkdir(parents=True, exist_ok=True)
ICONS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
ICONS.mkdir(parents=True, exist_ok=True)

# ------------------------------
# Archivos locales
# ------------------------------
CONFIG_FILE = DATA_DIR / "config.json"
NOTES_FILE = DATA_DIR / "notas.json"
FLAG_FILE = DATA_DIR / "notify_update.flag"

# ------------------------------
# Archivos para Google Drive
# ------------------------------
TOKEN_PATH = DATA_DIR / "token.json"
CREDENTIALS_PATH = DATA_DIR / "credentials.json"
DRIVE_FOLDER_NAME = "GameLauncherData"
BACKUP_FILE_NAME = "playtime_backup.json"
TEMP_PATH = DATA_DIR / BACKUP_FILE_NAME

# ------------------------------
# Lock global para operaciones de config
# ------------------------------
config_lock = threading.Lock()

# ------------------------------
# Cargar configuración y notas
# ------------------------------
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

# Inicialización de claves globales por defecto
config.setdefault("global", {}).setdefault("cloud_sync_enabled", False)
config.setdefault("global", {}).setdefault("email", None)
config.setdefault("global", {}).setdefault("allow_multiple_games", False)

def remove_temp_path():
    try:
        os.remove(TEMP_PATH)
    except PermissionError:
        print(f"⚠ No se pudo borrar")

