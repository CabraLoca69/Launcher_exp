from datetime import datetime

import pytest

from data_access.store import Store, summary_id


@pytest.fixture
def st(tmp_path):
    return Store(tmp_path / "t.db")


def _play(st, platform, game, seconds, started_at, machine="pc1", ended=True):
    """Crea una partida con fecha fija."""
    g = st.get_game(platform, game)
    sid = st.start_session(g.id, machine, pid=123)
    with st.conn:
        st.conn.execute(
            "UPDATE sessions SET started_at = ?, duration_s = ?, ended_at = ?, pid = ? WHERE id = ?",
            (
                started_at,
                seconds,
                started_at if ended else None,
                None if ended else 123,
                sid,
            ),
        )
    return sid


# ---------------- settings ----------------
def test_settings_roundtrip_and_default(st):
    assert st.get_setting("x", 5) == 5
    st.set_setting("x", {"a": [1, "ñ"]})
    assert st.get_setting("x") == {"a": [1, "ñ"]}


# ---------------- plataformas ----------------
def test_platforms_keep_insertion_order_and_reorder(st):
    for name in ("steam", "gog", "epic"):
        st.add_platform(name)
    assert st.list_platforms() == ["steam", "gog", "epic"]
    st.reorder_platforms(["epic", "steam", "gog"])
    assert st.list_platforms() == ["epic", "steam", "gog"]


def test_rename_platform_keeps_games_and_rejects_duplicates(st):
    st.add_platform("steam")
    st.add_platform("gog")
    st.add_game("steam", "a", "/a")
    assert st.rename_platform("steam", "Steam.Deck") is True
    assert st.get_game("Steam.Deck", "a").path == "/a"
    assert st.rename_platform("gog", "Steam.Deck") is False
    assert st.rename_platform("nope", "x") is False


def test_hide_platform_keeps_playtime_and_readd_restores_it(st):
    st.add_platform("steam")
    st.add_folder("steam", "/lib")
    st.add_game("steam", "a", "/lib/a")
    _play(st, "steam", "a", 600, "2026-11-01T10:00:00")

    st.hide_platform("steam")
    assert st.list_platforms() == []
    assert st.list_folders("steam") == []
    assert st.list_games("steam") == []

    st.add_platform("steam")
    st.upsert_game("steam", "a", "/lib/a", revive=True)  # carpeta agregada de nuevo
    assert [g.name for g in st.list_games("steam")] == ["a"]
    assert st.total_seconds("steam", "a") == 600


def test_folders(st):
    st.add_folder("steam", "/b")
    st.add_folder("steam", "/a")
    st.add_folder("steam", "/a")
    assert st.list_folders("steam") == ["/a", "/b"]
    st.remove_folder("steam", "/a")
    assert st.list_folders("steam") == ["/b"]


# ---------------- juegos ----------------
def test_names_with_dots_and_wildcards_are_plain_values(st):
    st.add_game("p", "Game.v2", "/g1")
    st.add_game("p", "my_game", "/g2")
    st.add_game("p", "myXgame", "/g3")
    assert st.get_game("p", "Game.v2").path == "/g1"
    assert st.find_game("my_game").path == "/g2"


def test_add_game_rejects_visible_duplicate_but_revives_hidden(st):
    assert st.add_game("p", "a", "/old") is True
    assert st.add_game("p", "a", "/other") is False
    st.hide_game("p", "a")
    assert st.add_game("p", "a", "/new") is True
    game = st.get_game("p", "a")
    assert (game.path, game.hidden) == ("/new", False)


def test_hide_game_removes_favorite_and_hides_from_lists(st):
    st.add_game("p", "a", "/a")
    st.set_favorite("p", "a", True)
    st.hide_game("p", "a")
    assert st.list_games("p") == []
    assert st.list_favorites("p") == []
    assert st.find_game("a") is None


def test_find_game_prefers_first_visible_platform(st):
    st.add_platform("steam")
    st.add_platform("gog")
    st.add_game("gog", "a", "/gog/a")
    st.add_game("steam", "a", "/steam/a")
    assert st.find_game("a").platform == "steam"


