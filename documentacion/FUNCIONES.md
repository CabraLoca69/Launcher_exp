# Funciones — Launcher_exp

Convención: `archivo.py :: Clase.metodo(args)` — descripción corta. Los métodos "privados" (`_algo`) están marcados igual, sin distinción especial salvo que importe.

---

## Raíz del proyecto

**`base_path.py`**
- `get_portable_base_dir()` — calcula el directorio raíz del proyecto (para armar paths relativos, sirve tanto corriendo como .py o como .exe empaquetado).

**`build.py`**
- `run(cmd)` — ejecuta un comando de shell (wrapper para el proceso de build).
- `clean()` — borra carpetas de builds anteriores (`build/`, `dist/`, etc.) antes de generar una nueva.
- `main()` — orquesta el proceso de empaquetado (clean → build).

**`launcher69.py`** (entry point)
- `parse_args(argv)` — parsea `--launch` y `--platform` (ignora argumentos desconocidos, ej. de Qt).
- `main(argv)` — corre la migración pendiente, resume meses cerrados y decide: lanzar un juego o levantar la UI.
- `start_qt_ui()` — inicializa el event bus Qt antes que el controller (ver `DECISIONES.md`) y levanta la interfaz.

---

## `/data_access` — persistencia

**`store.py :: Store`** — único lugar con SQL. Esquema y reglas de sesiones en el docstring del archivo.
- `transaction()` — context manager "todo o nada" (`BEGIN IMMEDIATE`); anidado se suma a la externa. Todas las escrituras pasan por acá.
- `summary_id(kind, machine_id, platform, game, period)` — (suelta) uuid5 determinista para filas resumen (`month`/`legacy`).
- `Game` / `Session` — dataclasses que devuelven las consultas.
- Settings: `get_setting(key, default)`, `set_setting(key, value)`.
- Plataformas: `list_platforms()` (visibles, en orden de pestañas), `add_platform(name)` (crea o vuelve a mostrar), `rename_platform(old, new)`, `reorder_platforms(names)`, `hide_platform(name)`, `list_folders(platform)`, `add_folder(platform, path)`, `remove_folder(platform, path)`.
- Juegos: `list_games(platform)` (visibles, por último jugado y nombre), `get_game(platform, name)`, `find_game(name)` (primera coincidencia visible, para `--launch` sin plataforma), `add_game(platform, name, path)`, `upsert_game(platform, name, path, revive)` (escaneo), `hide_game`, `set_game_path`, `set_favorite`, `set_steam_appid`, `set_notes`, `list_favorites(platform)`, `has_running_games(platform)`. `upsert_game` reutiliza un juego con la misma ruta aunque tenga otro nombre, y no vuelve a mostrar un juego oculto salvo con `revive=True`.
- Sesiones: `start_session(game_id, machine_id, pid)`, `update_session(session_id, duration_s)`, `end_session(session_id, duration_s)`, `open_sessions()` (juegos corriendo en esta PC), `open_session_for(platform, game)`, `close_orphan_sessions(is_alive)` (`is_alive` recibe la `Session`), `recent_sessions(platform, game, limit)`, `total_seconds(platform, game)`.
- `compact_months(machine_id, today)` — resume en una fila por mes las partidas terminadas de meses cerrados (solo las de esta PC), anotando en `covers` qué ids reemplaza.
- Cloud: `export_sessions()` (todas, identificadas por nombre) e `import_sessions(sessions)` (todo o nada, idempotente por uuid; un resumen borra exactamente las partidas de su `covers`).

**`migrate_kv.py`** — migración única desde la DB clave-valor vieja.
- `migrate(config_file, notes_file, store, machine_id)` — copia plataformas, carpetas, juegos, favoritos, Steam IDs, notas, settings y horas (totales por PC → filas `legacy` con el total completo; últimas 5 partidas → `history`, que no suman). Todo en una transacción.
- `legacy_row(pc, platform, game, minutes)` — fila legacy con id determinista (la reusa `cloudsync` para el formato viejo).
- `run_pending_migration()` — la ejecuta una sola vez (marca `kv_migrated` en settings); si falla, loguea y reintenta en el próximo arranque.

**`datafiles.py`** — sin funciones propias; paths (`ICONS`, `ICONS_CACHE_DIR`, `DB_FILE`, ...) y la instancia `store`.

**`machine_id.py`**
- `get_machine_id()` — devuelve un id persistente de la máquina (se guarda en cada sesión). Lo cachea: si el archivo falla, usa uno temporal pero estable durante la ejecución.

