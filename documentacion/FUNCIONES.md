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
- `main()` — parsea argumentos (`--tk`, `--launch`) y decide el flujo.
- `start_tk_ui()` — levanta la interfaz Tk.
- `start_qt_ui()` — levanta la interfaz Qt.
- `init(interface)` — inicialización común antes de levantar cualquier interfaz (event bus, etc.).

---

## `/data_access` — persistencia

**`sqlitedb.py :: SQLiteDatabase`** (motor de key-value tipo "dot path" sobre SQLite)
- `__init__(self, file_path)` — abre/crea la conexión a la db.
- `_setup(self)` — crea la tabla si no existe.
- `_resolve_path(self, keypath)` — convierte listas en clave tipo `"a.b.c"`.
- `_fetch_row(self, query, params)` — ejecuta una consulta a la db.
- `resolve_game(self, game_name)` — devuelve la plataforma y el path de un juego.
- `get(self, keypath, default)` — lee un valor por keypath.
- `set(self, keypath, value)` — escribe un valor.
- `delete(self, keypath)` — borra una clave puntual.
- `ensure(self, keypath, default)` — crea la clave con default si no existe (no pisa si ya está).
- `delete_prefix(self, prefix)` — borra todas las claves que empiecen con `"prefix."`.
- `rename_prefix(self, old_prefix, new_prefix)` — renombra todas las keys bajo un prefijo (usado al renombrar plataformas).
- `update(self, keypath, func)` — lee, aplica `func` y reescribe (read-modify-write atómico).
- `get_all(self)` — devuelve **todo** el contenido como diccionario anidado.
- `get_children(self, prefix)` — devuelve solo las claves hijas directas de un prefijo.

**`datafiles.py`** — sin funciones propias; solo resuelve constantes/paths (`ICONS`, `ICONS_CACHE_DIR`, `db` instanciado acá).

**`machine_id.py`**
- `get_machine_id()` — devuelve un id persistente de la máquina (se guarda una vez y se reusa; usado para no pisar datos entre dispositivos en el cloud sync).

**`cloudsync.py`** — todo lo de Google Drive:
- `has_internet_http(url, timeout)` — chequea conectividad real (no solo si "hay wifi").
- `login_and_sync(force_new_account)` — flujo de login OAuth + primer sync.
  - `_rollback()` — (interna) revierte el login si algo falla a mitad de camino.
- `get_drive_service()` — arma el cliente autenticado de la API de Drive.
- `save_email_to_db(creds)` — guarda el email de la cuenta logueada (para mostrarlo en la UI).
- `get_or_create_folder(service)` — busca (o crea) la carpeta del launcher dentro de Drive.
- `flatten_config(nested, prefix, exclude)` — aplana el dict anidado de la db a formato `"a.b.c": valor` (para exportar/subir).
- `rebuild_nested_config(flat)` — proceso inverso: de plano a anidado (al bajar de Drive).
- `write_full_config_to_db(nested_config)` — vuelca un config anidado completo a la db local.
- `read_full_config_from_db()` — lee toda la db local y la devuelve anidada.
- `upload_backup(service, folder_id, backup_data)` — sube el JSON a Drive.
- `download_backup(service, folder_id)` — baja el JSON de Drive.
- `build_cloud_payload_for_upload(existing_cloud_data)` — arma qué se debe subir (mezcla lo local con lo que ya había en la nube, respetando `machine_id`).
- `merge_backup_data(local_nested, cloud_data)` — mergea datos locales + nube sin pisar entre dispositivos.
- `download_and_merge_backup()` — orquesta: baja de Drive + mergea + guarda en local.
- `call_merge(callback)` — versión "threaded" de `download_and_merge_backup` (para no bloquear la UI al abrir el programa).
- `call_upload()` — versión "threaded" de subir cambios (se llama después de cada sesión de juego).
- `call_download()` — versión "threaded" de bajar manualmente (botón en configuración cloud).

> ⚠️ **Nota:** `flatten_config` / `rebuild_nested_config` / `merge_backup_data` / `build_cloud_payload_for_upload` son 4 funciones muy relacionadas entre sí (todo el pipeline de "aplanar → mergear → anidar"). alto riesgo de que una futura función "auxiliar" para cloud ya esté cubierta acá.

