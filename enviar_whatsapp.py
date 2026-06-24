"""Envia resumo de precos via WhatsApp Web (pywhatkit)."""
import csv, os, glob, re, sys
from datetime import datetime

DESTINO = "+5511999490614"
SITE_SAMS = "Sam's Club"
MARCAS_ORDEM = ["Heineken", "Spaten", "Michelob", "Stella Artois Pure Gold"]


def preco_float(s):
    try:
        return float(str(s).replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def extrair_unidades(nome):
    m = re.search(r'(\d+)\s*[xX]\s*\d+\s*ml', nome)
    if m:
        return int(m.group(1))
    m = re.search(r'Pack\s+(\d+)\s+(?:Latas?|Garrafas?|Un\.)', nome, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 1


def carregar():
    arquivos = sorted(glob.glob(os.path.join("data", "precos_*.csv")))
    if not arquivos:
        print("Nenhum CSV encontrado.")
        sys.exit(1)
    caminho = arquivos[-1]
    data_str = os.path.basename(caminho).replace("precos_","").replace(".csv","")
    data = datetime.strptime(data_str, "%Y%m%d").strftime("%d/%m/%Y")
    with open(caminho, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    vistos = {}
    for r in rows:
        chave = (r["site"], r["produto"])
        if chave not in vistos or r["timestamp"] > vistos[chave]["timestamp"]:
            vistos[chave] = r
    return list(vistos.values()), data


def montar_mensagem(produtos, data):
    sites = sorted({p["site"] for p in produtos})
    marcas = sorted({p["marca_buscada"] for p in produtos},
                    key=lambda m: MARCAS_ORDEM.index(m) if m in MARCAS_ORDEM else 99)

    linhas = [f"Cervejas - {data}", ""]

    for marca in marcas:
        linhas.append(f"[{marca}]")
        itens = [p for p in produtos if p["marca_buscada"] == marca]

        # agrupar por produto
        nomes_por_site = {}
        for p in itens:
            nomes_por_site.setdefault(p["produto"], {})[p["site"]] = p["preco"]

        for nome, precos in sorted(nomes_por_site.items(),
                                   key=lambda x: (-len(x[1]),
                                                  preco_float(list(x[1].values())[0]))):
            partes = []
            for site in sites:
                if site not in precos:
                    continue
                preco_str = precos[site]
                if site == SITE_SAMS:
                    unid = extrair_unidades(nome)
                    if unid > 1:
                        pu = preco_float(preco_str) / unid
                        partes.append(f"Sams R${preco_str} (R${pu:.2f}/un)".replace(".", ","))
                    else:
                        partes.append(f"Sams R${preco_str}")
                else:
                    partes.append(f"{site.split()[0]} R${preco_str}")

            # nome abreviado: cortar em 45 chars
            nome_curto = nome if len(nome) <= 45 else nome[:42] + "..."
            linhas.append(f"  {nome_curto}")
            linhas.append(f"    {' | '.join(partes)}")

        linhas.append("")

    linhas.append("(cerveja_monitor)")
    return "\n".join(linhas)


def enviar(mensagem):
    try:
        import pywhatkit as kit
    except ImportError:
        print("pywhatkit nao instalado. Rode: pip install pywhatkit")
        sys.exit(1)

    print("Enviando WhatsApp...")
    print("--- mensagem ---")
    print(mensagem)
    print("----------------")

    # sendwhatmsg_instantly abre o WhatsApp Web e envia imediatamente
    # wait_time=15 da tempo para carregar; tab_close=True fecha a aba depois
    kit.sendwhatmsg_instantly(
        phone_no=DESTINO,
        message=mensagem,
        wait_time=20,
        tab_close=True,
        close_time=5,
    )
    print("Mensagem enviada.")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    produtos, data = carregar()
    msg = montar_mensagem(produtos, data)
    enviar(msg)
