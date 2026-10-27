"""
Coleta de precos (v2) - Sonda Delivery e Sam's Club.

A mecanica de scraping e a mesma da v1, que funciona em producao desde
junho/2026. O que muda e o enriquecimento: cada oferta sai com marca, versao,
unidades, volume total e PRECO POR LITRO, que e o criterio de decisao.
"""

import csv
import logging
import os
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

import config_v2 as cfg
import cerveja_parse as cp

log = logging.getLogger("coleta")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

CAMPOS = [
    "data", "hora", "loja", "marca", "versao", "embalagem", "unidades",
    "volume_total_l", "preco_total", "preco_unidade", "preco_litro",
    "estoque", "desconto_pct", "produto", "link",
]


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def get(url: str):
    erro = None
    for tentativa in range(1, cfg.TENTATIVAS + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=cfg.TIMEOUT)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r
        except requests.RequestException as e:
            erro = e
            if tentativa < cfg.TENTATIVAS:
                time.sleep(5)
    raise erro


# ---------------------------------------------------------------------------
# PRECOS NO HTML
# ---------------------------------------------------------------------------

def precos_no_texto(texto: str):
    """
    Devolve (preco_final, preco_de) a partir de textos como:
      'R$ 36,98-20%R$ 29,52' -> ('29,52', '36,98')
      'De R$ 40,48 Por R$ 35,94' -> ('35,94', '40,48')
      'R$ 36,98' -> ('36,98', None)
    O ultimo valor e sempre o que o cliente paga.
    """
    valores = re.findall(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})", texto)
    if not valores:
        return None, None
    final = valores[-1]
    de = valores[0] if len(valores) > 1 and valores[0] != final else None
    return final, de


def _preco_subindo_arvore(link, padrao_href):
    """Sobe ate 6 niveis, parando se o pai contiver mais de um produto."""
    nivel = link
    for _ in range(6):
        nivel = nivel.find_parent()
        if nivel is None:
            return None, None
        if len(nivel.find_all("a", href=re.compile(padrao_href))) > 1:
            return None, None
        final, de = precos_no_texto(nivel.get_text(" ", strip=True))
        if final:
            return final, de
    return None, None


def limpar_nome(texto: str) -> str:
    """
    Tira do nome o que o card agrega: preco, desconto e botao.
      "Cerveja Heineken Pack 8 Latas 269ml CadaR$ 36,98Adicionar"
        -> "Cerveja Heineken Pack 8 Latas 269ml Cada"
    No Sonda o nome ja costuma vir limpo; aqui a funcao e um no-op.
    """
    nome = re.split(r"R\$", texto)[0]
    nome = re.sub(r"\b(Adicionar|Comprar|Esgotado)\s*$", "", nome, flags=re.IGNORECASE)
    return nome.strip(" -–—|")


