from data_access import machine_id


def test_machine_id_is_stable_even_if_file_fails(monkeypatch, tmp_path):
    class Broken:
        def exists(self):
            raise OSError("disco roto")

    monkeypatch.setattr(machine_id, "MACHINE_ID_FILE", Broken())
    monkeypatch.setattr(machine_id, "_cached", None)
    assert machine_id.get_machine_id() == machine_id.get_machine_id()


def test_machine_id_is_persisted(monkeypatch, tmp_path):
    monkeypatch.setattr(machine_id, "MACHINE_ID_FILE", tmp_path / "id.txt")
    monkeypatch.setattr(machine_id, "_cached", None)
    first = machine_id.get_machine_id()
    monkeypatch.setattr(machine_id, "_cached", None)
    assert machine_id.get_machine_id() == first == (tmp_path / "id.txt").read_text()
