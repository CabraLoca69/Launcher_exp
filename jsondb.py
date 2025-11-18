import json
import threading
from pathlib import Path
from typing import Any, Union, List


class JsonDatabase:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.lock = threading.RLock()
        self.data = {}

        if not self.file_path.exists():
            self._save_raw({})

        self._load_raw()

    # ---------------- RAW IO ----------------
    def _load_raw(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def _save_raw(self, data):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    # ---------------- PATH RESOLUTION ----------------
    def _resolve_path(self, keypath: Union[str, List[str]], create_missing: bool = False):
        """
        Devuelve (ref, final_key)
        """
        # Aceptar tanto string como lista
        if isinstance(keypath, str):
            parts = keypath.split(".")
        elif isinstance(keypath, list):
            parts = keypath
        else:
            raise TypeError("keypath debe ser str o list[str]")

        *parents, final = parts

        ref = self.data
        for p in parents:
            if p not in ref:
                if create_missing:
                    ref[p] = {}
                else:
                    return None, None
            ref = ref[p]

        return ref, final

    # ---------------- PUBLIC API ----------------
    def reload(self):
        with self.lock:
            self._load_raw()

    def save(self):
        with self.lock:
            self._save_raw(self.data)

    # ---------- GET ----------
    def get(self, keypath: Union[str, List[str]], default: Any = None) -> Any:
        with self.lock:
            ref, final = self._resolve_path(keypath, create_missing=False)
            if ref is None or final not in ref:
                return default
            return ref[final]

    # ---------- SET ----------
    def set(self, keypath: Union[str, List[str]], value: Any) -> None:
        with self.lock:
            ref, final = self._resolve_path(keypath, create_missing=True)
            ref[final] = value
            self.save()

    # ---------- DELETE ----------
    def delete(self, keypath: Union[str, List[str]]) -> bool:
        with self.lock:
            ref, final = self._resolve_path(keypath, create_missing=False)
            if ref is None or final not in ref:
                return False
            del ref[final]
            self.save()
            return True

    # ---------- UPDATE ----------
    def update(self, keypath: Union[str, List[str]], func) -> Any:
        with self.lock:
            ref, final = self._resolve_path(keypath, create_missing=True)
            old = ref.get(final, None)
            new = func(old)
            ref[final] = new
            self.save()
            return new

    # ---------- ENSURE ----------
    def ensure(self, keypath: Union[str, List[str]], default: Any) -> Any:
        with self.lock:
            ref, final = self._resolve_path(keypath, create_missing=True)
            if final not in ref:
                ref[final] = default
                self.save()
            return ref[final]
