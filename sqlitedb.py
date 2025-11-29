import sqlite3
import json
import threading
from typing import Any, Union, List

import traceback

class SQLiteDatabase:
    def __init__(self, file_path: str):
        self.conn = sqlite3.connect(file_path, check_same_thread=False)
        self.lock = threading.RLock()

        self._setup()

    # ---------------- INTERNAL ----------------
    def _setup(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            self.conn.commit()

    def _resolve_path(self, keypath: Union[str, List[str]]) -> str:
        """Convierte listas en clave tipo 'a.b.c'."""
        if isinstance(keypath, list):
            return ".".join(keypath)
        return keypath

    # ---------------- PUBLIC API ----------------
    def get(self, keypath: Union[str, List[str]], default=None):
        key = self._resolve_path(keypath)

        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT value FROM config WHERE key=?", (key,))
            row = cur.fetchone()

        if row is None:
            return default

        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return default

    def set(self, keypath: Union[str, List[str]], value: Any):
        key = self._resolve_path(keypath)
        value_json = json.dumps(value, ensure_ascii=False)

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO config(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value_json)
            )
            self.conn.commit()

    #eso es el debug de set, activarlo para ver quien escrible en la db
    """def set(self, key, value):
        print(f"\n[DEBUG] set(): key={key}")
        traceback.print_stack()
        self._set_db(key, value)"""

    def delete(self, keypath: Union[str, List[str]]):
        key = self._resolve_path(keypath)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM config WHERE key=?", (key,))
            self.conn.commit()
            return cur.rowcount > 0

    def ensure(self, keypath, default):
        current = self.get(keypath)
        if current is None:
            self.set(keypath, default)
            return default
        return current

    def delete_prefix(self, prefix: str):
        """Borra todas las claves que empiecen por 'prefix.' """
        with self.lock:
            cur = self.conn.cursor()
            like_pattern = prefix + ".%"
            cur.execute("DELETE FROM config WHERE key LIKE ?", (like_pattern,))
            self.conn.commit()

    def update(self, keypath, func):
        key = self._resolve_path(keypath)
        old = self.get(key)
        new = func(old)

        self.set(key, new)
        return new

    def get_all(self) -> dict:
        """Devuelve un diccionario con todas las claves tipo a.b.c."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT key, value FROM config")
            rows = cur.fetchall()

        result = {}
        for key, value_json in rows:
            try:
                result[key] = json.loads(value_json)
            except:
                result[key] = None
        return result
    
    def get_children(self, prefix: str) -> dict:
        prefix_str = prefix + "."
        plen = len(prefix_str)

        children = {}

        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT key, value FROM config WHERE key LIKE ?", (prefix_str + "%",))
            rows = cur.fetchall()

        for key, value_json in rows:
            subkey = key[plen:]  # lo que queda después de prefix.

            # Solo tomamos hijos directos, no nietos.
            if "." in subkey:
                continue
        
            try:
                children[subkey] = json.loads(value_json)
            except:
                children[subkey] = None

        return children
    


