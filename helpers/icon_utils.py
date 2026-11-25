import hashlib
from pathlib import Path

from PIL import Image


def icon_cache_name(game_path: str) -> str:
    """Nombre del ícono cacheado de un juego, único por ruta.

    Por nombre de archivo chocarían dos juegos con `Game.exe`.
    """
    return hashlib.sha1(game_path.encode()).hexdigest()[:16]


def ico_to_png(ico_path, output_dir=None, size=(256, 256)):
    ico_path = Path(ico_path)
    if not ico_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {ico_path}")

    # Directorio destino
    if output_dir is None:
        output_dir = ico_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    png_path = output_dir / (ico_path.stem + ".png")

    # Si ya existe, no lo volvemos a generar
    if png_path.exists():
        return png_path

    # Convertir
    img = Image.open(ico_path).convert("RGBA")
    if size:
        img.thumbnail(size)

    img.save(png_path, "PNG")

    return png_path
