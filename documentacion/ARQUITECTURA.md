# Arquitectura — Launcher_exp

Este documento explica **cómo está organizado el proyecto y qué responsabilidad tiene cada módulo**. No entra en detalle de funciones internas (eso va en `FUNCIONES.md`); acá el objetivo es que en 2 minutos te ubiques en qué carpeta/archivo tocar cuando necesites cambiar algo.

## Vista general (capas)

El proyecto está organizado en capas, de abajo (datos crudos) hacia arriba (interfaz visible):

```
launcher69.py            ← entry point
        │
        ▼
interface_files/         ← UI (Qt / PySide6)
        │
        ▼
helpers/                 ← lógica de negocio / orquestación
        │
        ▼
platform_adapters/       ← comportamiento según SO
        │
        ▼
data_access/             ← persistencia (db local + cloud)
        │
        ▼
data/                    ← archivos crudos (db, iconos, cloud config)
```

La idea de fondo: **la interfaz no accede directo a datos ni al SO**; pasan siempre por `helpers/`, que a su vez delega en `platform_adapters/` (si depende del SO) o en `data_access/` (si es persistencia).

---

## `/data`
Carpeta de contenido, no de código. Guarda todo lo que el programa lee/escribe en runtime.

| Subcarpeta | Contenido |
|---|---|
| `cloud_files/` | Credenciales/config necesarias para acceder a Google Drive |
| `databases/` | Bases de datos SQLite usadas por el programa |
| `icons/` | Iconos propios del launcher (UI) |
| `icons_cache/` | Iconos de ejecutables ya extraídos/cacheados (para no reprocesar), nombrados por un hash de la ruta del juego |
| `themes/` | Temas: plantilla `base.qss` + una paleta `.json` por tema |

---

## `/data_access`
Todo lo que toca **persistencia**: base de datos local y sincronización en la nube.

- **`store.py`** — la base de datos en sí: esquema (tablas `platforms`, `platform_folders`, `games`, `sessions`, `settings`) y **todo** el SQL del proyecto. El resto del código usa sus métodos con nombre de negocio.
- **`datafiles.py`** — resuelve los *paths* de los archivos de datos y crea la instancia `store`.
- **`migrate_kv.py`** — migración única desde la DB clave-valor vieja (`config.db` + `notas.db`) a `launcher.db`.
- **`machine_id.py`** — genera/provee el ID único de la máquina; cada sesión de juego lo guarda.
- **`cloudsync.py`** — sincronización con Google Drive: sube/baja la lista de sesiones y la mezcla con la local.

---

## `/helpers`
La capa de **lógica de negocio**: es el "backend" real del launcher, entre la UI y los datos/SO.

- **`data_manager.py`** — arma los datos que muestra la UI y maneja favoritos (habla con `data_access/store.py`).
- **`file_manager.py`** — backend de manejo de programas (escaneo de directorios, altas/bajas de ejecutables).
- **`games_launcher.py`** — backend del lanzamiento de juegos/programas.
- **`safe_threading`** — se encarga de lanzar hilos (para no bloquear la UI, ej. durante escaneos largos).
- **`db_qwatcher.py`** — vigila (con un timer de Qt) si terminó un juego que corre en otro proceso.
- **`icon_utils.py`** — convierte `.ico` → `.png` (lo usan `qicon_utils.py` e `icons_handler.py`).
- **`qicon_utils.py`** — carga íconos como `QIcon`.

---

## `/interface_files`
Todo lo visual, en Qt/PySide6. La UI Tk se eliminó (la última versión que la tiene es el tag `ultima-version-tk`).

- **`ui_handler.py`** — genera el `event_bus` (Qt, o uno vacío para `--launch`). Es el punto de entrada de esta capa.
- **`event_bus.py`** — avisa a la UI cuando un juego arranca o termina.
- **`qt_interface.py`**, **`qt_menus_renderer.py`**, **`qt_popups.py`** — la interfaz, sus menús y sus diálogos.
- **`themes.py`** — lee las paletas de `data/themes/` y arma la hoja de estilos desde `base.qss`.

---

## `/platform_adapters`
Todo lo que **cambia de comportamiento según el sistema operativo**. Patrón strategy/factory: un "handler" central elige la implementación correcta.

- **`platform_handler.py`** — el factory/strategy: elige el comportamiento de todos los scripts de este directorio según el SO detectado.
- **`executables_handler.py`** — qué es un ejecutable en cada SO y cómo se llama el juego (quita la extensión según el SO).
- **`icons_handler.py`** — extracción/manejo de iconos según SO.
- **`menus_handler.py`** — opciones de menús según SO.
- **`paths_handler.py`** — normalización/resolución de paths según SO.
- **`runners_handler.py`** — lanza los programas (el "run" real del ejecutable).
- **`shortcuts_handler.py`** — creación de accesos directos.

---

## Raíz del proyecto

- **`base_path.py`** — provee el directorio raíz del proyecto (referencia para todos los paths relativos).
- **`build.py`** — genera el ejecutable/binario final del programa (script de empaquetado).
- **`launcher69.py`** — **entry point**. Al arrancar corre la migración pendiente (si hay DB vieja) y resume los meses cerrados. Después decide si:
  - levantar la interfaz, o
  - lanzar un programa puntual (`--launch "juego" [--platform "plataforma"]`) sin abrir la UI.

---

## Flujo típico (ejemplo: abrir el launcher y lanzar un juego)

1. `launcher69.py` arranca, migra la DB vieja si hace falta, resume los meses cerrados y, sin argumentos, levanta la UI.
2. Si 'cloudsync' esta habilitado se baja la informacion desde drive y se mergea.
    (dependiendo la cantidad de datos/velocidad de internet, es practicamente instantaneo)
3. `ui_handler.py` arma el `event_bus`.
4. `qt_interface.py` pinta la lista de plataformas/programas, pidiendo los datos a `helpers/data_manager.py`.
5. `data_manager.py` consulta `data_access/store.py`.
6. Usuario hace doble click en un juego → `helpers/games_launcher.py` entra en acción.
7. `games_launcher.py` delega en `platform_adapters/runners_handler.py` (que sabe cómo lanzar procesos según el SO).
8. Mientras corre, cada 60 s se guarda la duración de la sesión en `store.py` (solo local); al cerrar se marca como terminada y, si corresponde, `cloudsync.py` sube las sesiones a Drive.

---
