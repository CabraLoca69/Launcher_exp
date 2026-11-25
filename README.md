# Launcher_exp

Launcher personal para trackear tiempo de juego (o de uso) de cualquier `.exe`/binario, sin depender de plataformas oficiales o de Steam.

## ¿Por qué un launcher?

Este programa nace de mi propia curiosidad: ¿cuánto llevo jugando esto? ¿Cuánto tiempo en total lo jugué?

La plataforma oficial no provee estos datos, y agregar el juego a Steam para que lo trackee tampoco funciona siempre, ya que Steam lanza el proceso y se "olvida" de él.

**Mi solución:** un launcher donde agregás tus `.exe`/binarios, creás un acceso directo, y cuando querés ver cuánto llevás jugado, accedés a la interfaz para revisar esos datos.

## Modo de uso

Se puede usar de 2 formas:

1. **Interfaz directa**: doble click al ejecutable y accedés a ella.
2. **Acceso directo**: creado por el mismo launcher, o manualmente con el argumento `--launch 'nombre_exe'`.

| Comando | Qué hace |
|---|---|
| *(sin argumentos)* | Abre la interfaz |
| `--launch "juego" --platform "plataforma"` | Lanza el juego sin abrir la interfaz y registra el tiempo (`--platform` es opcional) |

La interfaz vieja (Tk, `--tk`) se eliminó; la última versión que la incluye es el tag `ultima-version-tk`.

## ¿Cómo funciona?

### 1. Agregar una plataforma
Botón **"Agregar plataforma"** → te pide un nombre y un directorio.

Deberías seleccionar la carpeta **raíz** donde están tus programas. Por ejemplo, si quisieras agregar Steam (no es realmente el caso de uso pensado para esto, pero se puede), seleccionarías:

```
steam/steamapps/common/
```

El launcher automáticamente busca y muestra todos los ejecutables encontrados. Puede tardar un poco dependiendo de cuántos haya, y puede traer cosas que no son lo que buscás (filtra solo por extensión). Esos se pueden eliminar de la lista y no se vuelven a traer a menos que reescanees el directorio.

A partir de ahí, cada vez que entrés vas a tener la plataforma (con el nombre que hayas puesto) y los programas que hayas decidido dejar.

### 2. Gestionar programas y plataformas
Click derecho en un espacio vacío → **"Agregar programa"**.

Desde el menú de un juego podés jugarlo, quitarlo, marcarlo como favorito, crear accesos directos o cambiar su ejecutable. Con el juego seleccionado, **Enter** lo lanza y **Supr** lo quita (pide confirmación).

Con click derecho sobre la pestaña de la plataforma:
- **Propiedades**: lista de directorios (agregar, quitar, abrir en el explorador) y renombrar la plataforma
- **Recargar**: reescanea sus directorios
- **Eliminar plataforma**

En **⚙ Configuración** están la sincronización en la nube, la opción de permitir varios juegos abiertos a la vez y el **tema** de la interfaz (Cyberpunk, Oscuro, Claro, Nord, Dracula). Para crear un tema, copiá un `.json` de `data/themes/` y cambiá los colores (`#RRGGBB`).

Quitar un programa o una plataforma **no borra las horas jugadas**: dejan de mostrarse, y si volvés a agregarlos (o reescaneás) reaparecen con su historial.

### 3. Cloud sync
El launcher sincroniza los datos en la nube para no perderlos:

- Todo se guarda en un **JSON dentro de una carpeta en Google Drive**, con la lista de sesiones de juego.
- Cada sesión tiene un ID único y el **ID de la máquina** donde se jugó, así nunca se pisa información entre dispositivos y sincronizar dos veces no duplica horas.
- Las sesiones de meses ya cerrados se resumen en una sola fila por juego y por mes.

> ⚠️ Actualmente **solo yo puedo usar esta función**: el programa no está publicado, así que hay que habilitar el acceso a la API desde mi propia cuenta de Google. Si activás el cloud sync sin tener las credenciales de Google configuradas, el launcher no se rompe — tira un error al intentar sincronizar y sigue funcionando normalmente, simplemente sin guardar nada en la nube.

## Instalación / Ejecución

Por el momento la forma de instalar y ejecutar es clonar el repo y ejecutar launcher69.py directamente, la interfaz puede tener errores.
De todas formas deberias tomarte el trabajo de instalar las ['dependencias'](./requirements.txt) necesarias para que esto funcione.

Se puede empaquetar ejecutando `build.py` (antes: `pip install -r requirements-dev.txt`, que trae PyInstaller) (decide solo si genera `.exe` o binario según el SO). El resultado queda en `dist/Launcher69/`, ya con la estructura que necesita:

```
Launcher69(.exe)
_internal/
data/
    icons/      íconos del launcher
    themes/     base.qss + un .json por tema
```

En Linux, `build.py` usa `data/icons/icon.png`, que la app genera la primera vez que corre desde el código.

### Actualizar una instalación existente
1. Cerrá el launcher.
2. Reemplazá `Launcher69(.exe)`, `_internal/`, `data/icons/` y `data/themes/` por los de `dist/Launcher69/`.
3. **No borres** `data/databases/` ni `data/cloud_files/`: ahí están tus horas, tu cuenta y el id de la PC.

Al abrirla, la DB vieja (`config.db` + `notas.db`) se migra sola a `launcher.db`. Los archivos viejos quedan como respaldo. Los temas viejos (`theme_*.qss`) se pueden borrar.

---

📄 Para el detalle interno de funciones y arquitectura, ver ['ARQUITECTURA'](./documentacion/ARQUITECTURA.md) y ['FUNCIONES'](./documentacion/FUNCIONES.md).