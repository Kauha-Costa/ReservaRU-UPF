"""
=============================================================
  APP DESKTOP — Reserva RU UPF
  Roda um servidor local e abre no navegador automaticamente
  Uso: python app.py
=============================================================
"""

import json
import os
import sys
import threading
import webbrowser
import logging
from pathlib import Path
from datetime import date, datetime
from flask import Flask, jsonify, request, send_from_directory

# Quando rodando como .exe (PyInstaller), os arquivos bundled ficam em sys._MEIPASS
# mas config e logs precisam ficar ao lado do .exe para persistir entre execuções
if getattr(sys, "frozen", False):
    # Rodando como .exe
    BUNDLE_DIR = Path(sys._MEIPASS)          # arquivos bundled (app_ui, etc)
    BASE_DIR   = Path(sys.executable).parent # pasta onde o .exe está
else:
    BUNDLE_DIR = Path(__file__).parent
    BASE_DIR   = Path(__file__).parent

CONFIG_FILE = BASE_DIR / "config" / "config.json"
LOG_DIR     = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
(BASE_DIR / "config").mkdir(exist_ok=True)

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app = Flask(__name__, static_folder=str(BUNDLE_DIR / "app_ui"), static_url_path="")

REFEICOES       = ["Almoço e jantar", "Almoço", "Jantar"]
PERFIS_PUBLICOS = [
    "Aluno graduação UPF",
    "Aluno pós-graduação UPF",
    "Aluno Creati UPF",
    "Aluno Integrado UPF",
    "Professor ou Comunidade externa",
    "Funcionário UPF",
    "Residente multiprofissional",
    "Estudante rede municipal/estadual",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_config():
    if not CONFIG_FILE.exists():
        return {"perfis": [], "headless": True, "hora_limite": "10:00", "hora_execucao": "09:00"}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(c):
    CONFIG_FILE.parent.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)

def log_hoje():
    return LOG_DIR / f"reserva_{date.today()}.log"

def status_hoje(nome_perfil: str) -> dict:
    """Lê o log do dia e retorna se o perfil já teve reserva confirmada."""
    lf = log_hoje()
    if not lf.exists():
        return {"executado": False, "sucesso": None, "hora": None}
    linhas = lf.read_text(encoding="utf-8", errors="ignore").splitlines()
    for linha in reversed(linhas):
        if f"[{nome_perfil}]" not in linha:
            continue
        if "Reserva confirmada" in linha:
            hora = linha[:19] if len(linha) > 19 else ""
            return {"executado": True, "sucesso": True, "hora": hora}
        if "[ERROR]" in linha or "Erro inesperado" in linha:
            return {"executado": True, "sucesso": False, "hora": linha[:19]}
    return {"executado": False, "sucesso": None, "hora": None}

# ── Rotas API ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR / "app_ui"), "index.html")

@app.route("/api/config", methods=["GET"])
def get_config():
    c = load_config()
    return jsonify({
        "perfis": c.get("perfis", []),
        "headless": c.get("headless", True),
        "hora_limite": c.get("hora_limite", "10:00"),
        "hora_execucao": c.get("hora_execucao", "09:00"),
        "refeicoes": REFEICOES,
        "perfis_publicos": PERFIS_PUBLICOS,
    })

@app.route("/api/status", methods=["GET"])
def get_status():
    c = load_config()
    resultado = {}
    for p in c.get("perfis", []):
        resultado[p["nome"]] = status_hoje(p["nome"])
    return jsonify(resultado)

@app.route("/api/perfis", methods=["POST"])
def criar_perfil():
    c = load_config()
    dados = request.json
    novo = {
        "nome":          dados.get("nome", ""),
        "ativo":         True,
        "email":         dados.get("email", ""),
        "senha":         dados.get("senha", ""),
        "nome_completo": dados.get("nome_completo", ""),
        "matricula":     dados.get("matricula", ""),
        "perfil_publico": dados.get("perfil_publico", "Aluno graduação UPF"),
        "refeicao":      dados.get("refeicao", "Almoço e jantar"),
    }
    # Valida campos obrigatórios
    if not novo["nome"] or not novo["email"] or not novo["nome_completo"]:
        return jsonify({"erro": "Nome, e-mail e nome completo são obrigatórios."}), 400
    # Verifica duplicata
    if any(p["nome"].lower() == novo["nome"].lower() for p in c["perfis"]):
        return jsonify({"erro": f"Já existe um perfil com o nome '{novo['nome']}'."}), 400
    c["perfis"].append(novo)
    save_config(c)
    return jsonify({"ok": True, "perfil": novo})