---

## `/helpers` — lógica de negocio

**`data_manager.py :: DataManager`**
- `__init__(self)`
- `reload_in_thread(self, ui, on_callback)` — recarga todos los datos en un hilo aparte y llama al callback al terminar (usado al abrir el launcher / al hacer cloud sync).
  - `worker()` — (interna) el hilo en sí.
- `collect_platform_data(self, platform_name)` — arma el dict de datos de una plataforma puntual (juegos, tiempos, favoritos) para mostrarlo en la UI.
- `toggle_favorite(self, platform_name, game_name, limit)` — marca/desmarca favorito, respetando un límite máximo.

**`db_qwatcher.py :: RunningGameWatcher`**
- `__init__(self)`
- `_check(self)` — revisa periodicamente (timer seteado en init) la key de la db que indica si un juego esta corriendo.

**`file_manager.py :: FileManager`**
- `__init__(self)`
- `add_folder(self, platform_name, folder)` — agrega un directorio a una plataforma y dispara el escaneo.
- `add_game(self, platform_name, exe_path)` — da de alta un ejecutable puntual (agregado manual, no por escaneo).
- `_set_game_path(self, platform_name, exe_name, exe_path)` — (interna) escritura cruda en la db del path del juego.
- `delete_game(self, platform_name, game_name)` — borra un juego (y su ícono cacheado).
- `delete_folder(self, platform_name, folder_path)` — quita un directorio de la plataforma (y sus juegos asociados a ese folder).
- `rename_platform(old_name, new_name)` — renombra una plataforma (usa `sqlitedb.rename_prefix` por debajo).
- `scan_for_games(self, platform_name)` — escanea los directorios de la plataforma buscando ejecutables nuevos.
- `sort_key(self, game_name, game_times)` — función de orden usada para ordenar la lista de juegos (por tiempo jugado, alfabético, etc.).
- `remove_game_icon(self, game_path)` — borra el ícono cacheado de un juego (limpieza al eliminarlo).

**`games_launcher.py :: GameLauncherController`** (singleton)
- `__new__(cls, *args, **kwargs)` — implementa el singleton; primera vez limpia sesiones huérfanas.
- `__init__(self)`
- `launch_game(self, game_name)` — método principal: resuelve el juego, lo lanza vía `platform_adapters/runners_handler`, y arranca el guardado periódico + finalización.
  - `execute()` — (interna) el cuerpo real que corre en el hilo (lanza el proceso, espera a que cierre).
  - `periodic_saver()` — (interna) cada 60s llama a `_save_playtime` y sube a la nube si corresponde.
- `_save_playtime(self, platform_name, game_name, start_time, last_update_time, now)` — guarda tiempo **parcial** mientras el juego sigue corriendo (se llama cada 60s desde `periodic_saver`).
- `_finalize_playtime(self, platform_name, game_name, start_time, last_update_time, now)` — guarda el tiempo **final** cuando el juego se cierra, limpia sesión activa y notifica al event bus.
- `register_ui(self, platform, ui_instance)` — delega en el event bus.

**`games_launcher.py :: SessionsCleaner`**
- `clean_orphaned_sessions(self)` — al iniciar el programa, borra sesiones "activas" en la db que en realidad ya no tienen proceso vivo (ej. si cerraste el launcher a la fuerza).
- `is_process_running(self, pid)` — chequea si un PID sigue vivo (y no es zombie).

> ⚠️ **Nota (candidato a refactor, no duplicado real):** `_save_playtime` y `_finalize_playtime` tienen ~80% del cuerpo idéntico (actualizar total por PC + actualizar lista de sessions). La única diferencia real es que `_finalize` además limpia la sesión y notifica el event bus.

**`helpers.py`**
- `safe_askdirectory()` — wrapper de diálogo "elegir carpeta" (Tk) con algún fix/guarda extra (candidato a `tk_helpers.py`, ver deuda técnica).

**`icon_utils.py`** (Tk)
- `load_icon(path, size)` — carga un ícono como `ImageTk.PhotoImage` (con fix de `.ico`→`.png` en Linux).
- `ico_to_png(ico_path, output_dir, size)` — convierte `.ico` a `.png` y cachea el resultado en disco.

