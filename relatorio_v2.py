"""
Relatorio v2 - HTML para e-mail.

Secoes (na ordem definida na tarefa do Claude):
  1. cabecalho com data/hora e origem
  2. tabela geral ordenada por preco/litro, com as 3 melhores destacadas
  3. melhor custo-beneficio do dia
  4. melhores promocoes
  5. melhor preco por marca (as 9, com "nao encontrada" quando faltar)
  6. comparacao com dias anteriores: minimas de 7 e 30 dias e minima historica
  7. recomendacao
  8. limitacoes

Todas as tabelas levam <thead> com <th> em cinza claro e texto preto, com
bgcolor E estilo inline, para continuarem legiveis no modo escuro do Gmail.
"""

import csv
import os
from datetime import datetime, timedelta

import config_v2 as cfg
import cerveja_parse as cp

# --- paleta -----------------------------------------------------------------
BORDA = "#999999"
TH_BG = "#D9D9D9"
DESTAQUE_BG = "#FFF8E1"
VERDE = "#1b7a3d"
VERMELHO = "#c0392b"

TH = (f'style="background-color:{TH_BG};color:#000000;font-weight:bold;'
      f'text-align:left;padding:6px;border:1px solid {BORDA}"')
TD = f'style="padding:6px;border:1px solid {BORDA};color:#000000"'
TD_D = (f'style="padding:6px;border:1px solid {BORDA};color:#000000;'
        f'background-color:{DESTAQUE_BG};font-weight:bold"')


def _esc(texto) -> str:
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# HISTORICO
# ---------------------------------------------------------------------------

def _ler_v2(caminho):
    if not os.path.exists(caminho):
        return []
    with open(caminho, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f, delimiter=";")]


