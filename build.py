import os
import platform
import subprocess
import shutil

# Configuración
SCRIPT_NAME = "launcher69.py"
EXE_NAME = "Launcher69"
DIST_DIR = os.path.join("dist", EXE_NAME)

def run(cmd):
    print(">>>", " ".join(cmd))
    subprocess.check_call(cmd)

def copy_app_data():
    """Íconos y temas van al lado del ejecutable: la app los lee de data/ junto a él.
    Los datos del usuario (databases/, cloud_files/) no se tocan."""
    for folder in ("icons", "themes"):
        target = os.path.join(DIST_DIR, "data", folder)
        shutil.copytree(os.path.join("data", folder), target, dirs_exist_ok=True)


def clean():
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists(f"{EXE_NAME}.spec"):
        os.remove(f"{EXE_NAME}.spec")

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
        "--noconfirm",
        f"--name={EXE_NAME}",
        f"--icon={ICON_PATH}",
        "--add-data", ADD_DATA,

        SCRIPT_NAME
    ])

    copy_app_data()
    clean()

    print(f"\n✅ Proceso terminado. El ejecutable está en {DIST_DIR}/{output_name}")

if __name__ == "__main__":
    main()