**`qicon_utils.py`** (Qt)
- `load_qicon(path, size)` — equivalente Qt de `load_icon` (devuelve `QIcon`), **reusa** `ico_to_png` de `icon_utils.py`.

> 🔎 Ya documentado en `ARQUITECTURA.md`: existen separados por Tk vs Qt. `ico_to_png` es la única función realmente compartida entre ambos. No hace falta una tercera versión "genérica" a menos que unifiques la UI.

**`safe_threading.py`**
- `safe_thread(target)` — arranca un hilo con manejo de excepciones (para que un error en un hilo no tire todo el programa).
  - `wrapper()` — (interna) la función que efectivamente corre en el `Thread`.

---

## `/platform_adapters` — comportamiento según SO

Patrón repetido en casi todos estos archivos: una clase base/interfaz + una implementación Windows + una (o más) Linux, elegidas por `platform_handler.py`. **Esto es intencional, no está duplicado** — cada método `run`/`get_options`/`goto_folder`/etc. son la *misma función lógica* implementada distinto según el SO.

**`platform_handler.py`**
- `_detect_os()` — devuelve el SO actual.
- `PlatformHandler.get(self, key)` — factory: dado `"runner"`, `"icons"`, `"menus"`, etc. devuelve la implementación correcta según el SO.

**`registry.py`** — vacío actualmente (en proceso de eliminación, ver deuda técnica en `ARQUITECTURA.md`). ⚠️ No agregar nada acá.

**`executables_handler.py`**
- `ExecutableDetector.is_executable(self, path)` — interfaz.
- `WindowsExecutableDetector.is_executable(self, path)` — chequea extensión `.exe`.
- `UnixExecutableDetector.is_executable(self, path)` — chequea permisos de ejecución + tipo de archivo.

**`icons_handler.py`**
- `_fallback_icon(size)` — ícono genérico cuando no se puede extraer uno real.
- `IconProvider.set_window_icon(self, window, icon_name)` / `.get_icon(self, path, size)` — interfaz.
- `WindowsIconProvider` — implementa ambos + `resource_path(rel_path)` (interna, resuelve paths de recursos empaquetados).
- `LinuxIconProvider` — implementa ambos +:
  - `get_linux_icon(self, path, size)` — extracción de ícono nativo Linux.
  - `is_wine_executable(self, path)` — detecta si el ejecutable corre bajo Wine.
  - `get_wine_icon(self, path, size)` — extrae ícono de un `.exe` corrido con Wine.

**`menus_handler.py`**
- `MenuOptions.get_options(self, game_name, btn_props, frame)` — interfaz.
- `BaseMenuOptions` — implementación común:
  - `_play_option(self, btn_props, frame)` — (interna) opción "jugar".
  - `_common_options(self, game_name, frame)` — (interna) opciones compartidas entre SOs.
- `WindowsMenuOptions.get_options(...)` / `LinuxMenuOptions.get_options(...)` — arman el menú final combinando lo común + lo específico del SO.

**`paths_handler.py`**
- `PathWalker.goto_folder(self, path)` — interfaz ("abrir explorador en esta carpeta").
- `WindowsGoToFolder.goto_folder(self, path)` / `LinuxGoToFolder.goto_folder(self, path)` — implementaciones.

**`runners_handler.py`**
- `GameRunner.run(self, game_path)` — interfaz.
- `WindowsRunner.run(...)` — lanza el `.exe` directo en Windows.
- `LinuxNativeRunner.run(...)` — lanza un binario nativo de Linux.
- `LinuxWineRunner`:
  - `__init__(self, wineprefix)`
  - `run(self, game_path)` — lanza vía Wine.
  - `find_real_wine_process(self, parent_pid, expected_exe)` — Wine crea procesos intermedios; esto busca el proceso "real" del juego.
  - `_cmdline_matches(self, proc, expected_exe)` — (interna) matchea el cmdline del proceso contra el ejecutable esperado.
- `LinuxSelector.run(self, game_path)` — decide en runtime si usar `LinuxNativeRunner` o `LinuxWineRunner` según el tipo de archivo.

