import os
import platform
import subprocess
import shutil

# Configuración
SCRIPT_NAME = "launcher69.py"
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

    # Paths de íconos
    ICON_ICO = os.path.join("data", "icons", "icon.ico")
    ICON_PNG = os.path.join("data", "icons", "icon.png")

    if system == "Windows":
        output_name = f"{EXE_NAME}.exe"
        ICON_PATH = ICON_ICO
        ADD_DATA = f"{ICON_ICO};data/icons"
    else:
        output_name = EXE_NAME
        ICON_PATH = ICON_PNG
        ADD_DATA = f"{ICON_PNG}:data/icons"   # En Linux/Mac se usa ":" como separador

    run([
        "pyinstaller",
        "--onedir",
        "--noconsole",
        f"--icon={ICON_PATH}",
        "--hidden-import=PIL._tkinter_finder",
        "--add-data", ADD_DATA,

        SCRIPT_NAME
    ])

    clean()

    print(f"\n✅ Proceso terminado. El ejecutable está en dist/{output_name}")

if __name__ == "__main__":
    main()