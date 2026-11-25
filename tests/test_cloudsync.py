import json
from types import SimpleNamespace

import pytest

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


def test_payload_without_version_or_sessions_is_empty():
    assert cloudsync.sessions_from_payload({}) == []


def test_unknown_payload_version_is_rejected():
    """Un backup de un launcher más nuevo no se lee como vacío (y no se pisa)."""
    with pytest.raises(ValueError):
        cloudsync.sessions_from_payload({"version": 3, "sessions": []})


class FakeDrive:
    """Drive falso con un único backup en memoria."""

    def __init__(self, content: bytes | None):
        self.content = content
        self.uploads = 0

    def files(self):
        return self

    def list(self, q, fields):
        has_file = "mimeType" in q or self.content is not None
        return SimpleNamespace(
            execute=lambda: {"files": [{"id": "x"}] if has_file else []}
        )

    def get_media(self, fileId):
        return self.content

    def update(self, **_):
        self.uploads += 1
        return SimpleNamespace(execute=lambda: None)

    create = update


@pytest.fixture
def drive(monkeypatch):
    def install(content):
        service = FakeDrive(content)
        monkeypatch.setattr(cloudsync, "get_drive_service", lambda: service)

        class Downloader:
            def __init__(self, fh, request):
                fh.write(request)

            def next_chunk(self):
                return None, True

        monkeypatch.setattr(cloudsync, "MediaIoBaseDownload", Downloader)
        monkeypatch.setattr(cloudsync, "MediaFileUpload", lambda *a, **k: None)
        return service

    return install


def test_corrupt_backup_is_not_overwritten(drive):
    service = drive(b'{"version": 2, "sess')  # JSON cortado
    with pytest.raises(ValueError):
        cloudsync.sync_once(upload=True)
    assert service.uploads == 0


def test_sync_merges_cloud_and_uploads(drive, store):
    store.add_game("p", "a", "/a")
    sid = store.start_session(store.get_game("p", "a").id, "pc1", pid=None)
    store.end_session(sid, 60)
    remote = dict(store.export_sessions()[0], id="remota", machine_id="pc2")
    service = drive(json.dumps(cloudsync.build_payload([remote])).encode())

    cloudsync.sync_once(upload=True)

    assert service.uploads == 1
    assert store.total_seconds("p", "a") == 120


def test_background_sync_never_opens_the_browser(monkeypatch, tmp_path):
    """Sin token válido, un hilo de fondo falla en vez de abrir el login."""
    monkeypatch.setattr(cloudsync, "TOKEN_PATH", tmp_path / "no-existe.json")

    def browser(*_):
        raise AssertionError("abrió el navegador")

    monkeypatch.setattr(cloudsync.InstalledAppFlow, "from_client_secrets_file", browser)
    with pytest.raises(RuntimeError):
        cloudsync.get_drive_service()
