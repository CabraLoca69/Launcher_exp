"""Aísla los tests de la DB real.

`data_access.datafiles` crea `data/` y abre `config.db` al importarse, relativo a
`base_path.get_portable_base_dir()`. Lo redirigimos a un directorio temporal antes
de que cualquier test importe módulos del proyecto.
"""

import tempfile
from pathlib import Path

import pytest

import base_path

_TMP_BASE = Path(tempfile.mkdtemp(prefix="launcher69_tests_"))
base_path.get_portable_base_dir = lambda: _TMP_BASE

from data_access.datafiles import db


@pytest.fixture(autouse=True)
def clean_db():
    """Cada test arranca con la tabla config vacía."""
    with db.lock:
        db.conn.execute("DELETE FROM config")
        db.conn.commit()
    yield db
