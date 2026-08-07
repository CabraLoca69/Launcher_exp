import os
import logging
import threading
import psutil
import time
import sys
import json
import glob
from pathlib import Path
from datetime import datetime

from data_access.machine_id import get_machine_id
from data_access.cloudsync import call_upload
from data_access.datafiles import ICONS, ICONS_CACHE_DIR, db

from helpers.safe_threading import safe_thread

from platform_adapters.platform_handler import PlatformHandler

from interface_files.ui_handler import get_event_bus

class FileManager():
    def __init__(self):
        self.grouped = True
        pass
    
    def add_folder(self, platform_name, folder):  # agrega un directorio a la lista   
        # Asegura que exista la estructura base de la plataforma
        db.ensure(f"{platform_name}.platform_folders", [])
        db.ensure(f"{platform_name}.favorites", [])
        
        # Ahora agregamos la carpeta si no está
        folders = db.get(f"{platform_name}.platform_folders")
        if folder not in folders:
            folders.append(folder)
            db.set(f"{platform_name}.platform_folders", folders)

        self.scan_for_games(platform_name)
        return folder

    def add_game(self, platform_name: str, exe_path: str) -> tuple[bool, str]:
        exe_name = os.path.splitext(os.path.basename(exe_path))[0]
        key = f"{platform_name}.game_list.{exe_name}"

        if db.get(key) is not None:
            return False, f"Ya existe un juego llamado '{exe_name}' en esta plataforma."

        self._set_game_path(platform_name, exe_name, exe_path)
        return True, exe_name

    def _set_game_path(self, platform_name: str, exe_name: str, exe_path: str) -> None:
        db.set(f"{platform_name}.game_list.{exe_name}", exe_path)

    def delete_game(self, platform_name: str, game_name: str):
        with db.lock:
            game_path = db.get(f"{platform_name}.game_list.{game_name}")
            if game_path:
                self.remove_game_icon(game_path)

            db.delete(f"{platform_name}.game_list.{game_name}")
            db.delete(f"{platform_name}.game_times.{game_name}")
            db.delete(f"{platform_name}.game_total_times.{game_name}")

            favorites = db.get(f"{platform_name}.favorites", default=[])
            if game_name in favorites:
                favorites.remove(game_name)
                db.set(f"{platform_name}.favorites", favorites)

    def delete_folder(self, platform_name: str, folder_path: str):
        removed_games = []

        with db.lock:
            game_list = db.get_children(f"{platform_name}.game_list")
            for game_name, game_path in game_list.items():
                if folder_path in game_path:
                    self.delete_game(platform_name, game_name)
                    removed_games.append(game_name)

            folders = db.get(f"{platform_name}.platform_folders", default=[])
            new_folders = [f for f in folders if f != folder_path]
            db.set(f"{platform_name}.platform_folders", new_folders)

        return removed_games
    
    def rename_platform(old_name: str, new_name: str) -> bool:
        with db.lock:
            tab_order = db.get("global.tab_order", default=[])
            if old_name not in tab_order:
                return False

            db.rename_prefix(old_name, new_name)  

            index = tab_order.index(old_name)
            tab_order[index] = new_name
            db.set("global.tab_order", tab_order)

        return True

    def scan_for_games(self, platform_name):
        ignore_keywords = [
            kw.lower() for kw in [
                "vc_redist", "unins", "setup", "install", "dxsetup", "report",
                "dotnet", "readme", "helper", "support", "launcher", "win64"
            ]
        ]

        folders = db.get(f"{platform_name}.platform_folders", [])

        for path in folders:
            if not os.path.isdir(path):
                continue

            for root, _, files in os.walk(path):
                for file in files:
                    full_path = os.path.join(root, file)

                    if not PlatformHandler().get("exedetect").is_executable(full_path):
                        continue

                    if any(k in file.lower() for k in ignore_keywords):
                        continue

                    key = os.path.splitext(file)[0]
                    db.set(f"{platform_name}.game_list.{key}", full_path)
        
    def sort_key(self, game_name, game_times):
        sessions = game_times.get(game_name, [])
        if sessions:
            try:
                last_played = datetime.strptime(sessions[-1]["Start"], "%Y-%m-%d %H:%M:%S")
                return (0, -last_played.timestamp())
            except ValueError:
                return (0, float('-inf'))
        return (1, game_name.lower())    

    def remove_game_icon(self, game_path):
        if not game_path:
            return
            
        base_name = Path(os.path.basename(game_path)).stem
        icon_pattern = os.path.join(ICONS_CACHE_DIR , base_name + ".*") 

        # Buscar y eliminar cualquier archivo que coincida
        for icon_file in glob.glob(icon_pattern):
            try:
                os.remove(icon_file)

            except OSError as e:
                print(f"No se pudo eliminar {icon_file}: {e}")