def test_list_games_orders_by_last_played_then_name(st):
    for name in ("zeta", "Alpha", "old", "new"):
        st.add_game("p", name, f"/{name}")
    _play(st, "p", "old", 10, "2025-01-01T10:00:00")
    _play(st, "p", "new", 10, "2026-01-01T10:00:00")
    assert [g.name for g in st.list_games("p")] == ["new", "old", "Alpha", "zeta"]


def test_upsert_reuses_game_with_same_path(st):
    """Juego migrado como `Game_v2`: el escaneo lo encuentra como `Game.v2` y no lo duplica."""
    st.add_game("p", "Game_v2", "/g/Game.v2")
    st.upsert_game("p", "Game.v2", "/g/Game.v2")
    assert [g.name for g in st.list_games("p")] == ["Game_v2"]


def test_upsert_without_revive_keeps_hidden_game_hidden(st):
    """Recargar la pestaña no trae de vuelta un juego que el usuario borró."""
    st.add_game("p", "a", "/g/a")
    st.hide_game("p", "a")
    st.upsert_game("p", "a", "/g/a")
    st.upsert_game("p", "a", "/g/otra/a")  # mismo nombre, otra ruta
    assert st.list_games("p") == []
    st.upsert_game("p", "a", "/g/a", revive=True)
    assert [g.name for g in st.list_games("p")] == ["a"]


def test_hide_platform_clears_favorites(st):
    st.add_platform("p")
    st.add_game("p", "a", "/a")
    st.set_favorite("p", "a", True)
    st.hide_platform("p")
    assert st.get_game("p", "a").favorite is False


def test_game_attributes(st):
    st.add_game("p", "a", "/a")
    st.set_game_path("p", "a", "/b")
    st.set_steam_appid("p", "a", "620")
    st.set_notes("p", "a", "jefe final pendiente")
    game = st.get_game("p", "a")
    assert (game.path, game.steam_appid, game.notes) == (
        "/b",
        "620",
        "jefe final pendiente",
    )


# ---------------- sesiones ----------------
def test_session_lifecycle(st):
    st.add_game("p", "a", "/a")
    game = st.get_game("p", "a")
    sid = st.start_session(game.id, "pc1", pid=42)
    assert [s.id for s in st.open_sessions()] == [sid]
    assert st.open_session_for("p", "a").pid == 42

    st.update_session(sid, 60)
    st.end_session(sid, 90)

    assert st.open_sessions() == []
    assert st.total_seconds("p", "a") == 90
    [s] = st.recent_sessions("p", "a")
    assert (s.duration_s, s.ended_at is not None, s.pid) == (90, True, None)


def test_update_after_end_does_not_overwrite_final_duration(st):
    st.add_game("p", "a", "/a")
    sid = st.start_session(st.get_game("p", "a").id, "pc1", pid=1)
    st.end_session(sid, 90)
    st.update_session(sid, 60)  # heartbeat que llegó tarde
    assert st.total_seconds("p", "a") == 90


def test_close_orphan_sessions_keeps_last_saved_duration(st):
    st.add_game("p", "a", "/a")
    st.add_game("p", "b", "/b")
    dead = st.start_session(st.get_game("p", "a").id, "pc1", pid=1)
    alive = st.start_session(st.get_game("p", "b").id, "pc1", pid=2)
    st.update_session(dead, 120)

    st.close_orphan_sessions(lambda s: s.pid == 2)

    assert [s.id for s in st.open_sessions()] == [alive]
    assert st.total_seconds("p", "a") == 120


def test_recent_sessions_newest_first_with_limit(st):
    st.add_game("p", "a", "/a")
    for day in range(1, 6):
        _play(st, "p", "a", day, f"2026-11-0{day}T10:00:00")
    assert [s.duration_s for s in st.recent_sessions("p", "a", limit=3)] == [5, 4, 3]


