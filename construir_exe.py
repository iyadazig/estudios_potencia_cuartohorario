r"""
Genera dist\EstudioPotencia.exe con las credenciales de Gemweb de GE&PE incluidas, para que
los compañeros no tengan que introducirlas.

Uso (desde la carpeta del proyecto, con el entorno limpio de compilación):
    .venv_exe\Scripts\python construir_exe.py [ruta\secrets.toml]

Las credenciales se buscan, por este orden, en:
    1. la ruta indicada como argumento;
    2. credenciales_gemweb.toml en la carpeta del proyecto;
    3. ..\API_Gemweb\.streamlit\secrets.toml (proyecto API_Gemweb).
(formato: GEMWEB_CLIENT_ID = "..." y GEMWEB_CLIENT_SECRET = "...")

Las credenciales NUNCA pasan por git: se escriben ofuscadas en potencia\_credenciales_incluidas.py
(excluido en .gitignore; el script se niega a seguir si no lo estuviera) y ese módulo se borra, junto con
la carpeta build y sus restos compilados, en cuanto termina la compilación.
"""

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MODULO = RAIZ / "potencia" / "_credenciales_incluidas.py"


def buscar_credenciales(argumento=None):
    candidatos = [Path(argumento)] if argumento else []
    candidatos += [RAIZ / "credenciales_gemweb.toml", RAIZ.parent / "API_Gemweb" / ".streamlit" / "secrets.toml"]
    return next((c for c in candidatos if c.exists()), None)


def limpiar():
    MODULO.unlink(missing_ok=True)
    for pyc in (RAIZ / "potencia" / "__pycache__").glob("_credenciales_incluidas*"):
        pyc.unlink(missing_ok=True)
    shutil.rmtree(RAIZ / "build", ignore_errors=True)


def main():
    sys.path.insert(0, str(RAIZ))
    from potencia import gemweb

    # 1. el módulo con las credenciales tiene que estar excluido de git
    if subprocess.run(["git", "check-ignore", "-q", str(MODULO)], cwd=RAIZ).returncode != 0:
        sys.exit("ALTO: potencia/_credenciales_incluidas.py no está en .gitignore. No se incluyen las credenciales.")

    # 2. credenciales
    ruta = buscar_credenciales(sys.argv[1] if len(sys.argv) > 1 else None)
    credenciales = None
    if ruta is None:
        print("AVISO: no se han encontrado credenciales de Gemweb; el ejecutable pedirá las suyas a cada usuario.")
    else:
        credenciales = gemweb.leer_secrets_toml(ruta)
        gemweb.ClienteGemweb(*credenciales).comprobar()
        print(f"Credenciales de Gemweb leídas de {ruta} y comprobadas (no se muestran).")

    # 3. compilación
    try:
        if credenciales:
            MODULO.write_text(gemweb.ofuscar(*credenciales), encoding="utf-8")
        shutil.rmtree(RAIZ / "dist", ignore_errors=True)
        subprocess.run([sys.executable, "-m", "PyInstaller", "EstudioPotencia.spec", "--noconfirm",
                        "--log-level", "WARN"], cwd=RAIZ, check=True)
    finally:
        limpiar()

    # 4. ficheros junto al ejecutable
    dist = RAIZ / "dist"
    (dist / "config").mkdir(exist_ok=True)
    shutil.copy(RAIZ / "config" / "precios.json", dist / "config" / "precios.json")
    shutil.copy(RAIZ / "LEEME_exe.txt", dist / "LEEME.txt")

    # 5. comprobaciones
    exe = dist / "EstudioPotencia.exe"
    if credenciales and credenciales[1].encode() in exe.read_bytes():
        sys.exit("ALTO: la clave aparece en texto plano dentro del ejecutable.")
    if subprocess.run(["git", "status", "--porcelain", "--ignored=no"], cwd=RAIZ, capture_output=True,
                      text=True).stdout.count("_credenciales_incluidas"):
        sys.exit("ALTO: git ve el módulo de credenciales.")
    print(f"Listo: {exe} ({exe.stat().st_size / 1e6:.0f} MB)"
          + (" con las credenciales de Gemweb incluidas." if credenciales else " sin credenciales incluidas."))


if __name__ == "__main__":
    main()
