"""
=============================================================
  RESERVA AUTOMÁTICA — Restaurante UPF
  Formulário: Reserva de refeição RU/Lab Nutrição UPF
=============================================================
  Campos mapeados (da foto do formulário):
    Página 1: Email institucional UPF
    Página 2:
      • Data da reserva   → data de HOJE automaticamente
      • Qual refeição?    → "Almoço", "Jantar" ou "Almoço e jantar"
      • Nome completo     → texto
      • Perfil do público → ex: "Aluno graduação UPF"
      • Número matrícula  → texto
=============================================================
"""

import json
import time
import logging
import smtplib
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

BASE_DIR    = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config" / "config.json"
# RU_LOG_DIR pode ser passado pelo app.py para garantir caminho consistente
LOG_DIR = Path(os.environ.get("RU_LOG_DIR", str(BASE_DIR / "logs")))
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"reserva_{date.today()}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScxJSGzH0D-t4UqvxDt1C07tytcSkptaCRWWr2y1d4weNhhuQ/viewform"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        log.error(f"Config não encontrado: {CONFIG_FILE}")
        log.info("Execute:  python setup_upf.py  para configurar.")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def send_email(config: dict, subject: str, body: str, success: bool):
    n = config.get("notificacao", {})
    if not n.get("ativo", False):
        return
    try:
        msg = MIMEMultipart("alternative")
        emoji = "✅" if success else "❌"
        msg["Subject"] = f"{emoji} {subject}"
        msg["From"]    = n["email_remetente"]
        msg["To"]      = n["email_destinatario"]
        html = f"""
        <html><body style="font-family:Arial,sans-serif;padding:20px;max-width:500px">
          <h2 style="color:{'#2e7d32' if success else '#c62828'}">{emoji} {subject}</h2>
          <pre style="background:#f5f5f5;padding:16px;border-radius:8px;font-size:14px;white-space:pre-wrap">{body}</pre>
          <p style="color:#999;font-size:12px">RU UPF • {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </body></html>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(n.get("smtp_host", "smtp.gmail.com"), n.get("smtp_port", 587)) as s:
            s.starttls()
            s.login(n["email_remetente"], n["senha_app"])
            s.sendmail(n["email_remetente"], n["email_destinatario"], msg.as_string())
        log.info(f"E-mail enviado → {n['email_destinatario']}")
    except Exception as e:
        log.error(f"Falha ao enviar e-mail: {e}")


def preencher_form(config: dict, perfil: dict, data_reserva: str) -> tuple[bool, str]:
    """
    Preenche o formulário usando a URL de pre-fill do Google Forms
    com os entry IDs mapeados diretamente — sem depender de XPath.

    IDs mapeados do formulário:
      entry.438994047  → data (ano/mês/dia em campos separados)
      entry.24359638   → qual refeição (radio)
      entry.1773563523 → nome completo
      entry.919059448  → perfil do público (radio)
      entry.1642444040 → número de matrícula
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        return False, "Rode: pip install --upgrade selenium"

    nome_perfil   = perfil["nome"]
    email_upf     = perfil["email"]
    senha_upf     = perfil.get("senha", "")
    nome_completo = perfil["nome_completo"]
    matricula     = perfil.get("matricula", "")
    perfil_pub    = perfil.get("perfil_publico", "Aluno graduação UPF")
    refeicao      = perfil.get("refeicao", "Almoço e jantar")
    headless      = config.get("headless", True)

    log.info(f"[{nome_perfil}] Iniciando → data: {data_reserva} | refeição: {refeicao}")

    # ── Montar URL de pre-fill com todos os campos já preenchidos ──
    from urllib.parse import quote
    d, m_str, ano = data_reserva.split("/")

    params = (
        f"entry.438994047_year={ano}"
        f"&entry.438994047_month={int(m_str)}"
        f"&entry.438994047_day={int(d)}"
        f"&entry.24359638={quote(refeicao)}"
        f"&entry.1773563523={quote(nome_completo)}"
        f"&entry.919059448={quote(perfil_pub)}"
        f"&entry.1642444040={quote(str(matricula))}"
    )
    url_prefill = f"{FORM_URL}?usp=pp_url&{params}"
    log.info(f"[{nome_perfil}] URL prefill montada.")

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,960")
    opts.add_argument("--lang=pt-BR")

    user_data = config.get("chrome_user_data_dir", "")
    if user_data:
        opts.add_argument(f"--user-data-dir={user_data}")
        opts.add_argument(f"--profile-directory={config.get('chrome_profile', 'Default')}")

    driver = None
    try:
        driver = webdriver.Chrome(options=opts)
        wait   = WebDriverWait(driver, 30)

        driver.get(url_prefill)
        time.sleep(3)

        # ── Login Google se necessário ─────────────────────────────
        current = driver.current_url.lower()
        page    = driver.page_source.lower()

        if "accounts.google.com" in current or "identifierid" in page:
            log.info(f"[{nome_perfil}] Login Google — inserindo e-mail...")
            try:
                campo_email = wait.until(EC.visibility_of_element_located(
                    (By.XPATH, "//input[@type='email'] | //input[@id='identifierId']")
                ))
                campo_email.clear()
                campo_email.send_keys(email_upf)
                time.sleep(0.5)
                btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//*[@id='identifierNext'] | //span[contains(text(),'Avançar') or contains(text(),'Next')]/..")
                ))
                btn.click()
                log.info(f"[{nome_perfil}] E-mail enviado. Aguardando redirecionamento...")
                # Aguarda sair da tela de login do Google
                wait.until(lambda d: "accounts.google.com" not in d.current_url.lower())
                time.sleep(2)
            except Exception as e:
                log.warning(f"[{nome_perfil}] Campo e-mail: {e}")

        # ── Página 1: preencher e-mail e clicar em Próxima ────────
        # O Forms abre na p1 com cardápio + campo e-mail obrigatório.
        # Após Próxima vai para p2 com os outros campos e botão Enviar.
        time.sleep(2)
        log.info(f"[{nome_perfil}] Página 1 — preenchendo e-mail e avançando...")
        try:
            campo_email_form = wait.until(EC.visibility_of_element_located(
                (By.XPATH, "//input[@type='email']")
            ))
            campo_email_form.clear()
            campo_email_form.send_keys(email_upf)
            log.info(f"[{nome_perfil}] E-mail preenchido: {email_upf} ✓")
            time.sleep(0.5)
        except Exception as e:
            log.warning(f"[{nome_perfil}] Campo e-mail do Forms: {e}")

        try:
            btn_prox = wait.until(EC.element_to_be_clickable(
                (By.XPATH,
                 "//div[@jsname='OCpkoe'] | "
                 "//div[@role='button'][.//span[contains(text(),'róxim') or contains(text(),'ext')]]")
            ))
            driver.execute_script("arguments[0].click();", btn_prox)
            log.info(f"[{nome_perfil}] Clicou em Próxima ✓")
            time.sleep(3)
        except Exception as e:
            log.warning(f"[{nome_perfil}] Botão Próxima: {e}")

        # ── SSO / senha institucional (só se aparecer) ─────────────
        time.sleep(2)
        current = driver.current_url.lower()
        page    = driver.page_source.lower()

        if "password" in page or "login.microsoftonline" in current or "upf.br/login" in current:
            if senha_upf:
                log.info(f"[{nome_perfil}] Tela de senha — inserindo...")
                try:
                    campo_senha = wait.until(EC.visibility_of_element_located(
                        (By.XPATH, "//input[@type='password']")
                    ))
                    campo_senha.send_keys(senha_upf)
                    time.sleep(0.5)
                    btn_login = wait.until(EC.element_to_be_clickable(
                        (By.XPATH,
                         "//input[@type='submit'] | //button[@type='submit'] | "
                         "//*[@id='idSIButton9'] | "
                         "//span[contains(text(),'Entrar') or contains(text(),'Sign in')]/..")
                    ))
                    btn_login.click()
                    log.info(f"[{nome_perfil}] Senha enviada. Aguardando formulário...")
                    time.sleep(6)
                except Exception as e:
                    log.warning(f"[{nome_perfil}] Campo senha: {e}")
            else:
                log.warning(f"[{nome_perfil}] Tela de senha detectada mas sem senha no config. Tentando continuar...")

        log.info(f"[{nome_perfil}] Formulário carregado. URL: {driver.current_url}")

        # ── Verificar se os campos foram preenchidos pelo prefill ──
        page_src = driver.page_source
        campos_ok = sum([
            nome_completo.lower() in page_src.lower(),
            str(matricula) in page_src,
            ano in page_src,
        ])
        log.info(f"[{nome_perfil}] Campos detectados na página: {campos_ok}/3")

        # ── Aguardar o botão Enviar estar clicável ─────────────────
        log.info(f"[{nome_perfil}] Aguardando botão Enviar ficar clicável...")
        try:
            btn_enviar = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@jsname='M2UYVd']")))
            log.info(f"[{nome_perfil}] Botão Enviar pronto ✓")
        except Exception as e:
            log.warning(f"[{nome_perfil}] Timeout aguardando botão: {e}")
            btn_enviar = None

        # ── Clicar em Enviar ───────────────────────────────────────
        log.info(f"[{nome_perfil}] Clicando em Enviar...")
        enviado = False

        if btn_enviar:
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", btn_enviar)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", btn_enviar)
                enviado = True
                log.info(f"[{nome_perfil}] Botão Enviar clicado via JS ✓")
            except Exception as e:
                log.warning(f"[{nome_perfil}] Clique falhou: {e}")

        if not enviado:
            try:
                botoes = driver.find_elements(By.XPATH, "//*[@role='button']")
                textos = [b.text.strip() for b in botoes if b.text.strip()]
                log.error(f"[{nome_perfil}] Botões na página: {textos}")
            except Exception:
                pass
            return False, f"[{nome_perfil}] Campos preenchidos mas botão Enviar não encontrado."

        # Aguarda URL mudar (sair da viewform) ou texto de confirmação aparecer
        log.info(f"[{nome_perfil}] Aguardando confirmação do Forms...")
        try:
            wait.until(lambda d:
                "formrestricted" in d.current_url.lower() or
                "viewform" not in d.current_url.lower() or
                any(c in d.page_source.lower() for c in ["sua resposta foi registrada", "response recorded", "obrigado"])
            )
        except Exception:
            time.sleep(5)  # fallback: espera 5s mesmo sem confirmar mudança de URL

        # ── Confirmação ────────────────────────────────────────────
        pf = driver.page_source.lower()
        confirmacoes = ["sua resposta foi registrada", "response recorded", "obrigado", "thank you", "foi enviado"]
        if any(c in pf for c in confirmacoes):
            hora_conf = datetime.now().strftime('%H:%M:%S')
            log.info(f"[{nome_perfil}] Reserva confirmada! Data:{data_reserva} Refeição:{refeicao} Matrícula:{matricula or '-'} Horário:{hora_conf}")
            msg = (
                f"Reserva confirmada!\n"
                f"   Perfil   : {nome_perfil} ({nome_completo})\n"
                f"   Data     : {data_reserva}\n"
                f"   Refeição : {refeicao}\n"
                f"   Matrícula: {matricula or '-'}\n"
                f"   Horário  : {hora_conf}"
            )
            return True, msg
        else:
            return False, (
                f"Formulário enviado para {nome_perfil}, "
                f"mas confirmação não detectada.\nURL: {driver.current_url}"
            )

    except Exception as e:
        log.exception(f"[{nome_perfil}] Erro inesperado: {e}")
        return False, f"Erro para {nome_perfil}: {e}"
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Reserva RU UPF")
    parser.add_argument("--perfil",       help="Nome do perfil (default: todos ativos)")
    parser.add_argument("--data",         help="Data DD/MM/AAAA (default: hoje)")
    parser.add_argument("--forcar",       action="store_true", help="Ignora limite de horário")
    parser.add_argument("--testar-email", action="store_true", help="Testa envio de e-mail")
    parser.add_argument("--ver-tela",     action="store_true", help="Chrome visível (debug)")
    args = parser.parse_args()

    config = load_config()

    if args.testar_email:
        send_email(config, "Teste RU UPF", "E-mail funcionando! ✅", True)
        print("E-mail de teste enviado!")
        return

    if args.ver_tela:
        config["headless"] = False

    hora_limite = config.get("hora_limite", "10:00")
    agora = datetime.now()
    h, m  = map(int, hora_limite.split(":"))
    limite = agora.replace(hour=h, minute=m, second=0, microsecond=0)
    if not args.forcar and agora > limite:
        msg = f"Executado às {agora.strftime('%H:%M')} — após o limite de {hora_limite}."
        log.warning(msg)
        send_email(config, "Reserva NÃO feita — fora do horário", msg, False)
        return

    data_reserva = args.data or date.today().strftime("%d/%m/%Y")
    log.info(f"Data da reserva: {data_reserva}")

    perfis = [p for p in config.get("perfis", []) if p.get("ativo", True)]
    if args.perfil:
        perfis = [p for p in perfis if p["nome"].lower() == args.perfil.lower()]
        if not perfis:
            log.error(f"Perfil '{args.perfil}' não encontrado.")
            sys.exit(1)
    if not perfis:
        log.error("Nenhum perfil ativo.")
        sys.exit(1)

    resultados = []
    tudo_ok = True
    for perfil in perfis:
        sucesso, msg = preencher_form(config, perfil, data_reserva)
        resultados.append(msg)
        if not sucesso:
            tudo_ok = False

    relatorio = "\n\n".join(resultados)
    titulo = "Reserva RU UPF realizada!" if tudo_ok else "Problema na reserva RU UPF"
    log.info(f"\n{'='*50}\n{titulo}\n{relatorio}\n{'='*50}")
    send_email(config, titulo, relatorio, tudo_ok)
    if not tudo_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
