import os
import sys
from pathlib import Path
from jsondb import JsonDatabase

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
# Cargar configuración y notas
# ------------------------------
db = JsonDatabase(CONFIG_FILE)
notes_db = JsonDatabase(NOTES_FILE)

db.ensure("global.cloud_sync_enabled", False)
db.ensure("global.email", None)
db.ensure("global.allow_multiple_games", False)
db.ensure("global.tab_order", [])
db.ensure("global.last_selected_tab", None)
db.ensure("global.actual_sessions", {})
db.ensure("global.actual_running", {})


