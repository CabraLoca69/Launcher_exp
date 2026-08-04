
- El event_bus necesita crearse antes de llamar a GameLauncherController (GLC), caso contrario GLC se queda con NullEventBus
que no va a avisarle nada a nadie. El flujo del main es como es debido a esto.

- En caso de entrar por --launch, y despues abrir la interfaz son procesos diferentes por lo que el EventBus del GLC ya lanzado 
no puede comunicarse realmente con la UI, para ese caso se inicializa un watcher (si habia algo en la db, key global.actual_running)
que avisa a la ui cuando se cerro un juego. GLC se encarga de crear/eliminar esa key.


