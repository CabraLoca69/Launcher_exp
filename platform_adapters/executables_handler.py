import os

class ExecutableDetector:
    def is_executable(self, path: str) -> bool:
        raise NotImplementedError


class WindowsExecutableDetector(ExecutableDetector):
    def is_executable(self, path):
        return os.path.splitext(path)[1].lower() in [".exe", ".bat", ".cmd"]


class UnixExecutableDetector(ExecutableDetector):
    def is_executable(self, path):
        return os.path.isfile(path) and os.access(path, os.X_OK)