## Orden de inicialización: event_bus antes que GameLauncherController (GLC)

**Contexto:** GLC es singleton y guarda el event_bus en __init__. Si se crea 
antes de que exista la UI, queda con NullEventBus para siempre (no hay forma 
de reasignarlo después).
**Decisión:** el main() siempre inicializa el event_bus primero, GLC después. 
Ese orden en main() no es arbitrario, no reordenar.

---

## Watcher de sesiones abiertas para el caso --launch

**Contexto:** con --launch se lanza un juego en un proceso separado del que 
después abre la UI. Son procesos de Python distintos → el event_bus in-memory 
de uno no le puede avisar nada al otro.
**Decisión:** un juego corriendo es una fila de `sessions` con `ended_at` NULL 
y `pid` cargado. La UI, al levantar, consulta `store.open_sessions()` y vigila 
cada una con `RunningGameWatcher` hasta que se cierre.
**Por qué no otra cosa:** no hay memoria compartida entre procesos separados; 
la db ya es el único canal que ambos procesos tocan igual, así que se reusa 
en vez de meter IPC de verdad (sockets, pipes) para un caso puntual.

---

## Tablas reales en vez de claves con puntos

**Contexto:** la DB era un clave-valor con claves `plataforma.seccion.nombre`, 
herencia de la migración desde un `.json`. Nombres con `.`, `_` o `%` rompían 
búsquedas, y renombrar una plataforma implicaba reescribir todas sus claves.
**Decisión:** tablas `platforms`, `platform_folders`, `games`, `sessions` y 
`settings` (`data_access/store.py`). Los nombres son valores, no partes de una 
clave. Todo el SQL vive en `store.py`.
**Migración:** `migrate_kv.py` corre una vez al arrancar y no toca los archivos 
viejos. La última versión con la DB vieja (y la UI Tk) es el tag 
`ultima-version-tk`.

---

## Sesiones como unidad de sync, con resumen mensual

**Contexto:** antes se sincronizaban totales por PC y se mezclaban con `max()`; 
solo se guardaban las últimas 5 partidas.
**Decisión:** se guarda cada partida (`kind='session'`) con un uuid y el id de 
la PC. Sincronizar es unir por uuid: repetirlo no duplica horas. Las partidas de 
meses cerrados se resumen en una fila por juego, PC y mes (`kind='month'`, id 
uuid5 determinista). Cada PC resume solo las suyas. El resumen guarda en 
`covers` los ids exactos que reemplaza: al importarlo se borran esos y ningún 
otro (una partida que cerró después de compactar no se pierde) y esos ids no 
vuelven a entrar.
**Migración:** cada PC vieja tenía un total por PC. Ese total se guarda entero 
como fila `legacy` (mismo id en todas las PCs, el merge las unifica). Las 
últimas 5 partidas se importan como `history`: se ven pero no suman, porque ya 
están dentro del total.
**Por qué no otra cosa:** con totales, borrar o corregir una partida es 
imposible y el merge depende de que los totales solo crezcan.

---

## Borrar = ocultar

**Contexto:** borrar un juego no lo borra de la nube; si se borraba local, al 
volver a sincronizar o agregarlo se perdía su historial.
**Decisión:** quitar un juego pone `games.hidden = 1`; cerrar una plataforma 
pone `position = NULL` y oculta sus juegos. Las sesiones se conservan. Volver a 
agregarlos (o reescanear) los muestra con su historial.

