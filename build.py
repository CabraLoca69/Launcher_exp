import os
import sys
import platform
import subprocess
import shutil

# Configuración
SCRIPT_NAME = "launcher69.py"
ICON_PATH = os.path.join("data", "icons", "icon.ico")
EXE_NAME = "Launcher69"

def run(cmd):
    print(">>>", " ".join(cmd))
    subprocess.check_call(cmd)

def clean():
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("launcher69.spec"):
        os.remove("launcher69.spec")

def main():
    system = platform.system()

    if system == "Windows":
        output_name = f"{EXE_NAME}.exe"
    else:
        output_name = EXE_NAME  # En Linux/Mac no hay .exe

    run([
        "pyinstaller",
        "--onefile",
        f"--icon={ICON_PATH}",
        "--noconsole",
        "--hidden-import=PIL._tkinter_finder",
        SCRIPT_NAME
    ])

    clean()

    print(f"\n✅ Proceso terminado. El ejecutable está en dist/{output_name}")

if __name__ == "__main__":
    main()
