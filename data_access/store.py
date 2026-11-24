"""Acceso a la base de datos del launcher.

Es el único módulo que escribe SQL. El resto del código habla en términos de
plataformas, juegos y sesiones.

Sesiones (`kind`):
- `session`: una partida. `ended_at IS NULL` mientras el juego corre.
- `month`: resumen de partidas terminadas de un mes cerrado, por juego y PC.
  `covers` lista los ids de las partidas que reemplaza.
- `legacy`: total de horas de una PC importado de la DB clave-valor vieja.
- `history`: partidas viejas importadas solo para mostrar; NO suman horas
  (ya están incluidas en su fila `legacy`).

Los `id` de sesión son uuid para poder mezclar sesiones de varias PCs (cloud sync).
Los resúmenes usan uuid5 deterministas, así dos PCs generan el mismo id para lo mismo.
"""

import json
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS platforms (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
    position  INTEGER                -- orden de la pestaña; NULL = oculta
);

CREATE TABLE IF NOT EXISTS platform_folders (
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    path        TEXT NOT NULL,
    PRIMARY KEY (platform_id, path)
);

CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,
    favorite    INTEGER NOT NULL DEFAULT 0,
    hidden      INTEGER NOT NULL DEFAULT 0,
    steam_appid TEXT,
    notes       TEXT NOT NULL DEFAULT '',
    UNIQUE (platform_id, name)
);

CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    game_id        INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    machine_id     TEXT NOT NULL,
    kind           TEXT NOT NULL DEFAULT 'session',
    started_at     TEXT NOT NULL,
    duration_s     INTEGER NOT NULL DEFAULT 0,
    sessions_count INTEGER NOT NULL DEFAULT 1,
    ended_at       TEXT,
    pid            INTEGER,
    covers         TEXT NOT NULL DEFAULT '[]'   -- solo `month`: ids que resume
);
CREATE INDEX IF NOT EXISTS sessions_by_game ON sessions(game_id, started_at);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_ID_NAMESPACE = uuid.UUID("6f1c2a4e-9b7d-4c1e-8a35-3d2f0b9e7c11")
_COUNTED = "s.kind <> 'history'"  # filas que suman horas
_SESSION_FIELDS = (
    "id",
    "platform",
    "game",
    "machine_id",
    "kind",
    "started_at",
    "duration_s",
    "sessions_count",
    "ended_at",
    "covers",
)


