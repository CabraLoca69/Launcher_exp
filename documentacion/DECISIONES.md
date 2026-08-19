## Orden de inicialización: event_bus antes que GameLauncherController (GLC)

**Contexto:** GLC es singleton y guarda el event_bus en __init__. Si se crea 
antes de que exista la UI, queda con NullEventBus para siempre (no hay forma 
de reasignarlo después).
**Decisión:** el main() siempre inicializa el event_bus primero, GLC después. 
Ese orden en main() no es arbitrario, no reordenar.

---

## Watcher de `global.actual_running` para el caso --launch

**Contexto:** con --launch se lanza un juego en un proceso separado del que 
después abre la UI. Son procesos de Python distintos → el event_bus in-memory 
de uno no le puede avisar nada al otro.
**Decisión:** GLC escribe/borra la key global.actual_running en la db al 
lanzar/cerrar. La UI, al levantar, chequea esa key con un watcher y así se 
entera de sesiones que quedaron activas de un proceso anterior.
**Por qué no otra cosa:** no hay memoria compartida entre procesos separados; 
la db ya es el único canal que ambos procesos tocan igual, así que se reusa 
en vez de meter IPC de verdad (sockets, pipes) para un caso puntual.