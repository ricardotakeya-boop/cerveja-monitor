"""Gera relatorio.html, faz git push e envia por e-mail."""
import os, subprocess, sys, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

PROJETO = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    return subprocess.run(cmd, cwd=PROJETO, shell=True, capture_output=True, text=True)


def gerar():
    r = run(f'python "{os.path.join(PROJETO, "gerar_relatorio.py")}"')
    if r.returncode != 0:
        print("Erro ao gerar relatorio:", r.stderr)
        sys.exit(1)
    print(r.stdout.strip())


def publicar():
    hoje = datetime.now().strftime("%d/%m/%Y")
    run("git add relatorio.html data/")
    r = run(f'git commit -m "relatorio {hoje}"')
    print(r.stdout.strip() or r.stderr.strip())
    r = run("git push")
    if r.returncode != 0:
        print("Erro no push:", r.stderr)
        sys.exit(1)
    print("Push concluido.")


def enviar_email():
    from email_config import GMAIL_USER, GMAIL_APP_PASSWORD, DESTINATARIO

    hoje = datetime.now().strftime("%d/%m/%Y")
    html_path = os.path.join(PROJETO, "relatorio.html")
    with open(html_path, encoding="utf-8") as f:
        html_body = f.read()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Precos de cerveja - {hoje}"
    msg["From"] = GMAIL_USER
    msg["To"] = DESTINATARIO
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"Enviando e-mail para {DESTINATARIO}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, DESTINATARIO, msg.as_string())
    print("E-mail enviado.")


if __name__ == "__main__":
    os.chdir(PROJETO)
    gerar()
    publicar()
    enviar_email()
