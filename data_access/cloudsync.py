import json
import logging
import os
import tempfile
import threading
from collections.abc import Callable
from io import BytesIO
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from helpers.safe_threading import safe_thread

# --------- imports internos -------
from .datafiles import (
    BACKUP_FILE_NAME,
    CREDENTIALS_PATH,
    DRIVE_FOLDER_NAME,
    TOKEN_PATH,
    store,
)
from .migrate_kv import legacy_row

logger = logging.getLogger(__name__)

# Scopes para Drive (sólo archivos de app)
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# Una sola operación con Drive a la vez: dos subidas en paralelo pueden crear
# dos carpetas o dos backups, y después cada PC lee uno distinto.
_drive_lock = threading.Lock()


# -------------------------
# Google Drive auth & folder
# -------------------------
def login_and_sync(force_new_account: bool = False) -> bool:
    """Login interactivo (abre el navegador) y merge de la nube. Corre en un hilo."""
    backup_path = None
    if force_new_account and TOKEN_PATH.exists():
        backup_path = TOKEN_PATH.with_suffix(".json.bak")
        TOKEN_PATH.replace(backup_path)

    try:
        service = get_drive_service(interactive=True)
    except Exception:
        logger.exception("Falló el login de cloud")
        if backup_path and backup_path.exists():
            backup_path.replace(TOKEN_PATH)
        return False

    if backup_path and backup_path.exists():
        backup_path.unlink()

    try:
        with _drive_lock:
            _merge_from_cloud(service, get_or_create_folder(service))
    except Exception:
        logger.exception("Falló el merge tras un login exitoso")
        return False
    return True


def get_drive_service(interactive: bool = False):
    """Servicio de Drive con las credenciales guardadas.

    Solo con `interactive=True` abre el navegador para loguearse. Los hilos de
    fondo (subidas al cerrar un juego) nunca lo hacen: sin credenciales válidas
    tiran una excepción, que se loguea.
    """
    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            logger.exception("No se pudo leer TOKEN_PATH, reautenticando.")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                logger.exception("No se pudo refrescar las credenciales.")
                creds = None

        if not creds:
            if not interactive:
                raise RuntimeError(
                    "Sin credenciales válidas: hay que iniciar sesión desde Ajustes"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0, timeout_seconds=60)

        with open(TOKEN_PATH, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    if interactive:  # en segundo plano el email ya está guardado
        save_email_to_db(creds)
    return build("drive", "v3", credentials=creds)


def save_email_to_db(creds) -> None:
    """Guarda el email de la cuenta. Sin email, el login no terminó bien."""
    user_info = build("oauth2", "v2", credentials=creds).userinfo().get().execute()
    email = user_info.get("email")
    if not email:
        raise RuntimeError("Login incompleto: Google no devolvió el email")
    store.set_setting("email", email)


def get_or_create_folder(service) -> str:
    query = (
        f"name='{DRIVE_FOLDER_NAME}' and "
        "mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id,name)").execute()
    items = results.get("files", [])
    if items:
        return items[0]["id"]

    file_metadata = {
        "name": DRIVE_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=file_metadata, fields="id").execute()
    return folder["id"]


# -------------------------
# Backup upload / download
# -------------------------
def upload_backup(service, folder_id: str, backup_data: dict[str, Any]) -> None:
    fd, temp_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4, ensure_ascii=False)

        query = (
            f"name='{BACKUP_FILE_NAME}' and '{folder_id}' in parents and trashed=false"
        )
        results = service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])

        media = MediaFileUpload(str(temp_path), mimetype="application/json")

        if items:
            service.files().update(fileId=items[0]["id"], media_body=media).execute()
        else:
            metadata = {"name": BACKUP_FILE_NAME, "parents": [folder_id]}
            service.files().create(
                body=metadata, media_body=media, fields="id"
            ).execute()
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            logger.warning("No se pudo borrar el temporal %s", temp_path)


def download_backup(service, folder_id: str) -> dict[str, Any]:
    """El backup de Drive, o `{}` si todavía no hay ninguno.

    Si existe pero no se puede leer, tira `ValueError`: tratarlo como vacío
    haría que la próxima subida lo pise y se pierdan las horas de otras PCs.
    """
    query = f"name='{BACKUP_FILE_NAME}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get("files", [])

    if not items:
        logger.info("No se encontró backup en Drive.")
        return {}

    request = service.files().get_media(fileId=items[0]["id"])
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    fh.seek(0)
    try:
        return json.load(fh)
    except json.JSONDecodeError as e:
        raise ValueError("El backup de Drive no es un JSON válido") from e


# -------------------------
# Formato del backup
# -------------------------
PAYLOAD_VERSION = 2


def build_payload(sessions: list[dict]) -> dict[str, Any]:
    return {"version": PAYLOAD_VERSION, "sessions": sessions}


def sessions_from_payload(cloud: dict[str, Any]) -> list[dict]:
    """Sesiones de un backup, del formato actual o del viejo (`pc_ids`, sin versión).

    Una versión desconocida (de un launcher más nuevo) tira `ValueError`, así
    esta PC no la pisa con un backup que no la entiende.
    """
    if "version" not in cloud:
        return sessions_from_v1(cloud)
    if cloud["version"] == PAYLOAD_VERSION:
        return list(cloud.get("sessions", []))
    raise ValueError(f"Versión de backup desconocida: {cloud['version']!r}")


def sessions_from_v1(cloud: dict[str, Any]) -> list[dict]:
    """Formato viejo: {"pc_ids": {pc: {plataforma: {juego: minutos}}}} → filas `legacy`.

    Mismos ids que genera la migración local, así el merge las unifica.
    """
    rows = []
    for pc, platforms in (cloud.get("pc_ids") or {}).items():
        if not isinstance(platforms, dict):
            continue
        for platform, games in platforms.items():
            if platform in {"global", "settings", "config"} or not isinstance(
                games, dict
            ):
                continue
            rows += [legacy_row(pc, platform, game, m) for game, m in games.items()]
    return rows


# -------------------------
# Tareas de alto nivel
# -------------------------
def _merge_from_cloud(service, folder_id: str) -> None:
    cloud = download_backup(service, folder_id)
    if cloud:
        store.import_sessions(sessions_from_payload(cloud))


def sync_once(upload: bool) -> None:
    """Trae la nube y la mezcla con lo local; con `upload`, sube el resultado."""
    with _drive_lock:
        service = get_drive_service()
        folder_id = get_or_create_folder(service)
        _merge_from_cloud(service, folder_id)
        if upload:
            upload_backup(service, folder_id, build_payload(store.export_sessions()))


def call_merge(callback: Callable[[], Any] | None = None) -> None:
    def worker():
        try:
            sync_once(upload=False)
            logger.info("Merge cloud->local completado.")
        except Exception:
            logger.exception("Error trayendo el backup de la nube")
        if callback:
            callback()

    safe_thread(worker)
