"""Gera relatorio.html, faz git push e envia link via WhatsApp."""
import os, subprocess, sys
from datetime import datetime

PROJETO = os.path.dirname(os.path.abspath(__file__))
URL_PAGES = "https://ricardotakeya-boop.github.io/cerveja-monitor/relatorio.html"
DESTINO_WA = "+5511999490614"


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=PROJETO, shell=True, capture_output=True, text=True, **kw)


def gerar():
    r = run(f'python "{os.path.join(PROJETO, "gerar_relatorio.py")}"')
    if r.returncode != 0:
        print("Erro ao gerar relatorio:", r.stderr)
        sys.exit(1)
    print(r.stdout.strip())


def publicar():
    hoje = datetime.now().strftime("%d/%m/%Y")
    run('git add relatorio.html data/')
    r = run(f'git commit -m "relatorio {hoje}"')
    print(r.stdout.strip() or r.stderr.strip())
    r = run('git push')
    if r.returncode != 0:
        print("Erro no push:", r.stderr)
        sys.exit(1)
    print("Push concluido.")


def enviar_whatsapp():
    try:
        import pywhatkit as kit
    except ImportError:
        print("pywhatkit nao instalado. Rode: pip install pywhatkit")
        sys.exit(1)

    hoje = datetime.now().strftime("%d/%m/%Y")
    msg = f"Precos de cerveja - {hoje}\n{URL_PAGES}"
    print(f"Enviando WhatsApp para {DESTINO_WA}...")
    kit.sendwhatmsg_instantly(
        phone_no=DESTINO_WA,
        message=msg,
        wait_time=20,
        tab_close=True,
        close_time=5,
    )
    print("WhatsApp enviado.")


if __name__ == "__main__":
    os.chdir(PROJETO)
    gerar()
    publicar()
    enviar_whatsapp()