**`shortcuts_handler.py`**
- `ShortcutCreator.create_direct_access(...)` / `.create_start_menu_shortcut(...)` — interfaz.
- `WindowsShortcutCreator` / `LinuxShortcutCreator` — implementaciones, ambas con:
  - `create_direct_access(self, game_name, game_path, destino_desktop)`
  - `create_start_menu_shortcut(self, game_name, game_path, icon_path)`
- `LinuxShortcutCreator` además:
  - `get_desktop_dir(self)` — resuelve la carpeta Desktop real (puede variar por locale/config).
  - `_resolve_icon(self, game_name, game_path)` — (interna) resuelve qué ícono usar para el acceso directo.

---

## `/interface_files` — UI

### Compartido

**`ui_handler.py`**
- `init_event_bus(interface)` — crea el event bus correspondiente (Tk/Qt/Null) según la interfaz activa.
- `get_event_bus()` — devuelve la instancia actual del event bus.
- `_require_interface()` — (interna) valida que se haya inicializado antes de usar.
- `get_menu_renderer()` — devuelve el renderer de menús (Tk o Qt) correspondiente.

**`event_bus.py`**
- `GameEventBus` — interfaz: `register_ui(self, platform, ui_instance)`, `notify_game_closed(self, platform_name, game_name)`.
- `TkEventBus` — implementa ambos + `_watcher(self)` (interna, hilo que vigila procesos para Tk).
- `QtEventBus` — implementa ambos + `_check_pending(self, platform_name)`, `_check_running(self, platform_name, ui_instance)`, `_on_game_closed(self, platform_name, game_name)` (todas internas, manejo de señales Qt).
- `NullEventBus` — implementación vacía (usada cuando no hay UI activa, ej. `--launch`).

### Qt (`qt_interface.py`, `qt_menus_renderer.py`, `qt_popups.py`)

- **`FavoritesPanel`**: `__init__`, `refresh(self)` (repobla lista de favoritos), `_build_row(self, game_name, path)`, `_launch(self, game_name)`.
- **`GameDetailPanel`**: `__init__`, `show_game(self, game_name, icon)`, `_populate_sessions(self, sessions)`, `_build_session_row(self, index, session)`, `_launch_game(self)`, `_open_notes(self)`, `_toggle_favorites(self)`, `_show_props_menu(self)`, `mousePressEvent(self, event)`.
- **`ClearableTreeWidget`** — sin métodos propios listados (override menor de Qt).
- **`PlatformTab`**: `__init__`, `_build_sidebar(self)`, `_on_game_clicked/_on_game_double_clicked/_on_game_right_click`, `fill_games(self, games)`, `_add_game_item(self, game)`, `_delete_selected_item(self)`, `_filter_games(self, text)`, `launch_game(self, game_name)`, `confirm_remove(self)` + `_on_confirm(self, value)`, `add_exe(self)`, `change_game_directory(self, game_name)`, `gotofolder(self, game_name)`, `create_direct_access(self, game_name)`, `create_start_menu_shortcut(self, game_name)`.
- `ask_platform_folder(window)` — helper suelto para el diálogo de elegir carpeta al agregar plataforma.
- **`CloudSettingsWindow`**: `__init__`, `_build_ui(self)`, `_toggle_clouding(self, checked)`, `_change_account(self)`, `_confirm(self, title, message, callback)`, `_recall_token(self, respond)` (+ `worker()` interna), `_on_login_finished(self, ok)`, `_get_account_info(self)`.
- **`MainWindow`**: `__init__`, `_start_reload(self, callback)`, `_on_reload_finished(self, all_data)`, `_add_platform_tab(self, data)`, `_build_header(self)`, `update_title_label(self)`, `add_platform(self)`, `_open_cloud_settings(self)`, `_on_tab_close_requested(self, index)`, `_remove_tab(self, index, platform_name, confirmed)`, `_on_tab_context_menu(self, pos)`.
- **`ReloadWorker`**: `run(self)` + helper suelto `reload_with_thread(ui, on_callback)`.
- **`QtLauncherUI`**: `launch_ui()` — entry point de esta interfaz.
- `qt_menus_renderer.py :: QtMenuRenderer.build(self, menu, options)` — arma un `QMenu` a partir de opciones genéricas.
- `qt_popups.py`: `BasePopup` (show/hide/close/keyPress/eventFilter/`_respond`), `CustomPopupMenu` (`add_button`, `show_at`, + `_on_click()` interna), `InputDialog` (`_respond_input`), `ConfirmDialog` (sin métodos extra propios listados).

