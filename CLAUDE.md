# Launcher69

Launcher de escritorio (Windows y Linux) que trackea el tiempo de juego de cualquier ejecutable y lo sincroniza con Google Drive. UI en PySide6 (`interface_files/qt_*`). La UI Tk se eliminó: la última versión con ella es el tag `ultima-version-tk`.

## Comandos
- Entorno: `source venv/bin/activate` (venv dentro del proyecto, Python 3.14).
- Instalar deps: `pip install -r requirements.txt`.
- Herramientas de dev: `pip install pytest ruff mypy` (ya instaladas en el venv).
- Correr: `python launcher69.py` (UI), `--launch "<juego>" [--platform "<plataforma>"]` (lanza un juego sin UI y registra la sesión).
- Tests: `pytest -q`. `tests/conftest.py` redirige `data/` a un directorio temporal.
- Lint y formato: `ruff check . && ruff format .`
- Tipos: `mypy .`

## Gotchas
- Al importar, `data_access/datafiles.py` crea `data/` y abre `data/databases/launcher.db`, relativo a la raíz del proyecto (o al ejecutable congelado). En los tests, apuntá a una DB temporal y dejá intacta la real.
- Todo el SQL vive en `data_access/store.py`; el resto del código usa sus métodos (`store.add_game`, `store.total_seconds`, ...). Esquema y reglas de sesiones (`session`/`month`/`legacy`, uuid para cloud sync) en el docstring de ese archivo.
- Borrar un juego o una plataforma los **oculta** (`hidden` / `position NULL`); las horas jugadas se conservan.
- `config.db`/`notas.db` son la DB vieja: `data_access/migrate_kv.py` la migra una sola vez al arrancar y no la modifica.
- El nombre de un juego sale de `PlatformHandler().get("exedetect").game_name(path)`, que quita la extensión según el SO.
- El código específico de cada SO va en `platform_adapters/` y se obtiene con `PlatformHandler().get(...)`.
- Cloud sync necesita `data/cloud_files/credentials.json` (no versionado). Sin ese archivo, falla y se loguea; la app sigue funcionando.

## Convenciones
- Type hints en funciones públicas.
- Tests en `tests/`, un archivo por módulo (`test_<modulo>.py`).
- Funciones chicas, sin código muerto. Avisar antes de agregar una dependencia de runtime.
- Errores con `logging`, no `print`.
- Tarea terminada = tests, ruff y mypy en verde.

## Al responder
- Cada vez que nombres una función, clase o método, indicá dónde vive como `ruta/archivo.py:línea`.

## Flujo de trabajo
- Cambios no triviales: agente `planner` → implementar → `test-writer` → `code-reviewer`.
- Ante un fallo, usar `debugger` antes de adivinar.
