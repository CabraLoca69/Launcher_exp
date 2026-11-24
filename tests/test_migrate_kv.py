import json
import sqlite3

import pytest

from data_access.migrate_kv import migrate
from data_access.store import Store, summary_id

PC = "pc-local"


def _kv_db(path, data):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany(
        "INSERT INTO config VALUES (?, ?)",
        [(k, json.dumps(v)) for k, v in data.items()],
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def migrated(tmp_path):
    config = _kv_db(
        tmp_path / "config.db",
        {
            "global.tab_order": ["steam", "gog"],
            "global.email": "yo@x.com",
            "global.cloud_sync_enabled": True,
            "global.allow_multiple_games": False,
            "global.last_selected_tab": "steam",  # solo lo usaba Tk: no se migra
            "global.actual_running.Hollow": {"pid": 1},  # estado efímero: no se migra
            "global.steam_ids.Hollow": 367520,
            "steam.platform_folders": ["/steam"],
            "steam.favorites": ["Hollow"],
            "steam.game_list.Hollow": "/steam/Hollow.exe",
            "steam.game_list.Game.v2": "/steam/Game.v2.exe",
            "gog.game_list.Hollow": "/gog/Hollow.exe",
            "steam.game_times.Hollow": [
                {"Start": "2026-11-01 20:00:00", "Tiempo": 30},
                {"Start": "2026-11-02 20:00:00", "Tiempo": 15.5},
            ],
            f"steam.game_total_times.Hollow.{PC}": 100.0,  # minutos, incluye las 2 recientes
            "steam.game_total_times.Hollow.otra-pc": 20.0,
            f"steam.game_total_times.Game.v2.{PC}": 5.0,
            "epic.game_total_times.Viejo.otra-pc": 7.0,  # juego que ya no está en la lista
            "epic.game_total_times.Antiguo": 3.0,  # formato muy viejo: total sin PC
            "epic.game_total_times.Roto.pc": "no-es-un-numero",
            "epic.game_list.SinRuta": None,
        },
    )
    notes = _kv_db(tmp_path / "notas.db", {"Hollow": "falta el jefe"})
    st = Store(tmp_path / "new.db")
    migrate(config, notes, st, PC)
    return st


def test_platforms_folders_and_settings(migrated):
    assert migrated.list_platforms() == ["steam", "gog"]
    assert migrated.list_folders("steam") == ["/steam"]
    assert migrated.get_setting("email") == "yo@x.com"
    assert migrated.get_setting("cloud_sync_enabled") is True
    assert migrated.get_setting("allow_multiple_games") is False
    assert migrated.get_setting("last_selected_tab") is None


def test_games_with_favorites_steam_id_and_notes(migrated):
    hollow = migrated.get_game("steam", "Hollow")
    assert (hollow.path, hollow.favorite, hollow.steam_appid, hollow.notes) == (
        "/steam/Hollow.exe",
        True,
        "367520",
        "falta el jefe",
    )
    assert migrated.get_game("steam", "Game.v2").path == "/steam/Game.v2.exe"
    assert migrated.get_game("gog", "Hollow").favorite is False


def test_playtime_is_preserved_without_double_counting(migrated):
    # 100 min locales (que ya incluyen las 2 recientes) + 20 min de otra PC
    assert migrated.total_seconds("steam", "Hollow") == (100 + 20) * 60
    kinds = sorted(s.kind for s in migrated.recent_sessions("steam", "Hollow"))
    assert kinds == ["history", "history", "legacy", "legacy"]
    assert migrated.total_seconds("steam", "Game.v2") == 5 * 60


def test_totals_of_unlisted_games_survive_as_hidden(migrated):
    viejo = migrated.get_game("epic", "Viejo")
    assert viejo.hidden is True
    assert migrated.total_seconds("epic", "Viejo") == 7 * 60


def test_no_running_sessions_after_migration(migrated):
    assert migrated.open_sessions() == []


def test_legacy_ids_match_cloud_v1_ids(migrated):
    ids = {
        s.id for s in migrated.recent_sessions("steam", "Hollow") if s.kind == "legacy"
    }
    assert summary_id("legacy", "otra-pc", "steam", "Hollow") in ids


def test_migration_is_idempotent(tmp_path, migrated):
    # Repetirla (ej. si se cortó a la mitad) no duplica horas
    config, notes = tmp_path / "config.db", tmp_path / "notas.db"
    migrate(config, notes, migrated, PC)
    assert migrated.total_seconds("steam", "Hollow") == (100 + 20) * 60


def test_totals_without_pc_are_kept(migrated):
    assert migrated.total_seconds("epic", "Antiguo") == 3 * 60


def test_corrupt_values_are_skipped(migrated):
    assert migrated.total_seconds("epic", "Roto") == 0
    assert migrated.get_game("epic", "SinRuta") is None


def test_two_pcs_migrating_and_merging_keep_the_real_total(tmp_path):
    """Cada PC tiene en su DB vieja el total de la otra (por sync). Al mezclar, no se duplica nada."""
    recent = [{"Start": f"2026-11-0{d} 20:00:00", "Tiempo": 10} for d in range(1, 6)]
    stores = {}
    for me, other in [("A", "B"), ("B", "A")]:
        data = {
            "steam.game_list.g": "/g",
            f"steam.game_total_times.g.{me}": 600.0 if me == "A" else 100.0,
            f"steam.game_total_times.g.{other}": 600.0 if other == "A" else 100.0,
        }
        if me == "A":
            data["steam.game_times.g"] = recent
        config = _kv_db(tmp_path / f"{me}.db", data)
        stores[me] = Store(tmp_path / f"{me}-new.db")
        migrate(config, tmp_path / "no-existe.db", stores[me], me)

    a, b = stores["A"], stores["B"]
    a.import_sessions(b.export_sessions())
    b.import_sessions(a.export_sessions())
    assert a.total_seconds("steam", "g") == b.total_seconds("steam", "g") == 700 * 60


def test_failed_migration_leaves_nothing(tmp_path, monkeypatch):
    config = _kv_db(
        tmp_path / "c.db", {"global.tab_order": ["steam"], "steam.game_list.a": "/a"}
    )
    st = Store(tmp_path / "n.db")
    monkeypatch.setattr(
        st, "import_sessions", lambda rows: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(RuntimeError):
        migrate(config, tmp_path / "x.db", st, PC)
    assert st.list_platforms() == []
