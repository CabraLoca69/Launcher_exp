import sys
from pathlib import Path
from jsondb import JsonDatabase
from sqlitedb import SQLiteDatabase

# ------------------------------
# Directorios de datos
# ------------------------------
def get_portable_base_dir():
    if getattr(sys, "frozen", False):  
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent

BASE_DIR = get_portable_base_dir()

DATA_DIR = BASE_DIR / "data"
ICONS_CACHE_DIR = DATA_DIR / "icons_cache"
ICONS = DATA_DIR / "icons"

# Crear carpetas si no existen
DATA_DIR.mkdir(parents=True, exist_ok=True)
ICONS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
ICONS.mkdir(parents=True, exist_ok=True)

# ------------------------------
# Archivos locales
# ------------------------------
CONFIG_FILE = DATA_DIR / "config.db"
NOTES_FILE = DATA_DIR / "notas.json"

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
db = SQLiteDatabase(CONFIG_FILE)
notes_db = JsonDatabase(NOTES_FILE)

db.ensure("global.cloud_sync_enabled", False)
db.ensure("global.email", None)
db.ensure("global.allow_multiple_games", True)
db.ensure("global.tab_order", [])
db.ensure("global.last_selected_tab", None)
db.ensure("global.actual_sessions", {})
db.ensure("global.actual_running", {})