# ---------------- resumen mensual ----------------
def test_compact_months_summarizes_closed_months_only(st):
    st.add_game("p", "a", "/a")
    _play(st, "p", "a", 100, "2026-09-03T10:00:00")
    _play(st, "p", "a", 200, "2026-09-20T10:00:00")
    _play(st, "p", "a", 50, "2026-10-01T10:00:00")
    _play(st, "p", "a", 7, "2026-11-02T10:00:00")  # mes en curso
    _play(st, "p", "a", 9, "2026-09-05T10:00:00", machine="otra")  # otra PC
    _play(st, "p", "a", 3, "2026-09-06T10:00:00", ended=False)  # sigue abierta

    assert st.compact_months("pc1", today=datetime(2026, 11, 24)) == 3

    rows = {
        (s.kind, s.started_at[:7], s.machine_id): s
        for s in st.recent_sessions("p", "a")
    }
    assert rows[("month", "2026-09", "pc1")].duration_s == 300
    assert rows[("month", "2026-09", "pc1")].sessions_count == 2
    assert rows[("month", "2026-10", "pc1")].duration_s == 50
    assert ("session", "2026-11", "pc1") in rows
    assert ("session", "2026-09", "otra") in rows
    assert st.total_seconds("p", "a") == 100 + 200 + 50 + 7 + 9 + 3


def test_compact_months_is_atomic_with_other_writers(st, tmp_path):
    """Dos procesos compactando a la vez no duplican el mes."""
    st.add_game("p", "a", "/a")
    _play(st, "p", "a", 100, "2026-09-03T10:00:00")
    other = Store(st.conn.execute("PRAGMA database_list").fetchone()[2])
    today = datetime(2026, 11, 24)
    st.compact_months("pc1", today)
    other.compact_months("pc1", today)
    assert st.total_seconds("p", "a") == 100


def test_compact_months_is_idempotent_and_accumulates_late_sessions(st):
    st.add_game("p", "a", "/a")
    _play(st, "p", "a", 100, "2026-09-03T10:00:00")
    today = datetime(2026, 11, 24)
    st.compact_months("pc1", today)
    assert st.compact_months("pc1", today) == 0

    _play(st, "p", "a", 20, "2026-09-30T23:00:00")  # partida que cerró tarde
    st.compact_months("pc1", today)

    [month] = [s for s in st.recent_sessions("p", "a") if s.kind == "month"]
    assert (month.duration_s, month.sessions_count) == (120, 2)
    assert month.id == summary_id("month", "pc1", "p", "a", "2026-09")


# ---------------- cloud ----------------
def _session_dict(**kw):
    base = {
        "id": "s1",
        "platform": "p",
        "game": "a",
        "machine_id": "pc2",
        "kind": "session",
        "started_at": "2026-11-10T10:00:00",
        "duration_s": 60,
        "sessions_count": 1,
        "ended_at": None,
    }
    return base | kw


def test_import_creates_hidden_game_and_is_idempotent(st):
    st.import_sessions([_session_dict()])
    st.import_sessions([_session_dict()])
    game = st.get_game("p", "a")
    assert game.hidden is True
    assert st.total_seconds("p", "a") == 60
    assert st.list_platforms() == []  # plataforma solo conocida por la nube: oculta


def test_import_keeps_max_duration_and_closes(st):
    st.import_sessions([_session_dict(duration_s=300, ended_at="2026-11-10T10:05:00")])
    st.import_sessions([_session_dict(duration_s=120)])
    [s] = st.recent_sessions("p", "a")
    assert (s.duration_s, s.ended_at) == (300, "2026-11-10T10:05:00")


def test_imported_open_sessions_are_not_running_here(st):
    st.import_sessions([_session_dict()])
    assert st.open_sessions() == []


def _month(covers, duration, machine="pc2", month="2026-09"):
    return _session_dict(
        id=summary_id("month", machine, "p", "a", month),
        kind="month",
        machine_id=machine,
        started_at=f"{month}-01T00:00:00",
        ended_at=f"{month}-01T00:00:00",
        duration_s=duration,
        sessions_count=len(covers),
        covers=covers,
    )


