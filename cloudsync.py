import os
import json
import urllib.request
import threading
from machine_id import get_machine_id
from io import BytesIO
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from datafiles import TOKEN_PATH, CREDENTIALS_PATH, BACKUP_FILE_NAME, DRIVE_FOLDER_NAME, TEMP_PATH, db
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

def get_drive_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
    service = build("drive", "v3", credentials=creds)
    return service, creds

def get_or_create_folder(service):
    query = f"name='{DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id)").execute()
    items = results.get("files", [])
    if items:
        return items[0]["id"]
    # Crear carpeta
    file_metadata = {"name": DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
    folder = service.files().create(body=file_metadata, fields="id").execute()
    return folder["id"]

def upload_backup(service, folder_id, backup_data):
    """
    Sube o actualiza el archivo JSON de backup en Google Drive.
    No descarga ni mezcla datos, solo sube lo que se le pasa.
    """
    temp_path = TEMP_PATH

    # Guardar temporalmente el archivo en disco
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=4)

    try:
        # Buscar si ya existe el archivo en la carpeta de Drive
        query = f"name='{BACKUP_FILE_NAME}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])

        media = MediaFileUpload(str(temp_path), mimetype="application/json")

        if items:
            # Si ya existe, lo actualiza
            service.files().update(fileId=items[0]["id"], media_body=media).execute()
        else:
            # Si no existe, lo crea
            metadata = {"name": BACKUP_FILE_NAME, "parents": [folder_id]}
            service.files().create(body=metadata, media_body=media, fields="id").execute()

    finally:
        try:
            os.remove(temp_path)        
        except PermissionError:
            pass

def download_backup(service, folder_id):
    query = f"name='{BACKUP_FILE_NAME}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get("files", [])

    if not items:
        #print("ℹ️ No se encontró un backup en Drive.")
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
        data = json.load(fh)
        return data
    except json.JSONDecodeError:
        #print("⚠ Error al leer el backup (formato inválido).")
        return {}

def build_cloud_payload_for_upload(existing_data=None):
    pc_id = get_machine_id()

    # Si no hay datos previos, inicializamos
    cloud_data = existing_data or {}
    if "pc_ids" not in cloud_data:
        cloud_data["pc_ids"] = {}

    # Reemplazamos solo la sección de esta PC
    local_data = {}
    for platform, pdata in db.get_all().items():
        if platform == "global":
            continue
        for game, times_by_pc in pdata["game_total_times"].items():
            local_data.setdefault(platform, {})[game] = times_by_pc.get(pc_id, 0.0)

    cloud_data["pc_ids"][pc_id] = local_data
    return cloud_data

def download_and_merge_backup():
    local_config = {}
    local_config = db.get_all()
    
    cloud_data = call_download()
    if not cloud_data:
        return local_config

    merged_config = merge_backup_data(local_config, cloud_data)

    db.data = merged_config
    db.save()
    
    return merged_config

def merge_backup_data(local_config, cloud_data):
    """
    Combina las horas de juego de cloud_data con local_config.
    Solo suma los valores de game_total_times por juego.
    """
    merged = local_config.copy()
    cloud_pc_data = cloud_data.get("pc_ids", {}) # obtenemos los datos de todas las pc
    for cloud_pc, platforms in cloud_pc_data.items():
        for platform, pdata in platforms.items():
            if platform not in merged:
                merged[platform] = {}

            # Cada juego guarda un dict con pc_id como key
            local_games = merged[platform].setdefault("game_total_times", {})
            for game, time in pdata.items():
                game_times_by_pc = local_games.setdefault(game, {})
                # Si no existe tiempo para esta PC, lo inicializamos
                game_times_by_pc[cloud_pc] = max(game_times_by_pc.get(cloud_pc, 0.0), float(time)) 
           
    return merged

def has_internet_http(url="https://www.google.com", timeout=5):
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False
    
def call_merge():
    def worker():
        if not has_internet_http():
            return
        download_and_merge_backup()
    threading.Thread(target=worker, daemon=True).start()
    
def call_upload():
    def worker():
        if not has_internet_http():
            return
        service, creds= get_drive_service()
        folder = get_or_create_folder(service)
        data= build_cloud_payload_for_upload(call_download())
        upload_backup(service, folder, data)
    threading.Thread(target=worker, daemon=True).start()     

def call_download():
    if not has_internet_http():
        return
    service, creds= get_drive_service()
    folder = get_or_create_folder(service)
    return download_backup(service, folder)
