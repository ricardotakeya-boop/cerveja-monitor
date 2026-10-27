"""
Orquestrador do monitor de cervejas v2.

    python executar_v2.py            # coleta, grava, gera HTML, commita e envia
    python executar_v2.py --sem-email
    python executar_v2.py --sem-git

O e-mail e enviado MESMO quando a coleta e parcial ou falha: nesse caso o
relatorio explica o que nao funcionou na secao "Limitacoes". Um dia sem
e-mail seria indistinguivel de um dia sem novidade.
"""

import argparse
import logging
import os
import smtplib
import subprocess
import sys
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

PROJETO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJETO)

import config_v2 as cfg          # noqa: E402
import coleta_v2                 # noqa: E402
import relatorio_v2              # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("executar")


def _git(*args):
    return subprocess.run(["git", *args], cwd=PROJETO,
                          capture_output=True, text=True)


def publicar_git():
    hoje = datetime.now().strftime("%d/%m/%Y")
    _git("add", cfg.HISTORICO_V2, cfg.RELATORIO_HTML)
    commit = _git("commit", "-m", f"relatorio cervejas v2 {hoje}")
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr):
        log.warning("commit: %s", (commit.stdout + commit.stderr).strip()[:300])
    push = _git("push")
    if push.returncode == 0:
        log.info("push concluido")
    else:
        log.warning("push falhou: %s", push.stderr.strip()[:300])


def enviar_email(html: str, texto: str, assunto: str):
    usuario = os.environ.get("GMAIL_USER")
    senha = os.environ.get("GMAIL_APP_PASSWORD")
    destino = os.environ.get("DESTINATARIO") or usuario

    if not (usuario and senha and destino):
        try:
            from email_config import GMAIL_USER, GMAIL_APP_PASSWORD, DESTINATARIO
            usuario = usuario or GMAIL_USER
            senha = senha or GMAIL_APP_PASSWORD
            destino = destino or DESTINATARIO
        except ImportError:
            log.error("Credenciais ausentes (env ou email_config.py); e-mail nao enviado.")
            return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = usuario
    msg["To"] = destino
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    # O Gmail as vezes derruba a conexao (SMTPServerDisconnected); tentamos
    # 465/SSL e, se falhar, 587/STARTTLS antes de desistir.
    for tentativa, abrir in enumerate(
        (lambda: smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60),
         lambda: smtplib.SMTP("smtp.gmail.com", 587, timeout=60)), 1
    ):
        try:
            with abrir() as smtp:
                if smtp.__class__ is smtplib.SMTP:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(usuario, senha)
                smtp.sendmail(usuario, [destino], msg.as_string())
            log.info("e-mail enviado para %s (tentativa %s)", destino, tentativa)
            return True
        except Exception as e:
            log.warning("envio falhou (tentativa %s): %s: %s", tentativa, type(e).__name__, e)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-email", action="store_true")
    ap.add_argument("--sem-git", action="store_true")
    args = ap.parse_args()

    os.chdir(PROJETO)
    agora = datetime.now()
    ofertas, falhas = [], {}

    try:
        ofertas, falhas = coleta_v2.coletar()
        if ofertas:
            coleta_v2.salvar(ofertas)
    except Exception as e:
        falhas["Coleta"] = f"{type(e).__name__}: {e}"
        log.error("coleta falhou: %s", traceback.format_exc()[:1000])

    log.info("%s ofertas | %s limitacao(oes)", len(ofertas), len(falhas))

    html = relatorio_v2.gerar_html(ofertas, falhas, agora)
    texto = relatorio_v2.resumo_texto(ofertas, falhas, agora)
    with open(cfg.RELATORIO_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("relatorio salvo em %s", cfg.RELATORIO_HTML)

    if not args.sem_git:
        publicar_git()

    if not args.sem_email:
        sufixo = "" if ofertas else " — sem dados"
        assunto = f"{cfg.ASSUNTO_PREFIXO} — {agora:%d/%m/%Y}{sufixo}"
        enviar_email(html, texto, assunto)

    # Falha de coleta e sinalizada ao GitHub Actions, mas so depois do e-mail.
    if not ofertas:
        log.error("nenhuma oferta coletada")
        sys.exit(1)


if __name__ == "__main__":
    main()
