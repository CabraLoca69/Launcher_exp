# Launcher69

Launcher de escritorio (Windows y Linux) que trackea el tiempo de juego de cualquier ejecutable y lo sincroniza con Google Drive. UI principal en PySide6 (`interface_files/qt_*`); la UI Tk (`--tk`) es legado.

## Comandos
- Entorno: `source venv/bin/activate` (venv dentro del proyecto, Python 3.14).
- Instalar deps: `pip install -r requirements.txt`.
- Herramientas de dev: `pip install pytest ruff mypy` (ya instaladas en el venv).
- Correr: `python launcher69.py` (Qt), `--tk` (UI vieja), `--launch "<nombre>"` (lanza un juego sin UI y registra la sesión).
- Tests: `pytest -q`. `tests/conftest.py` redirige `data/` a un directorio temporal.
- Lint y formato: `ruff check . && ruff format .`
- Tipos: `mypy .`

## Gotchas
- Al importar, `data_access/datafiles.py` crea `data/` y abre `data/databases/config.db`, relativo a la raíz del proyecto (o al ejecutable congelado). En los tests, apuntá a una DB temporal y dejá intacta la real.
- La DB es un key-value con claves `plataforma.seccion.nombre`: ningún segmento puede tener `.`. El nombre de un juego sale de `PlatformHandler().get("exedetect").game_name(path)`, que quita la extensión según el SO y aplica `key_segment` (`data_access/keys.py`).
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
