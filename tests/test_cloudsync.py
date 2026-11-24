from data_access import cloudsync
from data_access.store import summary_id


def test_v2_payload_roundtrip():
    sessions = [{"id": "s1", "platform": "p", "game": "a"}]
    assert (
        cloudsync.sessions_from_payload(cloudsync.build_payload(sessions)) == sessions
    )


def test_v1_payload_becomes_legacy_rows():
    cloud = {
        "pc_ids": {
            "pc1": {"steam": {"a": 10}},
            "pc2": {"steam": {"a": 30, "b": 1.5}, "global": {"x": 1}},
        }
    }
    rows = cloudsync.sessions_from_payload(cloud)
    assert {(r["machine_id"], r["game"], r["duration_s"]) for r in rows} == {
        ("pc1", "a", 600),
        ("pc2", "a", 1800),
        ("pc2", "b", 90),
    }
    assert {r["kind"] for r in rows} == {"legacy"}
    assert summary_id("legacy", "pc2", "steam", "a") in {r["id"] for r in rows}


def test_empty_or_unknown_payload_has_no_sessions():
    assert cloudsync.sessions_from_payload({}) == []