def extrair_cards(html: str, padrao_href: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    produtos, vistos = [], set()

    for link in soup.find_all("a", href=re.compile(padrao_href)):
        href = link.get("href", "")
        texto = link.get_text(" ", strip=True)
        if not texto or href in vistos or len(texto) < 5:
            continue

        final, de = precos_no_texto(texto)
        if final is None:
            final, de = _preco_subindo_arvore(link, padrao_href)
        if final is None:
            continue

        nome = limpar_nome(texto)
        if not nome:
            continue

        vistos.add(href)
        produtos.append({
            "nome": nome,
            "url": href if href.startswith("http") else base_url + href,
            "preco": final,
            "preco_de": de,
        })
    return produtos


# ---------------------------------------------------------------------------
# SONDA DELIVERY
# ---------------------------------------------------------------------------

def buscar_sonda():
    from urllib.parse import quote
    base = "https://www.sondadelivery.com.br"
    achados, vistos = [], set()

    for termo in cfg.TERMOS_BUSCA:
        for pagina in range(1, cfg.MAX_PAGINAS_POR_CATEGORIA + 1):
            url = f"{base}/delivery/busca/{quote(termo.lower())}/{pagina}/18/0"
            try:
                resp = get(url)
            except requests.RequestException as e:
                log.warning("[Sonda] '%s' pagina %s: %s", termo, pagina, e)
                break

            produtos = extrair_cards(resp.text, r"/delivery/produto/", base)
            novos = [p for p in produtos if p["url"] not in vistos]
            if not novos:
                break
            for p in novos:
                vistos.add(p["url"])
            achados.extend(novos)
            log.info("[Sonda] '%s' p%s: +%s", termo, pagina, len(novos))
            time.sleep(cfg.DELAY_ENTRE_REQUISICOES)

    return achados


# ---------------------------------------------------------------------------
# SAM'S CLUB
# ---------------------------------------------------------------------------

def buscar_sams():
    base = "https://www.samsclub.com.br"
    achados, vistos = [], set()

    def varrer():
        for categoria in cfg.SAMS_CATEGORIAS:
            for pagina in range(1, cfg.MAX_PAGINAS_POR_CATEGORIA + 1):
                url = f"{base}/{categoria}" + ("" if pagina == 1 else f"?page={pagina}")
                try:
                    resp = get(url)
                except requests.RequestException as e:
                    log.warning("[Sam's] %s p%s: %s", categoria, pagina, e)
                    break

                produtos = extrair_cards(resp.text, r"/produto/", base)
                novos = [p for p in produtos if p["url"] not in vistos]
                if not novos:
                    break
                for p in novos:
                    vistos.add(p["url"])
                achados.extend(novos)
                log.info("[Sam's] %s p%s: +%s", categoria, pagina, len(novos))
                time.sleep(cfg.DELAY_ENTRE_REQUISICOES)

    varrer()
    if not achados:
        log.warning("[Sam's] nada na 1a varredura; nova tentativa em 30s")
        time.sleep(30)
        varrer()
    return achados


# ---------------------------------------------------------------------------
# ZE DELIVERY
# ---------------------------------------------------------------------------

def buscar_ze():
    """Desligado por padrao: ver config_v2.MOTIVO_SITE_INATIVO."""
    log.info("[Ze Delivery] desativado nesta execucao")
    return []


# ---------------------------------------------------------------------------
# ENRIQUECIMENTO
# ---------------------------------------------------------------------------

def enriquecer(brutos, loja: str):
    """Aplica cerveja_parse e calcula preco/unidade e preco/litro."""
    agora = datetime.now()
    data, hora = agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M")
    ofertas = []

    for p in brutos:
        info = cp.interpretar(p["nome"])
        if not info["eh_cerveja"] or not info["marca"]:
            continue

        total = cp.preco_para_float(p["preco"])
        if total <= 0:
            continue

        unidade, litro = cp.calcular(total, info["unidades"], info["volume_total_l"])

        desconto = ""
        if p.get("preco_de"):
            de = cp.preco_para_float(p["preco_de"])
            if de > total > 0:
                desconto = f"{round((de - total) / de * 100)}"

        ofertas.append({
            "data": data,
            "hora": hora,
            "loja": loja,
            "marca": info["marca"],
            "versao": info["versao"] + (" sem gluten" if info["sem_gluten"] else ""),
            "embalagem": info["embalagem"],
            "unidades": info["unidades"],
            "volume_total_l": f"{info['volume_total_l']:.3f}".replace(".", ",") if info["volume_total_l"] else "",
            "preco_total": f"{total:.2f}".replace(".", ","),
            "preco_unidade": f"{unidade:.2f}".replace(".", ",") if unidade else "",
            "preco_litro": f"{litro:.2f}".replace(".", ",") if litro else "",
            "estoque": "disponivel",
            "desconto_pct": desconto,
            "produto": p["nome"],
            "link": p["url"],
        })
    return ofertas


# ---------------------------------------------------------------------------
# PERSISTENCIA
# ---------------------------------------------------------------------------

def salvar(ofertas):
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    novo = not os.path.exists(cfg.HISTORICO_V2)
    with open(cfg.HISTORICO_V2, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";")
        if novo:
            w.writeheader()
        for o in ofertas:
            w.writerow(o)
    log.info("%s ofertas gravadas em %s", len(ofertas), cfg.HISTORICO_V2)


def coletar():
    """Retorna (ofertas, falhas) - falhas e {loja: motivo}."""
    ofertas, falhas = [], {}

    if cfg.SITES_ATIVOS.get("sonda"):
        try:
            ofertas += enriquecer(buscar_sonda(), "Sonda Delivery")
        except Exception as e:
            falhas["Sonda Delivery"] = f"{type(e).__name__}: {e}"
            log.error("Sonda falhou: %s", e)

    if cfg.SITES_ATIVOS.get("sams_club"):
        try:
            ofertas += enriquecer(buscar_sams(), "Sam's Club")
        except Exception as e:
            falhas["Sam's Club"] = f"{type(e).__name__}: {e}"
            log.error("Sam's falhou: %s", e)

    if cfg.SITES_ATIVOS.get("ze_delivery"):
        try:
            ofertas += enriquecer(buscar_ze(), "Ze Delivery")
        except Exception as e:
            falhas["Ze Delivery"] = f"{type(e).__name__}: {e}"
    else:
        falhas["Ze Delivery"] = cfg.MOTIVO_SITE_INATIVO["ze_delivery"]

    # Dedup: mesma loja + mesmo link, mantendo o menor preco por litro.
    melhor = {}
    for o in ofertas:
        chave = (o["loja"], o["link"])
        atual = melhor.get(chave)
        if atual is None:
            melhor[chave] = o
            continue
        pl_novo = cp.preco_para_float(o["preco_litro"]) or float("inf")
        pl_atual = cp.preco_para_float(atual["preco_litro"]) or float("inf")
        if pl_novo < pl_atual:
            melhor[chave] = o

    return list(melhor.values()), falhas
