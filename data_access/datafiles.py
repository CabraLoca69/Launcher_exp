from .sqlitedb import SQLiteDatabase
from base_path import get_portable_base_dir

# ------------------------------
# Directorios de datos
# ------------------------------
BASE_DIR = get_portable_base_dir()

DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR / "databases"
ICONS_CACHE_DIR = DATA_DIR / "icons_cache"
ICONS = DATA_DIR / "icons"
CLOUD = DATA_DIR / "cloud_files"
MACHINE_ID_FILE = CLOUD / "machine_id.txt"
THEMES_DIR = DATA_DIR / "themes"

# Crear carpetas si no existen
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
ICONS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
ICONS.mkdir(parents=True, exist_ok=True)
CLOUD.mkdir(parents=True, exist_ok=True)
THEMES_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------
# Archivos locales
# ------------------------------
CONFIG_FILE = DB_DIR / "config.db"
NOTES_FILE = DB_DIR / "notas.db"

# ------------------------------
# Archivos para Google Drive
# ------------------------------
TOKEN_PATH = CLOUD / "token.json"
CREDENTIALS_PATH = CLOUD / "credentials.json"
DRIVE_FOLDER_NAME = "GameLauncherData"
BACKUP_FILE_NAME = "playtime_backup.json"

# ------------------------------
# Cargar configuración y notas
# ------------------------------
db = SQLiteDatabase(CONFIG_FILE)
notes_db = SQLiteDatabase(NOTES_FILE)

db.ensure("global.cloud_sync_enabled", False)
db.ensure("global.email", None)
db.ensure("global.allow_multiple_games", True)
db.ensure("global.tab_order", [])
db.ensure("global.last_selected_tab", None)