**`cloudsync.py`** — todo lo de Google Drive:
- `login_and_sync(force_new_account)` — login OAuth interactivo + primer merge, todo en el hilo que la llama. Si el login falla, restaura el token anterior.
- `get_drive_service(interactive)` — arma el cliente autenticado de la API de Drive. Solo con `interactive=True` abre el navegador y guarda el email; en segundo plano, sin credenciales válidas, tira una excepción.
- `save_email_to_db(creds)` — guarda el email de la cuenta logueada (para mostrarlo en la UI); sin email, el login se considera incompleto.
- `get_or_create_folder(service)` — busca (o crea) la carpeta del launcher dentro de Drive.
- `upload_backup(service, folder_id, backup_data)` / `download_backup(service, folder_id)` — suben/bajan el JSON. Un backup ilegible tira `ValueError` (no se trata como vacío, así no se pisa).
- `build_payload(sessions)` — arma el JSON (formato v2: lista de sesiones).
- `sessions_from_payload(cloud)` — extrae sesiones de un backup v2 o del formato viejo (sin `version`); una versión desconocida tira `ValueError`.
- `sessions_from_v1(cloud)` — formato viejo (`pc_ids`) → filas `legacy`, con los mismos ids que la migración.
- `sync_once(upload)` — baja y mezcla en la DB local; con `upload`, sube el resultado. Un lock deja una sola operación con Drive a la vez.
- `call_merge(callback)` — `sync_once(upload=False)` en un hilo (al abrir la UI). La subida al cerrar un juego llama a `sync_once(upload=True)` directo desde el hilo de la partida.

---

## `/helpers` — lógica de negocio

**`data_manager.py :: DataManager`**
- `collect_platform_data(self, platform_name)` — juegos visibles de una plataforma con su ícono, para la UI.
- `toggle_favorite(self, platform_name, game_name, limit)` — marca/desmarca favorito, respetando un límite máximo.

**`db_qwatcher.py :: RunningGameWatcher`**
- `_check(self)` — revisa periódicamente si la sesión del juego sigue abierta; al cerrarse emite `game_closed_detected`.

**`file_manager.py :: FileManager`**
- `add_platform(self, platform_name, folder)` — crea (o vuelve a mostrar) la plataforma y escanea su carpeta.
- `add_folder(self, platform_name, folder)` — agrega un directorio y lo escanea; muestra sus juegos aunque estuvieran ocultos.
- `add_game(self, platform_name, exe_path)` — alta manual de un ejecutable.
- `delete_game(self, platform_name, game_name)` — oculta el juego (conserva horas) y borra su ícono cacheado.
- `delete_folder(self, platform_name, folder_path)` — quita un directorio y oculta sus juegos.
- `delete_platform(self, platform_name)` — oculta la plataforma y sus juegos.
- `rename_platform(self, old_name, new_name)` — renombra (falla si ya existe el nombre nuevo).
- `scan_for_games(self, platform_name)` — escanea los directorios y agrega juegos nuevos; los que el usuario borró siguen ocultos.
- `remove_game_icon(self, game_path)` — borra el ícono cacheado de un juego (nombrado con `icon_cache_name`).

**`games_launcher.py`**
- `is_session_alive(session)` — (suelta) chequea si el proceso de una sesión sigue vivo, no es zombie y no es un PID reusado (arrancó antes que la sesión).
- `GameLauncherController` (singleton):
  - `__new__` — la primera vez cierra sesiones huérfanas (`store.close_orphan_sessions`).
  - `launch_game(self, game_name, platform_name)` — resuelve el juego y lanza la partida en un hilo (si no está corriendo ya).
  - `_resolve(self, game_name, platform_name)` — busca el juego (en una plataforma o en todas).
  - `_run_session(self, game)` — lanza el proceso, abre la sesión, guarda la duración cada 60 s en la DB (`heartbeat()` interna), la cierra al terminar y recién ahí sube a la nube, en ese mismo hilo (con `--launch` un hilo daemon moriría al salir).
  - `register_ui(self, platform, ui_instance)` — delega en el event bus.
  - `force_close_game(self, platform_name, game_name)` — termina el proceso de una sesión en curso.

**`icon_utils.py`**
- `icon_cache_name(game_path)` — nombre del ícono cacheado: hash de la ruta completa, así no chocan dos `Game.exe`.
- `ico_to_png(ico_path, output_dir, size)` — convierte `.ico` a `.png` y cachea el resultado en disco.

**`qicon_utils.py`**
- `load_qicon(path, size)` — carga un ícono como `QIcon` (reusa `ico_to_png` en Linux).

**`safe_threading.py`**
- `safe_thread(target)` — arranca un hilo con manejo de excepciones (para que un error en un hilo no tire todo el programa).
  - `wrapper()` — (interna) la función que efectivamente corre en el `Thread`.

