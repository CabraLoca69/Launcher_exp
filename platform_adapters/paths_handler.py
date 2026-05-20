import os
import subprocess
import sys
import shutil

class PathWalker():
    def goto_folder(self, path):
        raise NotImplementedError

#____________WINDOWS______________
class WindowsGoToFolder(PathWalker):
    def goto_folder(self, path):
        os.startfile(path)

#__________LINUX__________
class LinuxGoToFolder(PathWalker):
    def goto_folder(self, path):
        subprocess.Popen(["xdg-open", os.path.dirname(path)])