def test_month_summary_replaces_exactly_the_sessions_it_covers(st):
    st.import_sessions(
        [
            _session_dict(
                id="s1", started_at="2026-09-01T10:00:00", ended_at="x", duration_s=100
            ),
            _session_dict(
                id="s2", started_at="2026-09-02T10:00:00", ended_at="x", duration_s=200
            ),
        ]
    )
    st.import_sessions([_month(["s1", "s2"], 300)])
    st.import_sessions(
        [
            _session_dict(
                id="s1", started_at="2026-09-01T10:00:00", ended_at="x", duration_s=100
            )
        ]
    )

    assert [s.kind for s in st.recent_sessions("p", "a")] == ["month"]
    assert st.total_seconds("p", "a") == 300


def test_own_month_echo_keeps_session_that_ended_after_compaction(st):
    """Partida que empezó el 31 y seguía abierta al compactar: no se pierde."""
    st.add_game("p", "a", "/a")
    _play(st, "p", "a", 100, "2026-01-10T10:00:00")
    late = _play(st, "p", "a", 7200, "2026-01-31T23:00:00", ended=False)
    st.compact_months("pc1", today=datetime(2026, 2, 1))
    st.end_session(late, 7200)

    st.import_sessions(st.export_sessions())  # eco desde la nube

    assert st.total_seconds("p", "a") == 7300


def test_month_summary_removes_partial_open_copy_from_other_pc(st):
    """B importó la partida de A mientras corría; al llegar el resumen de A no suma dos veces."""
    st.import_sessions(
        [_session_dict(id="s1", started_at="2026-09-01T10:00:00", duration_s=600)]
    )
    st.import_sessions([_month(["s1"], 7200)])
    assert st.total_seconds("p", "a") == 7200


def test_month_summary_with_more_sessions_wins(st):
    st.import_sessions([_month(["s1", "s2"], 300)])
    st.import_sessions([_month(["s1"], 100)])  # versión vieja del mismo resumen
    [month] = st.recent_sessions("p", "a")
    assert (month.duration_s, month.sessions_count, month.covers) == (
        300,
        2,
        ["s1", "s2"],
    )


def test_import_is_all_or_nothing(st):
    bad = {"id": "s2", "platform": "p"}  # le faltan campos
    with pytest.raises(ValueError):
        st.import_sessions([_session_dict(), bad])
    assert st.get_game("p", "a") is None


def test_history_rows_are_shown_but_not_counted(st):
    st.import_sessions(
        [
            _session_dict(id="l", kind="legacy", duration_s=1000, ended_at="x"),
            _session_dict(id="h", kind="history", duration_s=60, ended_at="x"),
        ]
    )
    assert st.total_seconds("p", "a") == 1000
    assert {s.kind for s in st.recent_sessions("p", "a")} == {"legacy", "history"}


def test_export_roundtrip(st, tmp_path):
    st.add_game("p", "a", "/a")
    _play(st, "p", "a", 60, "2026-11-01T10:00:00")
    other = Store(tmp_path / "other.db")
    other.import_sessions(st.export_sessions())
    other.import_sessions(st.export_sessions())
    assert other.total_seconds("p", "a") == 60


def test_opening_db_from_older_schema_adds_missing_columns(tmp_path):
    """DB creada antes de que `sessions` tuviera `covers`: se actualiza al abrirla."""
    path = tmp_path / "vieja.db"
    old = Store(path)
    old.add_game("p", "a", "/a")
    with old.conn:
        old.conn.execute("ALTER TABLE sessions DROP COLUMN covers")
    old.conn.close()

    st = Store(path)
    sid = st.start_session(st.get_game("p", "a").id, "pc1", pid=None)
    st.end_session(sid, 60)
    assert st.total_seconds("p", "a") == 60
    assert st.recent_sessions("p", "a")[0].covers == []