def summary_id(
    kind: str, machine_id: str, platform: str, game: str, period: str = ""
) -> str:
    """Id determinista para una fila resumen (mes o legacy)."""
    return str(
        uuid.uuid5(
            _ID_NAMESPACE, json.dumps([kind, machine_id, platform, game, period])
        )
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class Game:
    id: int
    platform: str
    name: str
    path: str
    favorite: bool
    hidden: bool
    steam_appid: str | None
    notes: str


@dataclass(frozen=True)
class Session:
    id: str
    platform: str
    game: str
    machine_id: str
    kind: str
    started_at: str
    duration_s: int
    sessions_count: int
    ended_at: str | None
    pid: int | None
    covers: list[str]


_GAME_COLS = (
    "g.id, p.name, g.name, g.path, g.favorite, g.hidden, g.steam_appid, g.notes"
)
_SESSION_COLS = (
    "s.id, p.name, g.name, s.machine_id, s.kind, s.started_at, s.duration_s, "
    "s.sessions_count, s.ended_at, s.pid, s.covers"
)
_SESSION_JOIN = (
    "sessions s JOIN games g ON g.id = s.game_id "
    "JOIN platforms p ON p.id = g.platform_id"
)


def _game(row: tuple) -> Game:
    return Game(
        row[0], row[1], row[2], row[3], bool(row[4]), bool(row[5]), row[6], row[7]
    )


def _session(row: tuple) -> Session:
    sid, platform, game, machine, kind, started, duration, count, ended, pid, covers = (
        row
    )
    return Session(
        sid,
        platform,
        game,
        machine,
        kind,
        started,
        duration,
        count,
        ended,
        pid,
        json.loads(covers),
    )


def _validate(session: dict) -> dict:
    missing = [f for f in _SESSION_FIELDS if f not in session and f != "covers"]
    if missing:
        raise ValueError(f"Sesión sin campos {missing}: {session!r}")
    return {"covers": [], **session}


class Store:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.lock = threading.RLock()
        with self.lock:
            # La UI y un `--launch` pueden escribir a la vez desde procesos distintos.
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.executescript(SCHEMA)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Todo o nada. Toma el lock de escritura de SQLite al empezar, así otro
        proceso no escribe en el medio. Anidada, se suma a la transacción externa."""
        with self.lock:
            if self.conn.in_transaction:
                yield self.conn
                return
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                self.conn.rollback()
                raise
            self.conn.commit()

    def _query(self, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
        with self.lock:
            return self.conn.execute(sql, tuple(params)).fetchall()

    def _write(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.transaction() as conn:
            return conn.execute(sql, tuple(params))

    # ---------------- settings ----------------
    def get_setting(self, key: str, default: Any = None) -> Any:
        rows = self._query("SELECT value FROM settings WHERE key = ?", (key,))
        return json.loads(rows[0][0]) if rows else default

    def set_setting(self, key: str, value: Any) -> None:
        self._write(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    # ---------------- plataformas ----------------
    def _platform_id(self, name: str) -> int | None:
        rows = self._query("SELECT id FROM platforms WHERE name = ?", (name,))
        return rows[0][0] if rows else None

    def _ensure_platform(self, name: str) -> int:
        with self.transaction() as conn:
            conn.execute("INSERT OR IGNORE INTO platforms(name) VALUES (?)", (name,))
            return conn.execute(
                "SELECT id FROM platforms WHERE name = ?", (name,)
            ).fetchone()[0]

    def list_platforms(self) -> list[str]:
        """Plataformas visibles, en el orden de las pestañas."""
        rows = self._query(
            "SELECT name FROM platforms WHERE position IS NOT NULL ORDER BY position"
        )
        return [r[0] for r in rows]

    def add_platform(self, name: str) -> None:
        """Crea la plataforma (o la vuelve a mostrar) al final de las pestañas."""
        with self.transaction() as conn:
            self._ensure_platform(name)
            conn.execute(
                "UPDATE platforms SET position = "
                "(SELECT COALESCE(MAX(position), -1) + 1 FROM platforms) "
                "WHERE name = ? AND position IS NULL",
                (name,),
            )

    def rename_platform(self, old: str, new: str) -> bool:
        try:
            cur = self._write(
                "UPDATE platforms SET name = ? WHERE name = ?", (new, old)
            )
        except sqlite3.IntegrityError:  # ya existe una con el nombre nuevo
            return False
        return cur.rowcount == 1

    def reorder_platforms(self, names: list[str]) -> None:
        with self.transaction() as conn:
            for position, name in enumerate(names):
                conn.execute(
                    "UPDATE platforms SET position = ? WHERE name = ?", (position, name)
                )

    def hide_platform(self, name: str) -> None:
        """Saca la pestaña y oculta sus juegos. Las horas jugadas se conservan."""
        pid = self._platform_id(name)
        if pid is None:
            return
        with self.transaction() as conn:
            conn.execute("UPDATE platforms SET position = NULL WHERE id = ?", (pid,))
            conn.execute(
                "UPDATE games SET hidden = 1, favorite = 0 WHERE platform_id = ?",
                (pid,),
            )
            conn.execute("DELETE FROM platform_folders WHERE platform_id = ?", (pid,))

    def list_folders(self, platform: str) -> list[str]:
        rows = self._query(
            "SELECT f.path FROM platform_folders f "
            "JOIN platforms p ON p.id = f.platform_id "
            "WHERE p.name = ? ORDER BY f.path",
            (platform,),
        )
        return [r[0] for r in rows]

    def add_folder(self, platform: str, path: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO platform_folders(platform_id, path) VALUES (?, ?)",
                (self._ensure_platform(platform), path),
            )

    def remove_folder(self, platform: str, path: str) -> None:
        self._write(
            "DELETE FROM platform_folders WHERE path = ? "
            "AND platform_id = (SELECT id FROM platforms WHERE name = ?)",
            (path, platform),
        )

    # ---------------- juegos ----------------
    def list_games(self, platform: str) -> list[Game]:
        """Juegos visibles: primero los jugados (más reciente primero), después por nombre."""
        rows = self._query(
            f"SELECT {_GAME_COLS} FROM games g JOIN platforms p ON p.id = g.platform_id "
            "LEFT JOIN (SELECT game_id, MAX(started_at) AS last FROM sessions "
            "GROUP BY game_id) l ON l.game_id = g.id "
            "WHERE p.name = ? AND g.hidden = 0 "
            "ORDER BY l.last IS NULL, l.last DESC, lower(g.name)",
            (platform,),
        )
        return [_game(r) for r in rows]

    def get_game(self, platform: str, name: str) -> Game | None:
        rows = self._query(
            f"SELECT {_GAME_COLS} FROM games g JOIN platforms p ON p.id = g.platform_id "
            "WHERE p.name = ? AND g.name = ?",
            (platform, name),
        )
        return _game(rows[0]) if rows else None

    def find_game(self, name: str) -> Game | None:
        """Primer juego visible con ese nombre, en cualquier plataforma."""
        rows = self._query(
            f"SELECT {_GAME_COLS} FROM games g JOIN platforms p ON p.id = g.platform_id "
            "WHERE g.name = ? AND g.hidden = 0 "
            "ORDER BY p.position IS NULL, p.position LIMIT 1",
            (name,),
        )
        return _game(rows[0]) if rows else None

    def add_game(self, platform: str, name: str, path: str) -> bool:
        """Agrega un juego. Si estaba oculto, lo vuelve a mostrar con la ruta nueva.

        Devuelve False si ya existe un juego visible con ese nombre.
        """
        with self.transaction():
            existing = self.get_game(platform, name)
            if existing and not existing.hidden:
                return False
            self._upsert_by_name(platform, name, path)
            return True

    def upsert_game(self, platform: str, name: str, path: str) -> None:
        """Lo usa el escaneo: deja visible el juego de esa ruta.

        Si ya hay un juego con la misma ruta (aunque se llame distinto, ej. migrado
        con otro nombre) se reutiliza, para no partir sus horas en dos.
        """
        with self.transaction() as conn:
            pid = self._ensure_platform(platform)
            cur = conn.execute(
                "UPDATE games SET hidden = 0 WHERE platform_id = ? AND path = ?",
                (pid, path),
            )
            if cur.rowcount == 0:
                self._upsert_by_name(platform, name, path)

    def _upsert_by_name(self, platform: str, name: str, path: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO games(platform_id, name, path) VALUES (?, ?, ?) "
                "ON CONFLICT(platform_id, name) DO UPDATE "
                "SET path = excluded.path, hidden = 0",
                (self._ensure_platform(platform), name, path),
            )

    def _update_game(self, platform: str, name: str, column: str, value: Any) -> None:
        self._write(
            f"UPDATE games SET {column} = ? WHERE name = ? AND platform_id = "
            "(SELECT id FROM platforms WHERE name = ?)",
            (value, name, platform),
        )

    def hide_game(self, platform: str, name: str) -> None:
        """Oculta el juego. Sus sesiones se conservan (y siguen en la nube)."""
        with self.transaction():
            self._update_game(platform, name, "hidden", 1)
            self._update_game(platform, name, "favorite", 0)

    def set_game_path(self, platform: str, name: str, path: str) -> None:
        self._update_game(platform, name, "path", path)

    def set_favorite(self, platform: str, name: str, favorite: bool) -> None:
        self._update_game(platform, name, "favorite", int(favorite))

    def set_steam_appid(self, platform: str, name: str, appid: str | None) -> None:
        self._update_game(platform, name, "steam_appid", appid)

    def set_notes(self, platform: str, name: str, notes: str) -> None:
        self._update_game(platform, name, "notes", notes)

    def list_favorites(self, platform: str) -> list[Game]:
        return [g for g in self.list_games(platform) if g.favorite]

    def has_running_games(self, platform: str) -> bool:
        return any(s.platform == platform for s in self.open_sessions())

    # ---------------- sesiones ----------------
    def start_session(self, game_id: int, machine_id: str, pid: int | None) -> str:
        session_id = str(uuid.uuid4())
        self._write(
            "INSERT INTO sessions(id, game_id, machine_id, started_at, pid) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, game_id, machine_id, _now(), pid),
        )
        return session_id

    def update_session(self, session_id: str, duration_s: int) -> None:
        """Guarda el avance de una partida en curso (no toca una ya cerrada)."""
        self._write(
            "UPDATE sessions SET duration_s = ? WHERE id = ? AND ended_at IS NULL",
            (duration_s, session_id),
        )

    def end_session(self, session_id: str, duration_s: int | None = None) -> None:
        """Cierra la sesión. Sin duración, conserva la última guardada."""
        self._write(
            "UPDATE sessions SET duration_s = COALESCE(?, duration_s), ended_at = ?, "
            "pid = NULL WHERE id = ?",
            (duration_s, _now(), session_id),
        )

    def open_sessions(self) -> list[Session]:
        """Juegos corriendo en esta PC.

        Las sesiones abiertas que llegan de otra PC no traen `pid`, así que no cuentan.
        """
        rows = self._query(
            f"SELECT {_SESSION_COLS} FROM {_SESSION_JOIN} "
            "WHERE s.ended_at IS NULL AND s.pid IS NOT NULL ORDER BY s.started_at"
        )
        return [_session(r) for r in rows]

    def open_session_for(self, platform: str, game: str) -> Session | None:
        for s in self.open_sessions():
            if (s.platform, s.game) == (platform, game):
                return s
        return None

    def close_orphan_sessions(self, is_alive: Callable[[int], bool]) -> None:
        """Cierra las sesiones abiertas cuyo proceso ya no existe (cierre abrupto)."""
        for s in self.open_sessions():
            if s.pid is not None and not is_alive(s.pid):
                self.end_session(s.id)

    def recent_sessions(
        self, platform: str, game: str, limit: int = 20
    ) -> list[Session]:
        """Últimas filas de historial del juego (partidas y resúmenes), más nuevas primero."""
        rows = self._query(
            f"SELECT {_SESSION_COLS} FROM {_SESSION_JOIN} "
            "WHERE p.name = ? AND g.name = ? ORDER BY s.started_at DESC LIMIT ?",
            (platform, game, limit),
        )
        return [_session(r) for r in rows]

    def total_seconds(self, platform: str, game: str) -> int:
        rows = self._query(
            f"SELECT COALESCE(SUM(s.duration_s), 0) FROM {_SESSION_JOIN} "
            f"WHERE p.name = ? AND g.name = ? AND {_COUNTED}",
            (platform, game),
        )
        return rows[0][0]

    def compact_months(self, machine_id: str, today: datetime | None = None) -> int:
        """Resume en una fila por mes las partidas terminadas de meses ya cerrados.

        Solo toca las sesiones de esta PC: cada PC resume las suyas y el resumen
        viaja a las demás por la nube. Devuelve cuántas partidas se resumieron.
        """
        current_month = (today or datetime.now()).strftime("%Y-%m")
        with self.transaction() as conn:
            rows = conn.execute(
                f"SELECT s.id, s.game_id, p.name, g.name, substr(s.started_at, 1, 7), "
                f"s.duration_s FROM {_SESSION_JOIN} "
                "WHERE s.machine_id = ? AND s.kind = 'session' AND s.ended_at IS NOT NULL "
                "AND substr(s.started_at, 1, 7) < ?",
                (machine_id, current_month),
            ).fetchall()
            groups: dict[tuple, list[tuple[str, int]]] = {}
            for sid, game_id, platform, game, month, duration in rows:
                groups.setdefault((game_id, platform, game, month), []).append(
                    (sid, duration)
                )
            for (game_id, platform, game, month), items in groups.items():
                self._add_to_month(
                    conn, game_id, machine_id, platform, game, month, items
                )
                conn.executemany(
                    "DELETE FROM sessions WHERE id = ?", [(sid,) for sid, _ in items]
                )
        return len(rows)

    def _add_to_month(self, conn, game_id, machine_id, platform, game, month, items):
        month_id = summary_id("month", machine_id, platform, game, month)
        row = conn.execute(
            "SELECT duration_s, covers FROM sessions WHERE id = ?", (month_id,)
        ).fetchone()
        duration, covers = (row[0], json.loads(row[1])) if row else (0, [])
        new = [(sid, d) for sid, d in items if sid not in covers]
        covers += [sid for sid, _ in new]
        duration += sum(d for _, d in new)
        start = f"{month}-01T00:00:00"
        conn.execute(
            "INSERT INTO sessions(id, game_id, machine_id, kind, started_at, duration_s, "
            "sessions_count, ended_at, covers) VALUES (?, ?, ?, 'month', ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET duration_s = excluded.duration_s, "
            "sessions_count = excluded.sessions_count, covers = excluded.covers",
            (
                month_id,
                game_id,
                machine_id,
                start,
                duration,
                len(covers),
                start,
                json.dumps(covers),
            ),
        )

    # ---------------- cloud sync ----------------
    def export_sessions(self) -> list[dict]:
        """Todas las sesiones, identificadas por nombres (los ids numéricos son locales)."""
        rows = self._query(f"SELECT {_SESSION_COLS} FROM {_SESSION_JOIN}")
        return [
            {k: v for k, v in asdict(_session(r)).items() if k != "pid"} for r in rows
        ]

    def import_sessions(self, sessions: Iterable[dict]) -> None:
        """Mezcla sesiones de otra fuente, todo o nada. Repetirlo no duplica nada.

        - Misma sesión (mismo id): mayor duración y el cierre si lo hay. Para un
          resumen mensual gana la versión que cubre más partidas.
        - Juegos o plataformas que no existen acá se crean ocultos.
        - Un resumen borra exactamente las partidas que lista en `covers`, y esas
          partidas ya no vuelven a entrar.
        """
        batch = [_validate(s) for s in sessions]
        with self.transaction() as conn:
            for s in batch:
                game_id = self._ensure_hidden_game(s["platform"], s["game"])
                if s["kind"] == "session" and self._is_covered(s["id"]):
                    continue
                if s["kind"] == "month":
                    conn.executemany(
                        "DELETE FROM sessions WHERE id = ? AND kind = 'session'",
                        [(sid,) for sid in s["covers"]],
                    )
                conn.execute(
                    "INSERT INTO sessions(id, game_id, machine_id, kind, started_at, "
                    "duration_s, sessions_count, ended_at, covers) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET "
                    "duration_s = CASE WHEN kind = 'month' THEN "
                    "  (CASE WHEN excluded.sessions_count > sessions_count "
                    "   THEN excluded.duration_s ELSE duration_s END) "
                    "  ELSE MAX(duration_s, excluded.duration_s) END, "
                    "covers = CASE WHEN excluded.sessions_count > sessions_count "
                    "  THEN excluded.covers ELSE covers END, "
                    "sessions_count = MAX(sessions_count, excluded.sessions_count), "
                    "ended_at = COALESCE(ended_at, excluded.ended_at)",
                    (
                        s["id"],
                        game_id,
                        s["machine_id"],
                        s["kind"],
                        s["started_at"],
                        s["duration_s"],
                        s["sessions_count"],
                        s["ended_at"],
                        json.dumps(s["covers"]),
                    ),
                )

    def _is_covered(self, session_id: str) -> bool:
        return bool(
            self.conn.execute(
                "SELECT 1 FROM sessions, json_each(sessions.covers) "
                "WHERE sessions.kind = 'month' AND json_each.value = ? LIMIT 1",
                (session_id,),
            ).fetchone()
        )

    def _ensure_hidden_game(self, platform: str, game: str) -> int:
        with self.transaction() as conn:
            pid = self._ensure_platform(platform)
            conn.execute(
                "INSERT OR IGNORE INTO games(platform_id, name, path, hidden) "
                "VALUES (?, ?, '', 1)",
                (pid, game),
            )
            return conn.execute(
                "SELECT id FROM games WHERE platform_id = ? AND name = ?", (pid, game)
            ).fetchone()[0]
