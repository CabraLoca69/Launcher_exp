"""Migración única desde la DB clave-valor vieja (`config.db` + `notas.db`).

Los archivos viejos no se modifican: quedan como backup.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .store import Store, summary_id

logger = logging.getLogger(__name__)

_EPOCH = "1970-01-01T00:00:00"
LEGACY_PC = "__legacy"  # totales viejos que no sabían de qué PC eran
_SETTINGS = ("email", "cloud_sync_enabled", "allow_multiple_games", "wineprefix")


def _read_kv(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
    finally:
        conn.close()
    result = {}
    for key, value in rows:
        try:
            result[key] = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            continue
    return result


def _split(key: str, section: str) -> tuple[str, str] | None:
    """`plat.<section>.resto` → (plat, resto). Las plataformas viejas no tenían '.'."""
    platform, sep, rest = key.partition(f".{section}.")
    if not sep or platform == "global" or "." in platform:
        return None
    return platform, rest


def migrate(config_file: Path, notes_file: Path, store: Store, machine_id: str) -> None:
    """Copia todo a `store` en una sola transacción: si algo falla, no queda nada a medias."""
    kv = _read_kv(config_file)
    notes = _read_kv(notes_file)
    with store.transaction():
        _migrate(kv, notes, store, machine_id)


def _migrate(
    kv: dict[str, Any], notes: dict[str, Any], store: Store, machine_id: str
) -> None:
    for name in kv.get("global.tab_order") or []:
        store.add_platform(name)

    for key in [k for k in kv if k.startswith("global.")]:
        name = key.removeprefix("global.")
        if name in _SETTINGS and kv[key] is not None:
            store.set_setting(name, kv[key])

    for key, value in kv.items():
        if key.endswith(".platform_folders") and key.count(".") == 1:
            for folder in value or []:
                store.add_folder(key.split(".")[0], folder)

    games: dict[str, list[tuple[str, str]]] = {}  # nombre -> [(plataforma, nombre)]
    for key, path in kv.items():
        parts = _split(key, "game_list")
        if parts and isinstance(path, str):
            store.upsert_game(parts[0], parts[1], path)
            games.setdefault(parts[1], []).append(parts)

    for key, value in kv.items():
        if key.endswith(".favorites") and key.count(".") == 1:
            for name in value or []:
                store.set_favorite(key.split(".")[0], name, True)

    for name, appid in (
        (k.removeprefix("global.steam_ids."), v)
        for k, v in kv.items()
        if k.startswith("global.steam_ids.")
    ):
        for platform, game in games.get(name, []):
            store.set_steam_appid(platform, game, str(appid))

    for name, text in notes.items():
        for platform, game in games.get(name, []):
            store.set_notes(platform, game, str(text))

    store.import_sessions(_sessions(kv, machine_id))


def _minutes(value: Any) -> float:
    try:
        return max(float(value or 0), 0.0)
    except (TypeError, ValueError):
        logger.warning("Tiempo inválido en la DB vieja: %r", value)
        return 0.0


def legacy_row(pc: str, platform: str, game: str, minutes: Any) -> dict:
    """Total de horas de una PC para un juego. El id es el mismo en todas las PCs,
    así el merge (MAX) unifica las copias que llegan por distintos caminos."""
    return _row(
        summary_id("legacy", pc, platform, game),
        platform,
        game,
        pc,
        "legacy",
        _EPOCH,
        round(_minutes(minutes) * 60),
    )


def _sessions(kv: dict[str, Any], machine_id: str) -> list[dict]:
    """Totales por PC → filas `legacy` con el total completo.

    Las últimas 5 partidas de esta PC → filas `history`: se ven en el historial
    pero no suman, porque ya están dentro de su total legacy.
    """
    rows = []
    for key, value in kv.items():
        parts = _split(key, "game_total_times")
        if not parts:
            continue
        platform, rest = parts
        if isinstance(value, dict):  # formato muy viejo: {pc: minutos}
            rows += [legacy_row(pc, platform, rest, m) for pc, m in value.items()]
        elif "." in rest:
            game, pc = rest.rsplit(".", 1)
            rows.append(legacy_row(pc, platform, game, value))
        else:  # total suelto sin PC
            rows.append(legacy_row(LEGACY_PC, platform, rest, value))

    for key, value in kv.items():
        parts = _split(key, "game_times")
        if not parts or not isinstance(value, list):
            continue
        for s in value:
            try:
                started = datetime.strptime(s["Start"], "%Y-%m-%d %H:%M:%S").isoformat()
            except (KeyError, TypeError, ValueError):
                logger.warning("Sesión vieja inválida: %r", s)
                continue
            rows.append(
                _row(
                    summary_id("history", machine_id, *parts, started),
                    *parts,
                    machine_id,
                    "history",
                    started,
                    round(_minutes(s.get("Tiempo")) * 60),
                )
            )
    return rows


def _row(id_, platform, game, machine_id, kind, started_at, duration_s) -> dict:
    return {
        "id": id_,
        "platform": platform,
        "game": game,
        "machine_id": machine_id,
        "kind": kind,
        "started_at": started_at,
        "duration_s": duration_s,
        "sessions_count": 1,
        "ended_at": started_at,
    }


def run_pending_migration() -> None:
    """Migra la DB vieja la primera vez que arranca esta versión.

    Si falla, se loguea y se reintenta en el próximo arranque (la app sigue).
    """
    from .datafiles import OLD_CONFIG_FILE, OLD_NOTES_FILE, store
    from .machine_id import get_machine_id

    if store.get_setting("kv_migrated") or not OLD_CONFIG_FILE.exists():
        return
    try:
        migrate(OLD_CONFIG_FILE, OLD_NOTES_FILE, store, get_machine_id())
    except Exception:
        logger.exception(
            "No se pudo migrar la DB vieja; se reintenta al próximo arranque"
        )
        return
    store.set_setting("kv_migrated", True)
    logger.info("DB vieja migrada desde %s", OLD_CONFIG_FILE)
