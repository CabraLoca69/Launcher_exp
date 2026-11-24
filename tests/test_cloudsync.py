from data_access import cloudsync
from data_access.machine_id import get_machine_id


def test_flatten_config_excludes_global():
    nested = {
        "global": {"email": "x"},
        "steam": {"game_list": {"a": "/a"}, "favorites": ["a"]},
    }
    assert cloudsync.flatten_config(nested) == {
        "steam.game_list.a": "/a",
        "steam.favorites": ["a"],
    }


def test_rebuild_is_inverse_of_flatten():
    nested = {"steam": {"game_total_times": {"a": {"pc1": 10.0}}, "favorites": ["a"]}}
    assert cloudsync.rebuild_nested_config(cloudsync.flatten_config(nested)) == nested


def test_merge_keeps_max_per_pc():
    local = {"steam": {"game_total_times": {"a": {"pc1": 50.0, "pc2": 5.0}}}}
    cloud = {"pc_ids": {"pc1": {"steam": {"a": 30.0}}, "pc2": {"steam": {"a": 20.0}}}}
    merged = cloudsync.merge_backup_data(local, cloud)
    assert merged["steam"]["game_total_times"]["a"] == {"pc1": 50.0, "pc2": 20.0}


def test_merge_adds_games_and_platforms_from_cloud():
    cloud = {"pc_ids": {"pc9": {"gog": {"b": 7}}}}
    merged = cloudsync.merge_backup_data({}, cloud)
    assert merged == {"gog": {"game_total_times": {"b": {"pc9": 7.0}}}}


def test_merge_ignores_internal_roots():
    cloud = {"pc_ids": {"pc1": {"global": {"a": 1}, "settings.x": {"a": 1}}}}
    assert cloudsync.merge_backup_data({}, cloud) == {}


def test_merge_does_not_mutate_local():
    local = {"steam": {"game_total_times": {"a": {"pc1": 1.0}}}}
    cloudsync.merge_backup_data(local, {"pc_ids": {"pc2": {"steam": {"a": 9}}}})
    assert local == {"steam": {"game_total_times": {"a": {"pc1": 1.0}}}}


def test_merge_wraps_legacy_float_totals():
    local = {"steam": {"game_total_times": {"a": 12.0}}}
    merged = cloudsync.merge_backup_data(
        local, {"pc_ids": {"pc1": {"steam": {"a": 3}}}}
    )
    assert merged["steam"]["game_total_times"]["a"] == {"__legacy": 12.0, "pc1": 3.0}


def test_payload_contains_only_this_pc_totals(clean_db):
    pc = get_machine_id()
    clean_db.set(f"steam.game_total_times.a.{pc}", 42.0)
    clean_db.set("steam.game_total_times.a.otra_pc", 99.0)
    clean_db.set("global.email", "x@y")

    payload = cloudsync.build_cloud_payload_for_upload(
        {"pc_ids": {"otra_pc": {"steam": {"a": 99.0}}}}
    )

    assert payload["pc_ids"][pc] == {"steam": {"a": 42.0}}
    assert payload["pc_ids"]["otra_pc"] == {"steam": {"a": 99.0}}
