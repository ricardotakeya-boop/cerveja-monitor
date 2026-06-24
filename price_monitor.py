"""
Monitor de preços de cerveja - Sonda Delivery / Zé Delivery / Sun's Club

Uso:
    python price_monitor.py

O script:
  1. Varre as categorias configuradas em cada site ativo;
  2. Filtra os produtos pelas marcas definidas em config.py;
  3. Salva os resultados em CSV (um arquivo por dia + um histórico acumulado);
  4. Compara com o CSV do dia anterior e avisa sobre mudanças de preço.

IMPORTANTE:
  - O parser do Sonda usa padrões confirmados nas páginas reais (URL de
    produto no formato /delivery/produto/<slug>/<id> e o texto "R$ X,XX").
  - Os parsers de Zé Delivery e Sun's Club estão como esqueleto (TODO).
    Sites modernos costumam carregar produtos via JavaScript/API, então
    pode ser necessário usar Selenium/Playwright ou a API interna do site
    em vez de requests simples. Ajuste com a ajuda do Claude Code, que terá
    acesso real à internet para inspecionar o HTML/JS de verdade.
"""

import csv
import logging
import os
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("monitor.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# SONDA DELIVERY
# ---------------------------------------------------------------------------

def parse_sonda_html(html: str, base_url: str = "https://www.sondadelivery.com.br"):
    """Extrai produtos (nome, url, preço) de uma página de categoria do Sonda.

    Estratégia: procura links cujo href siga o padrão /delivery/produto/...
    (confirmado nas páginas reais) e, a partir desse link, sobe na árvore
    HTML até achar um texto com "R$ X,XX" próximo.
    """
    soup = BeautifulSoup(html, "html.parser")
    produtos = []
    vistos = set()

    links = soup.find_all("a", href=re.compile(r"/delivery/produto/"))

    for link in links:
        href = link.get("href", "")
        nome = link.get_text(strip=True)

        if not nome or href in vistos:
            continue

        preco = None
        nivel = link
        for _ in range(6):  # sobe até 6 níveis procurando o preço
            nivel = nivel.find_parent()
            if nivel is None:
                break
            texto = nivel.get_text(" ", strip=True)
            m = re.search(r"R\$\s*([\d.,]+)", texto)
            if m:
                preco = m.group(1)
                break

        if preco is None:
            continue  # provavelmente não é o card do produto, e sim um link de menu

        vistos.add(href)
        url_completa = href if href.startswith("http") else base_url + href
        produtos.append({"nome": nome, "url": url_completa, "preco": preco})

    return produtos


def fetch_sonda_categoria(categoria_slug: str):
    """Varre todas as páginas de uma categoria do Sonda Delivery."""
    base = f"https://www.sondadelivery.com.br/delivery/categoria/{categoria_slug}"
    todos = []
    vistos_urls = set()
    itens_por_pagina = 15

    for pagina in range(1, config.MAX_PAGINAS_POR_CATEGORIA + 1):
        url = base if pagina == 1 else f"{base}/0/{pagina}/{itens_por_pagina}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logging.warning(f"[Sonda] Erro ao buscar página {pagina} de {categoria_slug}: {e}")
            break

        produtos = parse_sonda_html(resp.text)
        novos = [p for p in produtos if p["url"] not in vistos_urls]

        if not novos:
            break  # chegou ao fim das páginas (ou o parser não achou nada)

        for p in novos:
            vistos_urls.add(p["url"])
        todos.extend(novos)

        logging.info(f"[Sonda] {categoria_slug} - página {pagina}: {len(novos)} produtos novos")
        time.sleep(config.DELAY_ENTRE_REQUISICOES)

    return todos


def buscar_sonda():
    """Busca e filtra produtos do Sonda Delivery por marca."""
    resultados = []
    for categoria in config.SONDA_CATEGORIAS:
        produtos = fetch_sonda_categoria(categoria)
        resultados.extend(produtos)

    return filtrar_por_marcas(resultados, site="Sonda Delivery")


# ---------------------------------------------------------------------------
# ZÉ DELIVERY  (usa Playwright para renderizar o JS do site)
# ---------------------------------------------------------------------------

def buscar_ze_delivery():
    """
    Zé Delivery é um SPA Next.js que carrega produtos via GraphQL apenas após
    definir um endereço de entrega no contexto de sessão. Usa Playwright para
    abrir o site, inserir o CEP, navegar pelas marcas e interceptar as
    respostas GraphQL com os produtos.

    Requer instalação adicional (uma única vez):
        pip install playwright
        playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logging.warning(
            "[Zé Delivery] playwright não instalado. "
            "Execute: pip install playwright && playwright install chromium"
        )
        return []

    produtos_capturados = []

    def _capturar_resposta(response):
        if "api.ze.delivery/public-api" not in response.url or response.status != 200:
            return
        try:
            body = response.json()
            data = body.get("data") or {}
            for key in ("searchProducts", "search", "getProducts"):
                sr = data.get(key)
                if sr and isinstance(sr, dict):
                    items = (sr.get("items") or sr.get("products")
                             or sr.get("results") or [])
                    if items:
                        produtos_capturados.extend(items)
                        logging.info(
                            f"[Zé Delivery] GraphQL '{key}': {len(items)} itens capturados"
                        )
        except Exception:
            pass

    def _tentar_preencher(page, seletores, texto, timeout=5000):
        for sel in seletores:
            try:
                el = page.locator(sel).first
                el.wait_for(state="visible", timeout=timeout)
                el.fill(texto, timeout=timeout)
                return True
            except Exception:
                continue
        return False

    def _tentar_clicar(page, seletores, timeout=4000):
        for sel in seletores:
            try:
                el = page.locator(sel).first
                el.wait_for(state="visible", timeout=timeout)
                el.click(timeout=timeout)
                return True
            except Exception:
                continue
        return False

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="pt-BR",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.on("response", _capturar_resposta)

        try:
            logging.info("[Zé Delivery] Abrindo site...")
            page.goto("https://www.ze.delivery", wait_until="networkidle", timeout=30000)

            # --- inserir endereço / CEP ---
            SEL_ADDR = [
                "input[placeholder*='endereço']",
                "input[placeholder*='endereco']",
                "input[placeholder*='CEP']",
                "input[data-testid*='address']",
                "input[name='address']",
                "input[type='text']",
            ]
            SEL_SUG = [
                "[data-testid*='suggestion']",
                "[class*='suggestion']",
                "[class*='autocomplete'] li",
                "ul[role='listbox'] li",
                "[class*='dropdown'] li",
            ]
            SEL_SEARCH = [
                "input[placeholder*='buscar']",
                "input[placeholder*='pesquisar']",
                "input[placeholder*='procurar']",
                "input[type='search']",
                "[data-testid*='search'] input",
                "input[name='search']",
            ]

            ok = _tentar_preencher(page, SEL_ADDR, config.CEP)
            if ok:
                page.wait_for_timeout(2000)
                _tentar_clicar(page, SEL_SUG)
                page.wait_for_timeout(3000)
                logging.info(f"[Zé Delivery] Endereço {config.CEP} inserido.")
            else:
                logging.warning("[Zé Delivery] Não encontrou campo de endereço.")

            # --- buscar cada marca ---
            for marca in config.MARCAS:
                ok = _tentar_preencher(page, SEL_SEARCH, marca)
                if ok:
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(3000)
                    logging.info(f"[Zé Delivery] Busca por '{marca}' concluída.")
                else:
                    logging.warning(f"[Zé Delivery] Campo de busca não encontrado para '{marca}'.")
                time.sleep(config.DELAY_ENTRE_REQUISICOES)

        except Exception as e:
            logging.warning(f"[Zé Delivery] Erro inesperado: {e}")
        finally:
            browser.close()

    # Normalizar e deduplicar produtos capturados
    resultados = []
    vistos = set()
    for item in produtos_capturados:
        pid = str(item.get("id", ""))
        if pid in vistos:
            continue
        vistos.add(pid)

        nome = (item.get("title") or item.get("name")
                or item.get("productName") or pid)
        preco_raw = (item.get("price") or item.get("salesPrice")
                     or item.get("value"))

        if isinstance(preco_raw, dict):
            centavos = preco_raw.get("value") or preco_raw.get("cents") or 0
            preco = f"{centavos / 100:.2f}".replace(".", ",")
        elif preco_raw is not None:
            try:
                preco = f"{float(preco_raw):.2f}".replace(".", ",")
            except (ValueError, TypeError):
                preco = str(preco_raw)
        else:
            continue

        resultados.append({
            "nome": nome,
            "url": f"https://www.ze.delivery/produto/{pid}",
            "preco": preco,
        })

    return filtrar_por_marcas(resultados, site="Zé Delivery")


# ---------------------------------------------------------------------------
# SAM'S CLUB  (identificado como "Sun's Club" no config original)
# ---------------------------------------------------------------------------

def buscar_suns_club():
    """
    Sam's Club Brasil (samsclub.com.br) usa a plataforma VTEX, que expõe
    uma API de busca de texto sem autenticação. Busca cada marca da lista e
    extrai nome/preço/URL dos produtos disponíveis em estoque.

    A URL do site confirmada é: https://www.samsclub.com.br
    """
    BASE_URL = "https://www.samsclub.com.br"
    API_URL = f"{BASE_URL}/api/catalog_system/pub/products/search"
    todos = []
    vistos_ids = set()

    # Termos de busca: para "Stella Artois Pure Gold" a API VTEX não retorna nada
    # com o nome completo, então buscamos por "Stella Artois" e o filtro downstream
    # seleciona apenas os produtos Pure Gold.
    TERMOS_BUSCA = {
        "Stella Artois Pure Gold": "Stella",
    }

    for marca in config.MARCAS:
        termo = TERMOS_BUSCA.get(marca, marca)
        offset = 0
        while offset < 200:
            params = {"ft": termo, "_from": offset, "_to": offset + 49}
            try:
                resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
                if resp.status_code == 400:
                    # VTEX retorna 400 quando não acha resultados para o termo
                    logging.info(f"[Sam's Club] '{marca}': nenhum produto encontrado.")
                    break
                resp.raise_for_status()
                produtos = resp.json()
            except requests.RequestException as e:
                logging.warning(f"[Sam's Club] Erro ao buscar '{marca}': {e}")
                break
            except ValueError:
                logging.warning(f"[Sam's Club] JSON inválido para '{marca}'")
                break

            if not produtos:
                break

            novos = 0
            for p in produtos:
                pid = p.get("productId", "")
                if pid in vistos_ids:
                    continue
                vistos_ids.add(pid)

                nome = p.get("productName", "")
                link_text = p.get("linkText", "")

                # Pega o preço do primeiro SKU disponível em estoque
                preco = None
                for sku in p.get("items", []):
                    for seller in sku.get("sellers", []):
                        offer = seller.get("commertialOffer", {})
                        if offer.get("AvailableQuantity", 0) > 0:
                            val = offer.get("Price")
                            if val:
                                preco = f"{val:.2f}".replace(".", ",")
                                break
                    if preco:
                        break

                if not nome or not preco:
                    continue

                url = f"{BASE_URL}/{link_text}/p" if link_text else BASE_URL
                todos.append({"nome": nome, "url": url, "preco": preco})
                novos += 1

            logging.info(f"[Sam's Club] '{marca}' offset={offset}: {novos} produtos novos")

            if novos == 0 or len(produtos) < 50:
                break
            offset += 50
            time.sleep(config.DELAY_ENTRE_REQUISICOES)

    return filtrar_por_marcas(todos, site="Sam's Club")


# ---------------------------------------------------------------------------
# FILTRO POR MARCA
# ---------------------------------------------------------------------------

def filtrar_por_marcas(produtos, site: str):
    # Para marcas compostas como "Stella Artois Pure Gold", verifica as palavras
    # mais específicas (ex: "pure gold") em vez da string completa, pois os sites
    # usam nomes mais curtos que não incluem o subtítulo completo da marca.
    KEYWORDS = {
        "Stella Artois Pure Gold": ["pure gold"],
    }
    resultado = []
    for p in produtos:
        nome_lower = p["nome"].lower()
        for marca in config.MARCAS:
            keywords = KEYWORDS.get(marca, [marca.lower()])
            if any(kw in nome_lower for kw in keywords):
                resultado.append({
                    "site": site,
                    "marca_buscada": marca,
                    "produto": p["nome"],
                    "preco": p["preco"],
                    "url": p["url"],
                })
                break
    return resultado


# ---------------------------------------------------------------------------
# PERSISTÊNCIA EM CSV
# ---------------------------------------------------------------------------

def salvar_resultados(dados):
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    agora = datetime.now()
    timestamp = agora.strftime("%Y-%m-%d %H:%M:%S")
    arquivo_dia = os.path.join(config.OUTPUT_DIR, f"precos_{agora.strftime('%Y%m%d')}.csv")
    arquivo_historico = os.path.join(config.OUTPUT_DIR, "historico_completo.csv")

    campos = ["timestamp", "site", "marca_buscada", "produto", "preco", "url"]

    for caminho in (arquivo_dia, arquivo_historico):
        novo_arquivo = not os.path.exists(caminho)
        with open(caminho, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            if novo_arquivo:
                writer.writeheader()
            for item in dados:
                writer.writerow({**item, "timestamp": timestamp})

    logging.info(f"Resultados salvos em {arquivo_dia} e {arquivo_historico}")
    return arquivo_dia


def carregar_csv(caminho):
    if not os.path.exists(caminho):
        return []
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def comparar_com_dia_anterior(dados_hoje, arquivo_hoje):
    """Compara os preços de hoje com o último CSV diário disponível antes deste."""
    pasta = config.OUTPUT_DIR
    arquivos = sorted(
        f for f in os.listdir(pasta)
        if f.startswith("precos_") and f.endswith(".csv") and f != os.path.basename(arquivo_hoje)
    )

    if not arquivos:
        logging.info("Nenhum histórico anterior para comparar ainda.")
        return

    arquivo_anterior = os.path.join(pasta, arquivos[-1])
    dados_anteriores = carregar_csv(arquivo_anterior)

    precos_anteriores = {
        (d["site"], d["produto"]): d["preco"] for d in dados_anteriores
    }

    for item in dados_hoje:
        chave = (item["site"], item["produto"])
        preco_antigo = precos_anteriores.get(chave)
        if preco_antigo and preco_antigo != item["preco"]:
            logging.info(
                f"⚠️  MUDANÇA DE PREÇO: {item['produto']} ({item['site']}) "
                f"R$ {preco_antigo} -> R$ {item['preco']}"
            )


# ---------------------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# ---------------------------------------------------------------------------

def main():
    logging.info("=== Iniciando varredura de preços de cerveja ===")
    todos_resultados = []

    if config.SITES_ATIVOS.get("sonda"):
        todos_resultados.extend(buscar_sonda())

    if config.SITES_ATIVOS.get("ze_delivery"):
        todos_resultados.extend(buscar_ze_delivery())

    if config.SITES_ATIVOS.get("suns_club"):
        todos_resultados.extend(buscar_suns_club())

    if not todos_resultados:
        logging.warning("Nenhum produto encontrado. Verifique os parsers/seletores.")
        return

    logging.info(f"Total de produtos encontrados: {len(todos_resultados)}")
    for item in todos_resultados:
        logging.info(f"  [{item['site']}] {item['produto']} -> R$ {item['preco']}")

    arquivo_hoje = salvar_resultados(todos_resultados)
    comparar_com_dia_anterior(todos_resultados, arquivo_hoje)

    logging.info("=== Varredura concluída — publicando relatório ===")

    import subprocess, sys
    subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "publicar_relatorio.py")],
        check=False,
    )


if __name__ == "__main__":
    main()
