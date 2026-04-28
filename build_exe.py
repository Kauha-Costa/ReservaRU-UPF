"""
build_exe.py — Gera ReservaRU.exe com PyInstaller
Uso: python build_exe.py
Requer: pip install pyinstaller
"""
import subprocess, sys, shutil
from pathlib import Path

DIR = Path(__file__).parent

def main():
    # Instala PyInstaller se necessário
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller", "flask", "selenium"],
                   check=True)

    # Limpa builds anteriores
    for p in ["build", "dist"]:
        shutil.rmtree(DIR / p, ignore_errors=True)

    SEP = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                        # tudo em 1 exe
        "--windowed",                       # sem janela de CMD
        "--name", "ReservaRU",
        "--icon", str(DIR / "icone.ico"),
        "--add-data", f"{DIR / 'app_ui'}{SEP}app_ui",
        "--add-data", f"{DIR / 'config' / 'config.exemplo.json'}{SEP}config",
        "--add-data", f"{DIR / 'reserva.py'}{SEP}.",
        "--add-data", f"{DIR / 'perfis.py'}{SEP}.",
        "--hidden-import", "flask",
        "--hidden-import", "werkzeug",
        "--hidden-import", "jinja2",
        "--hidden-import", "click",
        "--hidden-import", "selenium",
        "--hidden-import", "selenium.webdriver",
        "--hidden-import", "selenium.webdriver.chrome",
        "--hidden-import", "selenium.webdriver.chrome.webdriver",
        "--hidden-import", "selenium.webdriver.chrome.options",
        "--hidden-import", "selenium.webdriver.chrome.service",
        "--hidden-import", "selenium.webdriver.common.by",
        "--hidden-import", "selenium.webdriver.common.keys",
        "--hidden-import", "selenium.webdriver.common.action_chains",
        "--hidden-import", "selenium.webdriver.support",
        "--hidden-import", "selenium.webdriver.support.ui",
        "--hidden-import", "selenium.webdriver.support.expected_conditions",
        str(DIR / "app.py"),
    ]

    result = subprocess.run(cmd, cwd=str(DIR))

    if result.returncode == 0:
        exe = DIR / "dist" / "ReservaRU.exe"
        dest = DIR / "ReservaRU.exe"
        shutil.copy(exe, dest)
        print(f"\n✅ Gerado: {dest}")
        print("   Distribua apenas o ReservaRU.exe — não precisa de Python instalado.")
    else:
        print("\n❌ Build falhou. Verifique os erros acima.")

if __name__ == "__main__":
    main()
