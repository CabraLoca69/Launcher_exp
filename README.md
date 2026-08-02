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

Actualmente el launcher tiene 2 interfaces utilizables:

| Comando | Interfaz |
|---|---|
| *(sin argumentos)* | UI en desarrollo |
| `--tk` | UI antigua |

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

Desde el menú también podés:
- Quitar un programa
- Reescanear el directorio
- Agregar más directorios a la misma plataforma (repite el mismo proceso de escaneo)
- Eliminar la plataforma directamente

### 3. Cloud sync
El launcher sincroniza los datos en la nube para no perderlos:

- Todo se guarda en un **JSON dentro de una carpeta en Google Drive**.
- Se usa un **ID por máquina** para diferenciar el origen de los datos, así nunca se pisa información entre dispositivos.

> ⚠️ Actualmente **solo yo puedo usar esta función**: el programa no está publicado, así que hay que habilitar el acceso a la API desde mi propia cuenta de Google.

## Instalación / Ejecución

Por el momento la forma de instalar y ejecutar es clonar el repo y ejecutar launcher69.py directamente, la interfaz puede tener errores.
De todas formas deberias tomarte el trabajo de instalar las ['dependencias'](./requirements.txt) necesarias para que esto funcione.
Lanzarlo desde la terminal (en linux) python launcher60.py --tk, abrira la interfaz antigua, es menos probable encontrar errores ahi.

Se puede empaquetar el script ejecutando build.py, el solo decide si .exe o binario segun so. Deberias mantener la arquitectura:
launcher69
_internals
/data
    /icons
        iconos.ico/.png
    /themes
        algun_tema.qss

de otra forma no va a abrirse nada o se abrira roto.

---

📄 Para el detalle interno de funciones y arquitectura, ver ['ARQUITECTURA.md'](./ARQUITECTURA.md) y ['FUNCIONES.md'](./FUNCIONES.md).