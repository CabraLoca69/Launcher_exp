# cloud_sync.py
import os
import json
import tempfile
import logging
import urllib.request
from io import BytesIO
from typing import Dict, Any

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

#--------- imports internos -------
from .datafiles import TOKEN_PATH, CREDENTIALS_PATH, BACKUP_FILE_NAME, DRIVE_FOLDER_NAME, db
from .machine_id import get_machine_id

from helpers.safe_threading import safe_thread

# Scopes para Drive (sólo archivos de app)
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]


# -------------------------
# Utilidades para internet
# -------------------------
def has_internet_http(url: str = "https://www.google.com", timeout: int = 5) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


# -------------------------
# Google Drive auth & folder
# -------------------------
def login_and_sync(force_new_account: bool = False):
    backup_path = None
    last_email = db.get("global.email")
    if force_new_account and TOKEN_PATH.exists():
        backup_path = TOKEN_PATH.with_suffix(".json.bak")
        TOKEN_PATH.replace(backup_path)
    
    def _rollback():
        db.set("global.email", last_email)
        if backup_path and backup_path.exists():
            backup_path.replace(TOKEN_PATH)

    try:
        get_drive_service()
    except Exception:
        logging.exception("Fallo el login/merge de cloud")
        _rollback()
        return False

    # get_drive_service no tiró excepción, pero eso no garantiza
    # que el login haya terminado bien (ej: usuario cerró la pestaña)
    if db.get("global.email") == "Desconocido":
        logging.error("Login incompleto o cancelado (email sigue en 'Desconocido')")
        _rollback()
        return False

    try:
        call_merge()
    except Exception:
        logging.exception("Fallo el merge tras login exitoso")
        return False

    if backup_path and backup_path.exists():
        backup_path.unlink()

    return True

def get_drive_service():
    creds = None
    db.set("global.email", "Desconocido")
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception:
            logging.exception("No se pudo leer TOKEN_PATH, reautenticando.")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                logging.exception("No se pudo refrescar credenciales. Hará login interactivo.")
                creds = None

        if not creds:
            # flujo interactivo en local
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0, timeout_seconds=60)

        # persistir token
        with open(TOKEN_PATH, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    save_email_to_db(creds)
    service = build("drive", "v3", credentials=creds)
    return service

def save_email_to_db(creds):
    service = build("oauth2", "v2", credentials=creds)
    user_info = service.userinfo().get().execute()
    user_info = user_info.get("email", "Desconocido")
    db.set("global.email", user_info)

def get_or_create_folder(service):
    query = f"name='{DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id,name)").execute()
    items = results.get("files", [])
    if items:
        return items[0]["id"]

    file_metadata = {"name": DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
    folder = service.files().create(body=file_metadata, fields="id").execute()
    return folder["id"]


# -------------------------
# Flatten / Rebuild helpers
# -------------------------
def flatten_config(nested: Dict[str, Any], prefix: str = "", exclude=("global",)) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in nested.items():
        if key in exclude:
            continue
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten_config(value, full, exclude))
        else:
            out[full] = value
    return out


def rebuild_nested_config(flat: Dict[str, Any]) -> Dict[str, Any]:
    root: Dict[str, Any] = {}
    for full_key, value in flat.items():
        parts = full_key.split(".")
        ref = root
        for p in parts[:-1]:
            if p not in ref or not isinstance(ref[p], dict):
                ref[p] = {}
            ref = ref[p]
        ref[parts[-1]] = value
    return root


# -------------------------
# DB helpers (compat con SQLite key-value)
# -------------------------
def write_full_config_to_db(nested_config: Dict[str, Any]):
    flat = flatten_config(nested_config)
    for key, value in flat.items():
        db.set(key, value)


def read_full_config_from_db() -> Dict[str, Any]:
    flat = db.get_all()  # devuelve dict plano key->value
    return rebuild_nested_config(flat)


# -------------------------
# Backup upload / download
# -------------------------
def upload_backup(service, folder_id, backup_data: Dict[str, Any]):
    # archivo temporal
    fd, temp_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4, ensure_ascii=False)

        # buscar archivo existente
        query = f"name='{BACKUP_FILE_NAME}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])

        media = MediaFileUpload(str(temp_path), mimetype="application/json")

        if items:
            service.files().update(fileId=items[0]["id"], media_body=media).execute()
        else:
            metadata = {"name": BACKUP_FILE_NAME, "parents": [folder_id]}
            service.files().create(body=metadata, media_body=media, fields="id").execute()

    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass


