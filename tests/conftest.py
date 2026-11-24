"""Aísla los tests de la DB real.

`data_access.datafiles` crea `data/` y abre `launcher.db` al importarse, relativo a
`base_path.get_portable_base_dir()`. Lo redirigimos a un directorio temporal antes
de que cualquier test importe módulos del proyecto.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

import base_path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # tests de UI sin pantalla

_TMP_BASE = Path(tempfile.mkdtemp(prefix="launcher69_tests_"))
# Íconos y temas propios del launcher (los usa la UI)
for _folder in ("icons", "themes"):
    shutil.copytree(
        Path(__file__).parent.parent / "data" / _folder, _TMP_BASE / "data" / _folder
    )
base_path.get_portable_base_dir = lambda: _TMP_BASE

from data_access.datafiles import store as _store

_TABLES = ("sessions", "games", "platform_folders", "platforms", "settings")


@pytest.fixture(autouse=True)
def store():
    """Cada test arranca con la DB vacía."""
    with _store.lock, _store.conn:
        for table in _TABLES:
            _store.conn.execute(f"DELETE FROM {table}")
    yield _store
