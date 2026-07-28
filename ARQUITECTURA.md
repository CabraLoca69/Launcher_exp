# Arquitectura — Launcher_exp

Este documento explica **cómo está organizado el proyecto y qué responsabilidad tiene cada módulo**. No entra en detalle de funciones internas (eso va en `FUNCIONES.md`); acá el objetivo es que en 2 minutos te ubiques en qué carpeta/archivo tocar cuando necesites cambiar algo.

## Vista general (capas)

El proyecto está organizado en capas, de abajo (datos crudos) hacia arriba (interfaz visible):

```
launcher69.py            ← entry point
        │
        ▼
interface_files/         ← UI (Tk y Qt en paralelo)
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

La idea de fondo: **las interfaces (Tk/Qt) no acceden directo a datos ni al SO**; pasan siempre por `helpers/`, que a su vez delega en `platform_adapters/` (si depende del SO) o en `data_access/` (si es persistencia).

---

## `/data`
Carpeta de contenido, no de código. Guarda todo lo que el programa lee/escribe en runtime.

| Subcarpeta | Contenido |
|---|---|
| `cloud_files/` | Credenciales/config necesarias para acceder a Google Drive |
| `databases/` | Bases de datos SQLite usadas por el programa |
| `icons/` | Iconos propios del launcher (UI) |
| `icons_cache/` | Iconos de ejecutables ya extraídos/cacheados (para no reprocesar) |
| `themes/` | Temas de la interfaz qt |

---

## `/data_access`
Todo lo que toca **persistencia**: base de datos local y sincronización en la nube.

- **`sqlitedb.py`** — la base de datos en sí (conexión, esquema, queries).
- **`datafiles.py`** — resuelve los *paths* para acceder a la información (dónde está cada archivo de datos).
- **`machine_id.py`** — genera/provee el ID único de la máquina, usado para no pisar datos entre dispositivos en el cloud sync.
- **`cloudsync.py`** — maneja todo lo relacionado a la sincronización con Google Drive (sube/baja el JSON, usa `machine_id` para diferenciar).

---

## `/helpers`
La capa de **lógica de negocio**: es el "backend" real del launcher, entre la UI y los datos/SO.

- **`data_manager.py`** — backend de manejo de datos (habla con `data_access/sqlitedb.py`).
- **`file_manager.py`** — backend de manejo de programas (escaneo de directorios, altas/bajas de ejecutables).
- **`games_launcher.py`** — backend del lanzamiento de juegos/programas.
- **`safe_threading`** — se encarga de lanzar hilos (para no bloquear la UI, ej. durante escaneos largos).
- **`icon_utils.py`** — convierte `.ico` → `.png`, genera iconos para la interfaz Tk.
- **`qicon_utils.py`** — equivalente a `icon_utils.py` pero para Qt.
- **`helpers.py`** — utilidades varias; hoy en día es específico de Tk (candidato a renombrar/mover si crece).

> 🔎 Nota mental: `icon_utils.py` y `qicon_utils.py` existen separados porque Tk y Qt manejan imágenes distinto. Si en algún momento unificás la UI a solo Qt, `icon_utils.py` quedaría obsoleto.

---

## `/interface_files`
Todo lo visual. **Hay dos interfaces en paralelo**: la vieja (Tk) y la nueva en desarrollo (Qt/PySide6).

- **`ui_handler.py`** — genera el `event_bus` y decide qué renderer de menú usar (Tk y Qt manejan menús distinto). Es el punto de entrada de esta capa.
- **`event_bus.py`** — los buses de eventos, uno por interfaz.
- **Qt:** `qt_interface.py`, `qt_menus_renderer.py`, `qt_popups.py`
- **Tk:** `tk_interface.py`, `tk_menus_renderer.py`, `tk_popups.py`

Cada trío (interfaz + menús + popups) es autocontenido para su framework. No se mezclan entre sí; `ui_handler.py` es el que decide cuál instanciar.

---

## `/platform_adapters`
Todo lo que **cambia de comportamiento según el sistema operativo**. Patrón strategy/factory: un "handler" central elige la implementación correcta.

- **`platform_handler.py`** — el factory/strategy: elige el comportamiento de todos los scripts de este directorio según el SO detectado.
- **`registry.py`** — actualmente duplica el rol de `platform_handler.py`; **está en proceso de eliminación** (quedó de un refactor, solo se le cambió el nombre). ⚠️ No agregar lógica nueva acá.
- **`executable_handler.py`** — maneja lo específico de ejecutables por SO.
- **`icons_handler.py`** — extracción/manejo de iconos según SO.
- **`menus_handler.py`** — opciones de menús según SO.
- **`paths_handler.py`** — normalización/resolución de paths según SO.
- **`runners_handler.py`** — lanza los programas (el "run" real del ejecutable).
- **`shortcuts_handler.py`** — creación de accesos directos.

---

## Raíz del proyecto

- **`base_path.py`** — provee el directorio raíz del proyecto (referencia para todos los paths relativos).
- **`build.py`** — genera el ejecutable/binario final del programa (script de empaquetado).
- **`launcher69.py`** — **entry point**. Decide si:
  - levantar la interfaz (Qt por defecto, Tk con `--tk`), o
  - lanzar un programa puntual (`--launch 'nombre_exe'`) sin abrir la UI.

---

## Flujo típico (ejemplo: abrir el launcher y lanzar un juego)

1. `launcher69.py` arranca, sin argumentos → decide levantar la UI en desarrollo.
2. Si 'cloudsync' esta habilitado se baja la informacion desde drive y se mergea.
    (dependiendo la cantidad de datos/velocidad de internet, es practicamente instantaneo)
3. `ui_handler.py` arma el `event_bus` y elige el renderer Qt.
4. `qt_interface.py` pinta la lista de plataformas/programas, pidiendo los datos a `helpers/data_manager.py`.
5. `data_manager.py` consulta `data_access/sqlitedb.py`.
6. Usuario hace doble click en un juego → `helpers/games_launcher.py` entra en acción.
7. `games_launcher.py` delega en `platform_adapters/runners_handler.py` (que sabe cómo lanzar procesos según el SO).
8. Al cerrar/trackear tiempo, se actualiza la db (`sqlitedb.py`) y, si corresponde, `cloudsync.py` sube el cambio a Drive.

---