---

## `/platform_adapters` — comportamiento según SO

Patrón repetido en casi todos estos archivos: una clase base/interfaz + una implementación Windows + una (o más) Linux, elegidas por `platform_handler.py`. **Esto es intencional, no está duplicado** — cada método `run`/`get_options`/`goto_folder`/etc. son la *misma función lógica* implementada distinto según el SO.

**`platform_handler.py`**
- `_detect_os()` — devuelve el SO actual.
- `PlatformHandler.get(self, key)` — factory: dado `"runner"`, `"icons"`, `"menus"`, etc. devuelve la implementación correcta según el SO.

**`executables_handler.py`**
- `ExecutableDetector.is_executable(self, path)` / `.game_name(self, path)` — interfaz.
- `WindowsExecutableDetector` — ejecutable = extensión `.exe`/`.bat`/`.cmd`; el nombre quita siempre la extensión.
- `UnixExecutableDetector` — ejecutable = permiso de ejecución; el nombre quita solo extensiones conocidas (`_UNIX_EXECUTABLE_SUFFIXES`).

**`icons_handler.py`**
- `_fallback_icon(size)` — ícono genérico cuando no se puede extraer uno real.
- `IconProvider.get_icon(self, path, size)` — interfaz.
- `WindowsIconProvider` — extrae el ícono del `.exe`.
- `LinuxIconProvider` — implementa `get_icon` +:
  - `get_linux_icon(self, path, size)` — extracción de ícono nativo Linux.
  - `is_wine_executable(self, path)` — detecta si el ejecutable corre bajo Wine.
  - `get_wine_icon(self, path, size)` — extrae ícono de un `.exe` corrido con Wine.

**`menus_handler.py`**
- `MenuOptions.get_options(self, game_name, btn_props, frame)` — interfaz.
- `BaseMenuOptions` — implementación común:
  - `_play_option(self, game_name, btn_props, frame)` — (interna) opción "jugar".
  - `_common_options(self, game_name, frame)` — (interna) opciones compartidas entre SOs.
- `WindowsMenuOptions.get_options(...)` / `LinuxMenuOptions.get_options(...)` — arman el menú final combinando lo común + lo específico del SO.

**`paths_handler.py`**
- `PathWalker.goto_folder(self, path)` — interfaz ("abrir explorador en esta carpeta").
- `WindowsGoToFolder.goto_folder(self, path)` / `LinuxGoToFolder.goto_folder(self, path)` — implementaciones.

**`runners_handler.py`**
- `GameRunner.run(self, game_path, steam_appid)` — interfaz.
- `WindowsRunner.run(...)` — lanza el `.exe` directo en Windows.
- `LinuxNativeRunner.run(...)` — lanza un binario nativo de Linux.
- `LinuxWineRunner`:
  - `__init__(self, wineprefix)`
  - `run(self, game_path, steam_appid)` — lanza vía Steam (si hay Steam ID) o Wine.
  - `find_real_wine_process(self, parent_pid, expected_exe)` — Wine crea procesos intermedios; esto busca el proceso "real" del juego.
  - `_cmdline_matches(self, proc, expected_exe)` — (interna) matchea el cmdline del proceso contra el ejecutable esperado.
- `LinuxSelector.run(self, game_path, steam_appid)` — decide en runtime si usar `LinuxNativeRunner` o `LinuxWineRunner` según el tipo de archivo.

**`shortcuts_handler.py`**
- `launcher_target()` — (suelta) programa del acceso directo: el ejecutable congelado, o Python + `launcher69.py` desde el código.
- `launch_args(platform_name, game_name)` — (suelta) argumentos `--launch ... --platform ...` que usan todos los accesos directos.
- `ShortcutCreator.create_direct_access(...)` / `.create_start_menu_shortcut(...)` — interfaz.
- `WindowsShortcutCreator` / `LinuxShortcutCreator` — implementaciones, ambas con:
  - `create_direct_access(self, platform_name, game_name, game_path, destino_desktop)`
  - `create_start_menu_shortcut(self, platform_name, game_name, game_path, icon_path)`
- `LinuxShortcutCreator` además:
  - `get_desktop_dir(self)` — resuelve la carpeta Desktop real (puede variar por locale/config).
  - `_resolve_icon(self, game_name, game_path)` — (interna) resuelve qué ícono usar para el acceso directo.

---

## `/interface_files` — UI

**`ui_handler.py`**
- `init_event_bus(interface)` — crea el event bus (`"Qt"` o `"None"` para `--launch`).
- `get_event_bus()` — devuelve la instancia actual (si no hay, crea la vacía).

