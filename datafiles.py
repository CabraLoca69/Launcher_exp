import os
import sys
import json
import threading

BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

# Carpeta de datos 
DATA_DIR = os.path.join(BASE_DIR, "data")
ICONS_CACHE_DIR = os.path.join(DATA_DIR, "icons_cache")
ICONS = os.path.join(DATA_DIR, "icons")

# Crear carpetas si no existen
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ICONS_CACHE_DIR, exist_ok=True)

# Archivos
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
NOTES_FILE = os.path.join(DATA_DIR, "notas.json")
FLAG_FILE = os.path.join(DATA_DIR, "notify_update.flag")

# Lock global para operaciones con config
config_lock = threading.Lock()

# Cargar configuración
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = {}

if os.path.exists(NOTES_FILE):
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        notas = json.load(f)
else : 
    notas = {}

if "global" not in config:
    config.setdefault("global", {}).setdefault("allow_multiple_games", False)
