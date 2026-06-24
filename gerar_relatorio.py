"""Lê o CSV diário mais recente e gera relatorio.html."""
import csv, os, glob, re
from datetime import datetime

SITE_SAMS = "Sam's Club"


def carregar_ultima_varredura():
    arquivos = sorted(glob.glob(os.path.join("data", "precos_*.csv")))
    if not arquivos:
        raise FileNotFoundError("Nenhum CSV encontrado em data/")
    caminho = arquivos[-1]
    data = datetime.strptime(os.path.basename(caminho).replace("precos_","").replace(".csv",""), "%Y%m%d")
    with open(caminho, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    vistos = {}
    for r in rows:
        chave = (r["site"], r["produto"])
        if chave not in vistos or r["timestamp"] > vistos[chave]["timestamp"]:
            vistos[chave] = r
    return list(vistos.values()), data


def preco_float(s):
    try:
        return float(str(s).replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def extrair_unidades(nome):
    """Retorna a quantidade de unidades indicada no nome do produto."""
    # "6x250ml", "6x330ml", "12x350ml"
    m = re.search(r'(\d+)\s*[xX]\s*\d+\s*ml', nome)
    if m:
        return int(m.group(1))
    # "Pack 8 Latas", "Pack 12 Latas", "Pack 6 Garrafas", "Pack 12 Un."
    m = re.search(r'Pack\s+(\d+)\s+(?:Latas?|Garrafas?|Un\.)', nome, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 1


def preco_unitario_str(preco_str, unidades):
    """Retorna o preço por unidade formatado, ou None se já for unitário."""
    if unidades <= 1:
        return None
    val = preco_float(preco_str)
    if val == 0:
        return None
    return f"{val / unidades:.2f}".replace(".", ",")


def gerar_html(produtos, data):
    sites = sorted({p["site"] for p in produtos})
    marcas_ordem = ["Heineken", "Spaten", "Michelob", "Stella Artois Pure Gold"]
    marcas = sorted({p["marca_buscada"] for p in produtos},
                    key=lambda m: marcas_ordem.index(m) if m in marcas_ordem else 99)

    data_fmt = data.strftime("%d/%m/%Y")

    # ── cabeçalhos: para Sam's Club, insere coluna extra "/un" logo ao lado ──
    th_cells = []
    for s in sites:
        th_cells.append(
            f'<th style="padding:10px 16px;text-align:center;font-size:12px;font-weight:500;'
            f'color:#a07840;border-bottom:2px solid #2e2410;white-space:nowrap">{s}</th>'
        )
        if s == SITE_SAMS:
            th_cells.append(
                '<th style="padding:10px 12px;text-align:center;font-size:11px;font-weight:400;'
                'color:#6a4e28;border-bottom:2px solid #2e2410;white-space:nowrap'
                ';border-left:1px dashed #2e2410">Sams/un</th>'
            )
    th_sites = "".join(th_cells)

    # ── Uma seção por marca ──────────────────────────────────────────────────
    def secao(marca):
        itens_marca = [p for p in produtos if p["marca_buscada"] == marca]

        nomes_por_site = {}
        for p in itens_marca:
            nomes_por_site.setdefault(p["produto"], {})[p["site"]] = p["preco"]

        nomes_ord = sorted(
            nomes_por_site.keys(),
            key=lambda n: (-len(nomes_por_site[n]), preco_float(list(nomes_por_site[n].values())[0]))
        )

        linhas = ""
        for nome in nomes_ord:
            precos_site = nomes_por_site[nome]
            url_map = {p["site"]: p["url"] for p in itens_marca if p["produto"] == nome}
            cels = ""
            for site in sites:
                if site in precos_site:
                    url = url_map.get(site, "")
                    link_open  = f'<a href="{url}" target="_blank" style="color:inherit;text-decoration:none">' if url else ""
                    link_close = "</a>" if url else ""
                    preco_str = precos_site[site]
                    cels += (
                        f'<td style="padding:9px 16px;text-align:center;border-bottom:1px solid #2e2410;'
                        f'font-weight:600;color:#f5a623;white-space:nowrap">'
                        f'{link_open}R$ {preco_str}{link_close}</td>'
                    )
                    # coluna extra /un para Sam's Club
                    if site == SITE_SAMS:
                        unid = extrair_unidades(nome)
                        pu = preco_unitario_str(preco_str, unid)
                        if pu:
                            cels += (
                                f'<td style="padding:9px 10px;text-align:center;border-bottom:1px solid #2e2410;'
                                f'border-left:1px dashed #2e2410;color:#c8832a;font-size:12px;white-space:nowrap">'
                                f'R$ {pu}<br><span style="font-size:10px;color:#6a4e28">({unid} un)</span></td>'
                            )
                        else:
                            cels += (
                                '<td style="padding:9px 10px;text-align:center;border-bottom:1px solid #2e2410;'
                                'border-left:1px dashed #2e2410;color:#4a3520;font-size:11px">unit.</td>'
                            )
                else:
                    cels += (
                        '<td style="padding:9px 16px;text-align:center;border-bottom:1px solid #2e2410;'
                        'color:#4a3520;font-size:12px">—</td>'
                    )
                    if site == SITE_SAMS:
                        cels += (
                            '<td style="padding:9px 10px;text-align:center;border-bottom:1px solid #2e2410;'
                            'border-left:1px dashed #2e2410;color:#4a3520;font-size:12px">—</td>'
                        )
            linhas += (
                f'<tr><td style="padding:9px 14px;border-bottom:1px solid #2e2410;'
                f'font-size:13px;color:#d4b896">{nome}</td>{cels}</tr>'
            )

        return f"""
  <div style="margin-bottom:36px">
    <h2 style="margin:0 0 10px;color:#f5a623;font-size:16px;font-weight:500;
               border-left:3px solid #f5a623;padding-left:10px">{marca}</h2>
    <div style="overflow-x:auto;border-radius:8px;border:1px solid #2e2410">
      <table style="width:100%;border-collapse:collapse;font-family:inherit">
        <thead>
          <tr style="background:#2a1c0a">
            <th style="padding:10px 14px;text-align:left;font-size:12px;font-weight:500;
                       color:#a07840;border-bottom:2px solid #2e2410">Produto</th>
            {th_sites}
          </tr>
        </thead>
        <tbody style="background:#1e1408">{linhas}</tbody>
      </table>
    </div>
  </div>"""

    secoes = "".join(secao(m) for m in marcas)
    total  = len(produtos)
    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de Precos de Cerveja - {data_fmt}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#120d04;color:#e8d5b0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
</style>
</head>
<body>
<div style="max-width:1080px;margin:0 auto;padding:32px 20px">

  <header style="margin-bottom:36px;border-bottom:1px solid #2e2410;padding-bottom:20px">
    <p style="font-size:11px;color:#a07840;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">
      Monitoramento de precos</p>
    <h1 style="font-size:26px;font-weight:500;color:#f5a623;margin-bottom:6px">
      Cervejas — Comparativo por site</h1>
    <p style="font-size:13px;color:#6a4e28">{data_fmt} &nbsp;·&nbsp; {total} produtos &nbsp;·&nbsp; {len(sites)} sites</p>
  </header>

  {secoes}

  <footer style="margin-top:36px;border-top:1px solid #2e2410;padding-top:14px;
                 font-size:11px;color:#4a3520;text-align:center">
    Gerado por cerveja_monitor em {gerado}
  </footer>
</div>
</body>
</html>"""


if __name__ == "__main__":
    produtos, data = carregar_ultima_varredura()
    html = gerar_html(produtos, data)
    with open("relatorio.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Relatorio gerado: relatorio.html  ({len(produtos)} produtos)")