**`event_bus.py`**
- `QtEventBus` — `register_ui`, `notify_game_started`, `notify_game_closed` con señales Qt, y además:
  - `watch_external(self)` — busca juegos lanzados desde otro proceso (accesos directos); la UI la llama con un timer.
  - `_watch_running(self, platform_name, ui_instance)` — vigila los juegos que corren y la UI no conocía.
  - `_on_game_closed(self, platform_name, game_name)` — avisa a la pestaña de la plataforma y suelta el watcher de ese juego.
- `NullEventBus` — mismos métodos, vacíos (usada con `--launch`).

**`qt_interface.py`**
- **`SessionsBar`** — barra inferior con los juegos corriendo y su tiempo.
- **`FavoritesPanel`**: `refresh(self)`, `_build_row(self, game_name, path)`, `_launch(self, game_name)`.
- **`GameDetailPanel`**: `show_game(self, game_name, icon)`, `_refresh_if_running(self)` (timer: refresca horas y sesiones mientras el juego corre), `_populate_sessions(self, sessions)`, `_build_session_row(self, index, session)`, `_launch_game(self)`, `_open_notes(self)`, `_toggle_favorites(self)`, `_show_props_menu(self)`.
- **`ClearableTreeWidget`** — árbol que se deselecciona al hacer click en vacío.
- **`PlatformTab`**: `_build_sidebar`, `_on_game_clicked/_on_game_double_clicked/_on_game_right_click`, `show_game_menu`, `update_on_close` (reordena la lista y refresca favoritos), `refresh_games`, `_show_panel` (favoritos/detalle con fundido), `_launch_selected` (Enter), `_confirm_remove_selected` (Supr), `toggle_favorite`, `fill_games`, `_add_game_item`, `_delete_selected_item`, `_filter_games`, `_find_item_by_name`, `launch_game`, `confirm_remove` + `_on_confirm`, `add_exe`, `change_game_directory`, `ask_steam_id`, `_game_path`, `gotofolder`, `create_direct_access`, `create_start_menu_shortcut`.
- `fade_in(widget)` — fundido al mostrar un panel (`FADE_MS`). `apply_theme(theme_id)` — aplica un tema a toda la app.
- **`SettingsWindow`** (Configuración: cloud, "varios juegos a la vez" y tema; se cierra con click afuera): `_change_theme`, `_build_ui`, `_toggle_clouding`, `_change_account`, `_confirm`, `_recall_token` (+ `worker()` interna), `_on_login_finished`, `_get_account_info`.
- **`MainWindow`**: `_start_reload`, `_on_reload_finished` (restaura la última pestaña), `_remember_tab`, `_refresh_all_tabs` (tras el merge de la nube al abrir), `_add_platform_tab`, `_build_header`, `update_title_label`, `add_platform`, `_open_settings`, `_on_tab_close_requested`, `_remove_tab`, `_on_tab_context_menu`, `_save_tab_order`, `_replace_tab`, `_open_properties`, `_reload_tab`.
- **`PlatformPropertiesDialog`**: directorios (`_add_folder`, `_remove_folder`, `_open_folder`) y `_rename`; `changed` indica si hay que reconstruir la pestaña.
- `_exe_filter()` — filtro del diálogo de ejecutables (en Linux, "Todos los archivos" primero).
- `ask_platform_folder(window)` — diálogo de nombre + carpeta al agregar plataforma.
- `_session_label(session)` — texto de una fila del historial (partida, resumen mensual o legacy).
- **`NotesDialog`**: `ask(parent, game_name, notes)` — editor de notas; devuelve el texto al cerrar (se guarda siempre).
- **`ReloadWorker`**: `run(self)` + helper suelto `reload_with_thread(ui, on_callback)`.
- **`QtLauncherUI`**: `launch_ui()` — entry point de esta interfaz.

**`qt_menus_renderer.py`** — `QtMenuRenderer.build(self, menu, options)`: arma el menú a partir de opciones genéricas.

**`themes.py`** — `list_themes(themes_dir)` (temas válidos), `load_theme(path)` (valida colores `#RRGGBB`), `render(template, colors)` (`@color` y `@color/NN`), `stylesheet(theme_id)` (con fallback a `DEFAULT_THEME`).

**`qt_popups.py`** — `CloseOnClickOutside` (mixin: diálogo que se cierra con click afuera, salvo que haya otro modal o menú encima), `BasePopup` (cierre con Escape / click afuera, `_respond`), `CustomPopupMenu` (`add_button`, `show_at`), `InputDialog` (`_respond_input`), `ConfirmDialog`.

---
