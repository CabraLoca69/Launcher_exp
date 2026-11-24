"""Aísla los tests de la DB real.

`data_access.datafiles` crea `data/` y abre `launcher.db` al importarse, relativo a
`base_path.get_portable_base_dir()`. Lo redirigimos a un directorio temporal antes
de que cualquier test importe módulos del proyecto.
"""

import tempfile
from pathlib import Path

import pytest

import base_path

_TMP_BASE = Path(tempfile.mkdtemp(prefix="launcher69_tests_"))
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
