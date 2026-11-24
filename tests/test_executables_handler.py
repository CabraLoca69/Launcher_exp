import os

from platform_adapters.executables_handler import (
    UnixExecutableDetector,
    WindowsExecutableDetector,
)


def test_windows_detects_by_extension():
    d = WindowsExecutableDetector()
    assert d.is_executable("C:/g/Game.EXE")
    assert d.is_executable("run.bat")
    assert not d.is_executable("readme.txt")


def test_unix_detects_by_exec_bit(tmp_path):
    f = tmp_path / "bin"
    f.write_text("")
    d = UnixExecutableDetector()
    assert not d.is_executable(str(f))
    os.chmod(f, 0o755)
    assert d.is_executable(str(f))
    assert not d.is_executable(str(tmp_path))  # un directorio no cuenta