### Tk (`tk_interface.py`, `tk_menus_renderer.py`, `tk_popups.py`)

- **`SplashFrame`**: `__init__`, `close(self)`.
- **`TkLauncherUI`**: `__init__`, `init_ui(self)`, `set(self)`, `start(self, all_data)`, `add_session(...)`, `monitor_sessions(self)` (+ `loop()` interna), `restore_sessions(self)`.
- **`SessionManager`**: `__init__`, `add_session(...)`, `update_session(self, pid, game_name)`, `monitor_process(self, pid)`, `force_close(self, pid)`, `show(self)`, `hide(self)`.
- **`MainLauncherFrame`**: `__init__`, `open_cloud_settings(self)`, `ask_platform_name(self)`, `update_title_label(self)`.
- **`DraggableNotebook`**: `__init__`, `on_button_press/release`, `on_mouse_move`, `on_right_click`, `save_tab_order(self)`, `on_tab_change(self, event)`, `ask_platform_name(self)`, `input_callback_handler(self, value)`, `emptyframe(self)`, `new_platform(self, platform_name)`, `call_populate(self, platform_name)`, `confirm_remove(self)` + `remove_tab(self, confirmed)`, `show_menu(...)`, `open_properties(self, platform_name)`, `open_cloud_settings(self)` (+ helpers sueltos `refresh_tree()`, `update_tab(new_name, pre_name)`).
- **`GamePlatformFrame`**: `__init__`, click/dobleclick/right-click de juegos, `on_delete_key`, `on_selection_change` (activa/desactiva bind de Supr), `create_direct_access`, `create_start_menu_shortcut`, `launch_game`, `add_exe`, `confirm_remove` + `remove_exe(self, confirmed)`, `update_on_close`, `find_item_id_for_game`, `filter_games`, `gotofolder`, `change_game_directory`, `toggle_favorite`, `show_favorites`, `show_game_details`, `open_notes_window`, `ask_steam_id` (+ helpers sueltos `save_steam_id`, `input_callback_handler`, `ask_input`), `show_menu`, `clean_info`.
- **`GameDetailsPanel`**: `__init__`, `show_game_details`, `update_sessions_block`, `start/stop_session_watcher` + `_session_watcher_loop` (interna), `show_favorites`, `clean_info`, `format_playtime(minutes)` (estática/util), `launch_game`, `toggle_favorite`, `open_notes`, `show_props_menu`.
- **`NotesWindow`**: `__init__`, `save_and_close`, `periodic_save`, `save_note`.
- **`PropertiesWindow`**: `__init__`, `build_ui`, path click/dobleclick/right-click (+ `close_menu` interna), `menu_closed`, `toggle_multiple_games`, `btn_new_path`, `gotofolder`, `confirm_remove` + `remove_folder(self, confirmed)`, `update_directory_list`, `update_game_list`, `update_tab_name`.
- **`CloudSettingsWindow`** (versión Tk): `__init__`, `build_ui`, `get_account_info`, `toggle_clouding`, `change_account`, `recall_token` (+ `worker()` interna), + helpers sueltos `call(all_data)`, `fill_tree(tree, grouped)`, `restore_selection()`.
- `tk_menus_renderer.py :: TkMenuRenderer.build(self, menu, options)` — equivalente Tk de `QtMenuRenderer.build`.
- `tk_popups.py`: `AutoCloseFrame` (bind_escape, bind_click_outside, check_click_outside, should_close, after_close, on_close, `_is_child_of`), `CustomPopupMenu` (add_button, show, after_close), `InputDialog` (`_respond`, after_close), `ConfirmDialog` (after_close, `_respond`).

> 🔎 **Importante:** casi todo `qt_interface.py` tiene su espejo en `tk_interface.py` (`gotofolder`, `create_direct_access`, `launch_game`, `toggle_favorite`, `confirm_remove`, `add_exe`, `change_game_directory`, `filter_games`/`_filter_games`, `show_favorites`, `CloudSettingsWindow`...). **Esto es esperado** (dos interfaces en paralelo, como dice `ARQUITECTURA.md`)  
---