def download_backup(service, folder_id) -> Dict[str, Any]:
    query = f"name='{BACKUP_FILE_NAME}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get("files", [])

    if not items:
        logging.info("No se encontró backup en Drive.")
        return {}

    file_id = items[0]["id"]
    request = service.files().get_media(fileId=file_id)
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.seek(0)
    try:
        return json.load(fh)
    except json.JSONDecodeError:
        logging.error("Error al leer el backup descargado (JSON inválido).")
        return {}
    except Exception:
        logging.exception("Error inesperado leyendo backup.")
        return {}


# -------------------------
# Cloud payload / merge
# -------------------------
def build_cloud_payload_for_upload(existing_cloud_data: Dict[str, Any] = None) -> Dict[str, Any]:
    pc_id = get_machine_id()
    cloud_data = existing_cloud_data.copy() if existing_cloud_data else {}
    cloud_data.setdefault("pc_ids", {})

    nested = read_full_config_from_db()

    # nested tiene estructura: { "steam": { "game_total_times": { "Game": { "pc1": 123.0 }}}}
    local_data: Dict[str, Dict[str, float]] = {}

    for platform, pdata in nested.items():
        if platform == "global":
            continue
        gtot = pdata.get("game_total_times", {})
        if not isinstance(gtot, dict):
            continue
        for game, by_pc in gtot.items():
            # by_pc puede ser dict or simple float (compat con viejos)
            if isinstance(by_pc, dict):
                total_for_this_pc = by_pc.get(pc_id, 0.0)
            else:
                total_for_this_pc = float(by_pc or 0.0)
            local_data.setdefault(platform, {})[game] = total_for_this_pc

    cloud_data["pc_ids"][pc_id] = local_data
    return cloud_data


def merge_backup_data(local_nested: Dict[str, Any], cloud_data: Dict[str, Any]) -> Dict[str, Any]:
    merged = json.loads(json.dumps(local_nested))  # deep copy

    cloud_pc_data = cloud_data.get("pc_ids", {}) or {}
    INVALID_ROOTS = {"global", "settings", "config"}

    for cloud_pc, platforms in cloud_pc_data.items():
        for platform, games in platforms.items():
            
            # No mezclar nodos internos del launcher
            if platform.split(".")[0] in INVALID_ROOTS:
                continue

            if not isinstance(games, dict):
                continue

            platform_node = merged.setdefault(platform, {})
            local_game_totals = platform_node.setdefault("game_total_times", {})

            for game, time_val in games.items():
                time_val = float(time_val or 0.0)

                local_by_pc = local_game_totals.setdefault(game, {})

                if not isinstance(local_by_pc, dict):
                    local_game_totals[game] = {"__legacy": float(local_by_pc)}
                    local_by_pc = local_game_totals[game]

                prev = local_by_pc.get(cloud_pc, 0.0)
                local_by_pc[cloud_pc] = max(prev, time_val)

    return merged

# -------------------------
# High level tasks
# -------------------------
def download_and_merge_backup():
    try:
        if not has_internet_http():
            logging.info("No hay conexión. Abortando descarga merge.")
            return read_full_config_from_db()

        service = get_drive_service()
        folder_id = get_or_create_folder(service)
        cloud = download_backup(service, folder_id)
        if not cloud:
            logging.info("No hay backup en la nube o está vacío.")
            return read_full_config_from_db()

        local_nested = read_full_config_from_db()
        merged = merge_backup_data(local_nested, cloud)

        # escribir merged a la DB plano
        write_full_config_to_db(merged)
        logging.info("Merge cloud->local completado y guardado.")
        return merged

    except Exception:
        logging.exception("Error en download_and_merge_backup:")
        return read_full_config_from_db()


def call_merge(callback = None):
    def worker():
        merged = download_and_merge_backup()
        if callback:
            try:
                callback(merged)
            except Exception:
                logging.exception("Error en callback post-merge:")
    
    safe_thread(worker)


def call_upload():
    def worker():
        try:
            if not has_internet_http():
                logging.info("No internet, abort upload.")
                return

            service = get_drive_service()
            folder_id = get_or_create_folder(service)
            existing = download_backup(service, folder_id) or {}
            payload = build_cloud_payload_for_upload(existing)
            upload_backup(service, folder_id, payload)
            logging.info("Backup subido correctamente.")
        except Exception:
            logging.exception("Error en call_upload()")

    safe_thread(worker)


def call_download():
    if not has_internet_http():
        return {}
    try:
        service = get_drive_service()
        folder_id = get_or_create_folder(service)
        return download_backup(service, folder_id)
    except Exception:
        logging.exception("call_download error")
        return {}