def _ler_v1(caminho):
    """Converte o historico antigo (schema v1) para o formato v2, em memoria.

    Serve para o relatorio ja nascer com minimas de 7 e 30 dias e minima
    historica reais, aproveitando os meses coletados pela versao anterior.
    """
    if not os.path.exists(caminho):
        return []
    convertidos = []
    with open(caminho, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nome = (r.get("produto") or "").strip()
            if not nome:
                continue
            info = cp.interpretar(nome)
            if not info["eh_cerveja"] or not info["marca"]:
                continue
            total = cp.preco_para_float(r.get("preco_pack"))
            if total <= 0:
                continue
            _, litro = cp.calcular(total, info["unidades"], info["volume_total_l"])
            ts = (r.get("timestamp") or "")[:10]          # 2026-10-26
            try:
                data = datetime.strptime(ts, "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                continue
            convertidos.append({
                "data": data,
                "loja": r.get("site", ""),
                "marca": info["marca"],
                "versao": info["versao"],
                "embalagem": info["embalagem"],
                "preco_total": f"{total:.2f}".replace(".", ","),
                "preco_litro": f"{litro:.2f}".replace(".", ",") if litro else "",
                "produto": nome,
                "link": r.get("url", ""),
            })
    return convertidos


def carregar_historico():
    """Historico v2 + v1 convertido, sem duplicar o dia/loja/produto."""
    registros = _ler_v2(cfg.HISTORICO_V2) + _ler_v1(cfg.HISTORICO_ANTIGO)
    vistos, unicos = set(), []
    for r in registros:
        chave = (r.get("data"), r.get("loja"), r.get("produto"))
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(r)
    return unicos


def _data(reg):
    try:
        return datetime.strptime(reg.get("data", ""), "%d/%m/%Y")
    except ValueError:
        return None


def minimas(historico, chave_produto, hoje):
    """(min 7 dias, min 30 dias, min historica, data da min historica)."""
    d7 = hoje - timedelta(days=7)
    d30 = hoje - timedelta(days=30)
    m7 = m30 = mh = None
    data_mh = None

    for r in historico:
        if (r.get("marca"), r.get("versao"), r.get("embalagem")) != chave_produto:
            continue
        pl = cp.preco_para_float(r.get("preco_litro"))
        if pl <= 0:
            continue
        dt = _data(r)
        if dt is None:
            continue
        if mh is None or pl < mh:
            mh, data_mh = pl, dt
        if dt >= d7 and (m7 is None or pl < m7):
            m7 = pl
        if dt >= d30 and (m30 is None or pl < m30):
            m30 = pl
    return m7, m30, mh, data_mh


# ---------------------------------------------------------------------------
# BLOCOS
# ---------------------------------------------------------------------------

def _tabela(cabecalhos, linhas):
    if not linhas:
        return '<p style="color:#000000">Nada a mostrar.</p>'
    ths = "".join(f"<th {TH}>{_esc(c)}</th>" for c in cabecalhos)
    corpo = ""
    for celulas, destacar in linhas:
        td = TD_D if destacar else TD
        corpo += "<tr>" + "".join(f"<td {td}>{c}</td>" for c in celulas) + "</tr>"
    return (
        '<table cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;width:100%;max-width:640px;'
        f'border:1px solid {BORDA};font-size:14px">'
        f'<thead><tr bgcolor="{TH_BG}">{ths}</tr></thead>'
        f"<tbody>{corpo}</tbody></table>"
    )


def _link(oferta, texto=None):
    url = oferta.get("link") or ""
    rotulo = _esc(texto or "abrir")
    if not url:
        return rotulo
    return f'<a href="{_esc(url)}" style="color:#0b5fae">{rotulo}</a>'


def _pl(oferta):
    return cp.preco_para_float(oferta.get("preco_litro")) or float("inf")


def secao(titulo, conteudo, cor="#0b5fae"):
    return (
        f'<h2 style="font-size:17px;color:{cor};margin:26px 0 10px">{titulo}</h2>'
        f"{conteudo}"
    )


def bloco_geral(ofertas):
    com_litro = sorted([o for o in ofertas if _pl(o) != float("inf")], key=_pl)
    sem_litro = [o for o in ofertas if _pl(o) == float("inf")]
    linhas = []
    for i, o in enumerate(com_litro + sem_litro, 1):
        pl = cp.preco_para_float(o.get("preco_litro"))
        promo = f'{o["desconto_pct"]}%' if o.get("desconto_pct") else "—"
        linhas.append((
            [
                str(i), _esc(o["loja"]),
                f'{_esc(o["marca"])} <span style="color:#555">{_esc(o["versao"])}</span>',
                _esc(o["embalagem"]),
                cp.formatar_brl(cp.preco_para_float(o["preco_total"])),
                cp.formatar_brl(cp.preco_para_float(o["preco_unidade"])) if o.get("preco_unidade") else "—",
                cp.formatar_brl(pl) if pl else "—",
                promo,
                _link(o),
            ],
            i <= 3,
        ))
    return _tabela(
        ["#", "Loja", "Cerveja", "Embalagem", "Preço total",
         "Preço/unidade", "Preço/litro", "Promoção", "Link"],
        linhas,
    )


def bloco_melhor(ofertas):
    candidatas = [o for o in ofertas if _pl(o) != float("inf")]
    if not candidatas:
        return '<p style="color:#000000">Nenhuma oferta com preço por litro calculável hoje.</p>'
    o = min(candidatas, key=_pl)
    return (
        f'<p style="font-size:15px;color:#000000;margin:0">'
        f'<b>{_esc(o["marca"])} {_esc(o["versao"])}</b> — {_esc(o["embalagem"])} '
        f'na <b>{_esc(o["loja"])}</b><br>'
        f'{cp.formatar_brl(cp.preco_para_float(o["preco_total"]))} '
        f'&nbsp;·&nbsp; <b style="color:{VERDE}">'
        f'{cp.formatar_brl(cp.preco_para_float(o["preco_litro"]))} por litro</b><br>'
        f'{_link(o, "ver na loja")}</p>'
    )


def bloco_promocoes(ofertas):
    promos = [o for o in ofertas if o.get("desconto_pct")]
    promos.sort(key=lambda o: -int(o["desconto_pct"]))
    linhas = []
    for o in promos[:10]:
        total = cp.preco_para_float(o["preco_total"])
        pct = int(o["desconto_pct"])
        de = total / (1 - pct / 100) if pct < 100 else None
        linhas.append((
            [
                _esc(o["loja"]),
                f'{_esc(o["marca"])} {_esc(o["versao"])} — {_esc(o["embalagem"])}',
                cp.formatar_brl(de) if de else "—",
                cp.formatar_brl(total),
                f'<b style="color:{VERDE}">−{pct}%</b>',
                _link(o),
            ],
            False,
        ))
    if not linhas:
        return '<p style="color:#000000">Nenhum desconto identificado hoje.</p>'
    return _tabela(["Loja", "Cerveja", "De", "Por", "Desconto", "Link"], linhas)


def bloco_por_marca(ofertas):
    linhas = []
    for marca in cfg.MARCAS_RELATORIO:
        candidatas = [o for o in ofertas if o["marca"] == marca and _pl(o) != float("inf")]
        if not candidatas:
            linhas.append((
                [_esc(marca), "—", '<i style="color:#666">não encontrada</i>', "—", "—"],
                False,
            ))
            continue
        o = min(candidatas, key=_pl)
        linhas.append((
            [
                f'<b>{_esc(marca)}</b>',
                _esc(o["loja"]),
                f'{_esc(o["versao"])} / {_esc(o["embalagem"])}',
                cp.formatar_brl(cp.preco_para_float(o["preco_total"])),
                f'<b>{cp.formatar_brl(cp.preco_para_float(o["preco_litro"]))}</b>',
            ],
            False,
        ))
    return _tabela(["Marca", "Loja", "Versão / embalagem", "Preço", "Preço/litro"], linhas)


def bloco_historico(ofertas, historico, hoje):
    linhas, recordes = [], []
    for o in sorted(ofertas, key=_pl):
        pl = cp.preco_para_float(o.get("preco_litro"))
        if pl <= 0:
            continue
        chave = (o["marca"], o["versao"], o["embalagem"])
        m7, m30, mh, data_mh = minimas(historico, chave, hoje)

        if mh and pl <= mh + 0.001:
            tendencia = f'<b style="color:{VERDE}">menor preço já registrado</b>'
            recordes.append(o)
        elif m7 and pl < m7:
            tendencia = f'<span style="color:{VERDE}">abaixo da mínima de 7 dias</span>'
        elif m7 and pl > m7 * 1.05:
            tendencia = f'<span style="color:{VERMELHO}">acima da mínima recente</span>'
        else:
            tendencia = "estável"

        linhas.append((
            [
                f'{_esc(o["marca"])} {_esc(o["versao"])} — {_esc(o["embalagem"])}',
                _esc(o["loja"]),
                cp.formatar_brl(pl),
                cp.formatar_brl(m7) if m7 else "—",
                cp.formatar_brl(m30) if m30 else "—",
                (cp.formatar_brl(mh) + (f' <span style="color:#555">({data_mh:%d/%m})</span>' if data_mh else "")) if mh else "—",
                tendencia,
            ],
            bool(mh and pl <= mh + 0.001),
        ))

    tabela = _tabela(
        ["Cerveja", "Loja", "Hoje (R$/L)", "Mín. 7 dias", "Mín. 30 dias",
         "Mínima histórica", "Situação"],
        linhas[:25],
    )
    return tabela, recordes


def bloco_recomendacao(ofertas, recordes):
    candidatas = [o for o in ofertas if _pl(o) != float("inf")]
    if not candidatas:
        return '<p style="color:#000000">Sem dados suficientes para recomendar hoje.</p>'

    melhor = min(candidatas, key=_pl)
    caras = sorted(candidatas, key=_pl, reverse=True)[:3]

    partes = [
        f'<p style="color:#000000;margin:0 0 8px"><b>Vale comprar:</b> '
        f'{_esc(melhor["marca"])} {_esc(melhor["versao"])} ({_esc(melhor["embalagem"])}) '
        f'na {_esc(melhor["loja"])}, a {cp.formatar_brl(cp.preco_para_float(melhor["preco_litro"]))} por litro.</p>'
    ]
    if recordes:
        nomes = ", ".join(f'{_esc(o["marca"])} {_esc(o["embalagem"])}' for o in recordes[:3])
        partes.append(
            f'<p style="color:{VERDE};margin:0 0 8px"><b>Mínima histórica hoje:</b> {nomes}. '
            f'Se for estocar, é o momento.</p>'
        )
    if caras:
        nomes = ", ".join(
            f'{_esc(o["marca"])} {_esc(o["embalagem"])} ({cp.formatar_brl(_pl(o))}/L)'
            for o in caras
        )
        partes.append(
            f'<p style="color:#000000;margin:0"><b>Melhor esperar:</b> {nomes}.</p>'
        )
    return "".join(partes)


def bloco_limitacoes(falhas):
    if not falhas:
        return '<p style="color:#000000">Nenhuma limitação: todas as lojas foram consultadas.</p>'
    itens = "".join(
        f'<li style="margin-bottom:6px"><b>{_esc(loja)}</b>: {_esc(motivo)}</li>'
        for loja, motivo in falhas.items()
    )
    return (
        '<div style="background-color:#fff3e0;border-left:4px solid #ef8a17;'
        'padding:10px 14px"><ul style="margin:0;padding-left:18px;color:#000000">'
        f"{itens}</ul></div>"
    )


# ---------------------------------------------------------------------------
# MONTAGEM
# ---------------------------------------------------------------------------

def gerar_html(ofertas, falhas, agora=None):
    agora = agora or datetime.now()
    historico = carregar_historico()
    tabela_hist, recordes = bloco_historico(ofertas, historico, agora)

    lojas = sorted({o["loja"] for o in ofertas})
    resumo = (
        f'{len(ofertas)} ofertas · {len(lojas)} loja(s): {", ".join(lojas)}'
        if ofertas else "Nenhuma oferta coletada nesta execução."
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Preços de cervejas — {agora:%d/%m/%Y}</title></head>
<body style="margin:0;padding:0;background-color:#ffffff">
<div style="max-width:640px;margin:0 auto;padding:18px;
            font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#000000">

  <h1 style="font-size:20px;color:#0b5fae;margin:0 0 6px">🍺 Preços de cervejas</h1>
  <p style="margin:0 0 4px;color:#000000">
    Consulta: <b>{agora:%d/%m/%Y às %H:%M}</b> (horário de Brasília)</p>
  <p style="margin:0 0 4px;color:#333333;font-size:13px">
    Origem: GitHub Actions · CEP de referência {cfg.CEP} (São Bernardo do Campo)</p>
  <p style="margin:0 0 4px;color:#333333;font-size:13px">{_esc(resumo)}</p>

  {secao("🏆 Melhor custo-benefício do dia", bloco_melhor(ofertas))}
  {secao("📊 Todas as ofertas (ordenadas por preço/litro)", bloco_geral(ofertas))}
  {secao("🔥 Melhores promoções", bloco_promocoes(ofertas))}
  {secao("🍺 Melhor preço por marca", bloco_por_marca(ofertas))}
  {secao("📉 Comparação com dias anteriores", tabela_hist)}
  {secao("🛒 Recomendação", bloco_recomendacao(ofertas, recordes))}
  {secao("⚠️ Limitações", bloco_limitacoes(falhas), cor="#b35c00")}

  <p style="margin:28px 0 0;padding-top:12px;border-top:1px solid #cccccc;
            font-size:12px;color:#666666">
    Monitor de cervejas v2 · preço por litro como critério principal ·
    gerado em {agora:%d/%m/%Y %H:%M}</p>
</div></body></html>"""


def resumo_texto(ofertas, falhas, agora=None):
    """Corpo alternativo em texto simples."""
    agora = agora or datetime.now()
    candidatas = [o for o in ofertas if _pl(o) != float("inf")]
    linhas = [f"Precos de cervejas - {agora:%d/%m/%Y %H:%M}", ""]
    if candidatas:
        o = min(candidatas, key=_pl)
        linhas.append(
            f'Melhor do dia: {o["marca"]} {o["versao"]} {o["embalagem"]} '
            f'({o["loja"]}) - R$ {o["preco_litro"]}/L'
        )
    linhas.append(f"{len(ofertas)} ofertas coletadas.")
    if falhas:
        linhas.append("")
        linhas.append("Limitacoes:")
        for loja, motivo in falhas.items():
            linhas.append(f"  - {loja}: {motivo}")
    return "\n".join(linhas)
