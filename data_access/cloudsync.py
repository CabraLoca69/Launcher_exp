# cloud_sync.py
import os
import json
import tempfile
import logging
import urllib.request
from io import BytesIO
from typing import Any, Dict

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

#--------- imports internos -------
from .datafiles import TOKEN_PATH, CREDENTIALS_PATH, BACKUP_FILE_NAME, DRIVE_FOLDER_NAME, store
from .migrate_kv import legacy_row

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
    last_email = store.get_setting("email")
    if force_new_account and TOKEN_PATH.exists():
        backup_path = TOKEN_PATH.with_suffix(".json.bak")
        TOKEN_PATH.replace(backup_path)
    
    def _rollback():
        store.set_setting("email", last_email)
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
    if store.get_setting("email") == "Desconocido":
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
    store.set_setting("email", "Desconocido")
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
    store.set_setting("email", user_info)

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
# Formato del backup
# -------------------------
PAYLOAD_VERSION = 2


def build_payload(sessions: list[dict]) -> Dict[str, Any]:
    return {"version": PAYLOAD_VERSION, "sessions": sessions}


def sessions_from_payload(cloud: Dict[str, Any]) -> list[dict]:
    """Sesiones contenidas en un backup, sea del formato actual o del viejo (`pc_ids`)."""
    if cloud.get("version") == PAYLOAD_VERSION:
        return list(cloud.get("sessions", []))
    return sessions_from_v1(cloud)


def sessions_from_v1(cloud: Dict[str, Any]) -> list[dict]:
    """Formato viejo: {"pc_ids": {pc: {plataforma: {juego: minutos}}}} → filas `legacy`.

    Mismos ids que genera la migración local, así el merge las unifica.
    """
    rows = []
    for pc, platforms in (cloud.get("pc_ids") or {}).items():
        if not isinstance(platforms, dict):
            continue
        for platform, games in platforms.items():
            if platform in {"global", "settings", "config"} or not isinstance(games, dict):
                continue
            rows += [legacy_row(pc, platform, game, m) for game, m in games.items()]
    return rows


# -------------------------
# Tareas de alto nivel
# -------------------------
def _merge_from_cloud(service, folder_id) -> None:
    cloud = download_backup(service, folder_id)
    if cloud:
        store.import_sessions(sessions_from_payload(cloud))


def download_and_merge_backup() -> None:
    try:
        if not has_internet_http():
            logging.info("No hay conexión. Abortando descarga merge.")
            return
        service = get_drive_service()
        _merge_from_cloud(service, get_or_create_folder(service))
        logging.info("Merge cloud->local completado.")
    except Exception:
        logging.exception("Error en download_and_merge_backup:")


def call_merge(callback=None):
    def worker():
        download_and_merge_backup()
        if callback:
            try:
                callback()
            except Exception:
                logging.exception("Error en callback post-merge:")

    safe_thread(worker)


def call_upload():
    """Trae lo que haya en la nube, lo mezcla con lo local y sube el resultado completo."""
    def worker():
        try:
            if not has_internet_http():
                logging.info("No internet, abort upload.")
                return
            service = get_drive_service()
            folder_id = get_or_create_folder(service)
            _merge_from_cloud(service, folder_id)
            upload_backup(service, folder_id, build_payload(store.export_sessions()))
            logging.info("Backup subido correctamente.")
        except Exception:
            logging.exception("Error en call_upload()")

    safe_thread(worker)