@app.route("/api/perfis/<nome>", methods=["PUT"])
def editar_perfil(nome):
    c = load_config()
    dados = request.json
    for p in c["perfis"]:
        if p["nome"].lower() == nome.lower():
            for campo in ["email", "senha", "nome_completo", "matricula", "perfil_publico", "refeicao", "ativo"]:
                if campo in dados:
                    p[campo] = dados[campo]
            # Renomear
            if "nome" in dados and dados["nome"] != nome:
                if any(x["nome"].lower() == dados["nome"].lower() for x in c["perfis"] if x["nome"] != nome):
                    return jsonify({"erro": "Nome já em uso."}), 400
                p["nome"] = dados["nome"]
            save_config(c)
            return jsonify({"ok": True, "perfil": p})
    return jsonify({"erro": "Perfil não encontrado."}), 404

@app.route("/api/perfis/<nome>", methods=["DELETE"])
def deletar_perfil(nome):
    c = load_config()
    antes = len(c["perfis"])
    c["perfis"] = [p for p in c["perfis"] if p["nome"].lower() != nome.lower()]
    if len(c["perfis"]) == antes:
        return jsonify({"erro": "Perfil não encontrado."}), 404
    save_config(c)
    return jsonify({"ok": True})

@app.route("/api/ping", methods=["POST"])
def ping():
    global _ultimo_ping
    _ultimo_ping = _time.time()
    return jsonify({"ok": True})

# processo de reserva em background
_processos = {}

# ── Heartbeat: encerra o servidor quando o browser fechar ────────────────────
import time as _time
_ultimo_ping = _time.time()

def _watchdog():
    """Para o processo se não receber ping por 8 segundos."""
    while True:
        _time.sleep(3)
        if _time.time() - _ultimo_ping > 8:
            os.kill(os.getpid(), 9)

threading.Thread(target=_watchdog, daemon=True).start()

@app.route("/api/reservar", methods=["POST"])
def reservar():
    dados = request.json  # {perfis: [...], refeicao_override: "Almoço" | null, forcar: bool}
    perfis_sel   = dados.get("perfis", [])
    ref_override = dados.get("refeicao_override")  # se não nulo, sobrescreve a refeição
    forcar       = dados.get("forcar", True)

    if not perfis_sel:
        return jsonify({"erro": "Selecione ao menos um perfil."}), 400

    c = load_config()

    # Aplica override de refeição temporariamente se pedido
    if ref_override:
        for p in c["perfis"]:
            if p["nome"] in perfis_sel:
                p["refeicao"] = ref_override

    # Importa preencher_form diretamente (compativel com PyInstaller --onefile)
    os.environ["RU_LOG_DIR"] = str(LOG_DIR)
    if getattr(sys, "frozen", False):
        import importlib.util
        _spec = importlib.util.spec_from_file_location("reserva", str(BUNDLE_DIR / "reserva.py"))
        _mod  = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        preencher_form = _mod.preencher_form
    else:
        from reserva import preencher_form

    from datetime import date as _date
    data_reserva = _date.today().strftime("%d/%m/%Y")

    def rodar():
        from datetime import datetime as _dt
        hora_limite = c.get("hora_limite", "10:00")
        agora = _dt.now()
        h, m  = map(int, hora_limite.split(":"))
        limite = agora.replace(hour=h, minute=m, second=0, microsecond=0)

        for nome in perfis_sel:
            if not forcar and agora > limite:
                _processos[nome] = "erro"
                continue
            perfil_cfg = next((p for p in c["perfis"] if p["nome"] == nome), None)
            if not perfil_cfg:
                _processos[nome] = "erro"
                continue
            _processos[nome] = "rodando"
            try:
                sucesso, _ = preencher_form(c, perfil_cfg, data_reserva)
                _processos[nome] = "ok" if sucesso else "erro"
            except SystemExit:
                _processos[nome] = "erro"
            except Exception as e:
                _processos[nome] = f"erro: {e}"

    t = threading.Thread(target=rodar, daemon=True)
    t.start()
    return jsonify({"ok": True, "mensagem": f"Reserva iniciada para: {', '.join(perfis_sel)}"})

@app.route("/api/processos", methods=["GET"])
def get_processos():
    return jsonify(_processos)

@app.route("/api/log", methods=["GET"])
def get_log():
    lf = log_hoje()
    if not lf.exists():
        return jsonify({"linhas": []})
    linhas = lf.read_text(encoding="utf-8", errors="ignore").splitlines()
    return jsonify({"linhas": linhas[-100:]})  # últimas 100 linhas

# ── Main ──────────────────────────────────────────────────────────────────────

def abrir_browser():
    import time
    time.sleep(1.2)
    webbrowser.open("http://localhost:5757")

if __name__ == "__main__":
    import os
    log_app = LOG_DIR / "app.log"
    sys.stdout = open(log_app, "a", encoding="utf-8")
    sys.stderr = sys.stdout
    threading.Thread(target=abrir_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=5757, debug=False, use_reloader=False)
