"""
Monitor de preços de cerveja - Sonda Delivery / Sam's Club / Zé Delivery

Uso:
    python price_monitor.py

O script:
  1. Varre as categorias configuradas em cada site ativo;
  2. Filtra os produtos pelas marcas definidas em config.py;
  3. Salva os resultados em CSV (um arquivo por dia + histórico acumulado);
  4. Compara com o CSV do dia anterior e avisa sobre mudanças de preço.
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
# UTILIDADES COMUNS
# ---------------------------------------------------------------------------

def extrair_preco_final(texto: str):
    """
    Extrai o preço final (com desconto, se houver) de um texto como:
      'R$ 36,98-20%R$ 29,52'  → '29,52'
      'R$ 14,98-10%R$ 13,48'  → '13,48'
      'R$ 36,98'              → '36,98'
    Retorna None se não encontrar nenhum valor.
    """
    # Pega TODOS os valores "R$ X,XX" e retorna o último (que é o preço com desconto)
    valores = re.findall(r"R\$\s*([\d]+[.,][\d]{2})", texto)
    if not valores:
        return None
    return valores[-1]  # o último é sempre o preço final


def extrair_quantidade_e_volume(nome: str):
    """
    Tenta extrair quantidade de unidades e volume do nome do produto.
    Exemplos:
      'Cerveja Heineken Pack 8 Latas 269ml Cada' → (8, '269ml')
      'Cerveja Heineken Long Neck 330ml'          → (1, '330ml')
      'Cerveja Heineken Pack 12 Latas 350ml Cada' → (12, '350ml')
    Retorna (qtd, volume_str) onde qtd é int e volume_str é string como '269ml'.
    """
    nome_lower = nome.lower()

    # Tenta achar "pack X latas/garrafas/unidades Yml"
    m_pack = re.search(r"pack\s+(\d+)\s+(?:latas?|garrafas?|unidades?|long\s+neck)[^0-9]*(\d+\s*ml)", nome_lower)
    if m_pack:
        return int(m_pack.group(1)), m_pack.group(2).replace(" ", "")

    # Tenta achar "X unidades ... Yml"
    m_unid = re.search(r"(\d+)\s+unidades?[^0-9]*(\d+\s*ml)", nome_lower)
    if m_unid:
        return int(m_unid.group(1)), m_unid.group(2).replace(" ", "")

    # Apenas volume (produto avulso)
    m_vol = re.search(r"(\d+\s*ml)", nome_lower)
    volume = m_vol.group(1).replace(" ", "") if m_vol else None
    return 1, volume


def filtrar_por_marcas(produtos, site: str):
    resultado = []
    for p in produtos:
        nome_lower = p["nome"].lower()
        for marca in config.MARCAS:
            if marca.lower() in nome_lower:
                qtd, volume = extrair_quantidade_e_volume(p["nome"])
                preco_pack = p.get("preco")
                try:
                    preco_num = float(preco_pack.replace(".", "").replace(",", ".")) if preco_pack else None
                    preco_unit = f"{preco_num / qtd:.2f}".replace(".", ",") if (preco_num and qtd > 0) else None
                except Exception:
                    preco_unit = None

                resultado.append({
                    "site": site,
                    "marca_buscada": marca,
                    "produto": p["nome"],
                    "quantidade": qtd,
                    "volume": volume or "",
                    "preco_pack": preco_pack or "",
                    "preco_unitario": preco_unit or "",
                    "url": p.get("url", ""),
                })
                break
    return resultado


# ---------------------------------------------------------------------------
# SONDA DELIVERY
# ---------------------------------------------------------------------------

def parse_sonda_html(html: str, base_url: str = "https://www.sondadelivery.com.br"):
    """
    Extrai produtos de uma página do Sonda (busca ou categoria).
    Procura links cujo href contenha /delivery/produto/ e acha o preço
    no texto do próprio link ou subindo na árvore — mas só enquanto o
    elemento pai contiver apenas ESTE produto, para não pegar preço de
    outro card (padrão 'De R$ X Por R$ Y': o último valor é o final).
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

        preco = extrair_preco_final(link.get_text(" ", strip=True))
        if preco is None:
            nivel = link
            for _ in range(6):
                nivel = nivel.find_parent()
                if nivel is None:
                    break
                if len(nivel.find_all("a", href=re.compile(r"/delivery/produto/"))) > 1:
                    break
                preco = extrair_preco_final(nivel.get_text(" ", strip=True))
                if preco:
                    break

        if preco is None:
            continue

        vistos.add(href)
        url_completa = href if href.startswith("http") else base_url + href
        produtos.append({"nome": nome, "url": url_completa, "preco": preco})

    return produtos


def fetch_sonda_busca(termo: str):
    """
    Busca produtos pelo termo (marca) na busca do site, que continua
    funcionando sem JavaScript — a página de categoria não serve mais
    os produtos para clientes sem JS (passou a devolver vitrine genérica).
    Padrão de URL: /delivery/busca/<termo>/<pagina>/<itens>/<ordenacao>
    """
    from urllib.parse import quote

    termo_url = quote(termo.lower())
    itens_por_pagina = 18
    todos = []
    vistos_urls = set()

    for pagina in range(1, config.MAX_PAGINAS_POR_CATEGORIA + 1):
        url = (
            f"https://www.sondadelivery.com.br/delivery/busca/"
            f"{termo_url}/{pagina}/{itens_por_pagina}/0"
        )

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            logging.warning(f"[Sonda] Erro página {pagina} da busca '{termo}': {e}")
            break

        produtos = parse_sonda_html(resp.text)
        novos = [p for p in produtos if p["url"] not in vistos_urls]

        if not novos:
            break

        for p in novos:
            vistos_urls.add(p["url"])
        todos.extend(novos)

        logging.info(f"[Sonda] busca '{termo}' - página {pagina}: {len(novos)} produtos novos")
        time.sleep(config.DELAY_ENTRE_REQUISICOES)

    return todos


def buscar_sonda():
    resultados = []
    for marca in config.MARCAS:
        resultados.extend(fetch_sonda_busca(marca))

    # Deduplica por URL (buscas de marcas diferentes podem retornar o mesmo produto)
    vistos = set()
    unicos = []
    for p in resultados:
        if p["url"] not in vistos:
            vistos.add(p["url"])
            unicos.append(p)

    return filtrar_por_marcas(unicos, site="Sonda Delivery")


# ---------------------------------------------------------------------------
# SAM'S CLUB
# ---------------------------------------------------------------------------

def limpar_nome_sams(nome: str) -> str:
    """
    Remove o lixo que vem junto do nome no card do Sam's Club:
      'Cerveja Heineken Pack 8 Latas 269ml CadaR$ 36,98Adicionar'
        → 'Cerveja Heineken Pack 8 Latas 269ml Cada'
    Corta tudo a partir do primeiro 'R$' e remove 'Adicionar' no final.
    """
    nome = re.split(r"R\$", nome)[0]
    nome = re.sub(r"Adicionar\s*$", "", nome, flags=re.IGNORECASE)
    return nome.strip()


def parse_sams_html(html: str, base_url: str = "https://www.samsclub.com.br"):
    """
    Extrai produtos de uma página de categoria do Sam's Club.
    O site é HTML estático (VTEX), então requests + BeautifulSoup funciona.

    Estrutura observada:
      - Links de produto: /produto/<slug>-<id>
      - O texto do próprio link contém nome + preço + 'Adicionar'
        (pode ter desconto: 'R$ X,XX-Y%R$ Z,WW' → o último valor é o final)
    """
    soup = BeautifulSoup(html, "html.parser")
    produtos = []
    vistos = set()

    links = soup.find_all("a", href=re.compile(r"/produto/"))

    for link in links:
        href = link.get("href", "")
        texto_link = link.get_text(" ", strip=True)

        if not texto_link or href in vistos or len(texto_link) < 5:
            continue

        # 1) Preço: primeiro tenta no texto do próprio link (contém só ESTE produto)
        preco = extrair_preco_final(texto_link)

        # 2) Se não achou, sobe na árvore — mas só enquanto o pai contiver
        #    apenas este link de produto, para não pegar preço de outro card.
        if preco is None:
            nivel = link
            for _ in range(6):
                nivel = nivel.find_parent()
                if nivel is None:
                    break
                if len(nivel.find_all("a", href=re.compile(r"/produto/"))) > 1:
                    break
                preco = extrair_preco_final(nivel.get_text(" ", strip=True))
                if preco:
                    break

        if preco is None:
            continue

        nome = limpar_nome_sams(texto_link)
        if not nome:
            continue

        vistos.add(href)
        url_completa = href if href.startswith("http") else base_url + href
        produtos.append({"nome": nome, "url": url_completa, "preco": preco})

    return produtos


def fetch_sams_categoria(categoria_path: str):
    """Varre todas as páginas de uma categoria do Sam's Club."""
    base = f"https://www.samsclub.com.br/{categoria_path}"
    todos = []
    vistos_urls = set()

    for pagina in range(1, config.MAX_PAGINAS_POR_CATEGORIA + 1):
        url = base if pagina == 1 else f"{base}?page={pagina}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = "utf-8"  # evita nomes como 'Ãlcool'
        except requests.RequestException as e:
            logging.warning(f"[Sam's Club] Erro página {pagina} de {categoria_path}: {e}")
            break

        produtos = parse_sams_html(resp.text)
        novos = [p for p in produtos if p["url"] not in vistos_urls]

        if not novos:
            logging.info(f"[Sam's Club] {categoria_path} - página {pagina}: fim da paginação")
            break

        for p in novos:
            vistos_urls.add(p["url"])
        todos.extend(novos)

        logging.info(f"[Sam's Club] {categoria_path} - página {pagina}: {len(novos)} produtos novos")
        time.sleep(config.DELAY_ENTRE_REQUISICOES)

    return todos


def buscar_sams_club():
    resultados = []
    for categoria in config.SAMS_CATEGORIAS:
        produtos = fetch_sams_categoria(categoria)
        resultados.extend(produtos)

    # Deduplica por URL (a mesma cerveja pode aparecer em mais de uma categoria)
    vistos = set()
    unicos = []
    for p in resultados:
        if p["url"] not in vistos:
            vistos.add(p["url"])
            unicos.append(p)

    return filtrar_por_marcas(unicos, site="Sam's Club")


# ---------------------------------------------------------------------------
# ZÉ DELIVERY (TODO - esqueleto)
# ---------------------------------------------------------------------------

def buscar_ze_delivery():
    """
    TODO: O Zé Delivery carrega produtos via JavaScript/API.
    Inspecione a aba Network (F12) no navegador, filtre por Fetch/XHR,
    e ache a chamada que retorna os produtos em JSON ao buscar por "cerveja".
    Depois implemente aqui chamando essa API diretamente com requests.
    """
    logging.info("[Zé Delivery] Ainda não implementado - pulando.")
    return []


# ---------------------------------------------------------------------------
# PERSISTÊNCIA EM CSV
# ---------------------------------------------------------------------------

CAMPOS = [
    "timestamp", "site", "marca_buscada", "produto",
    "quantidade", "volume", "preco_pack", "preco_unitario", "url"
]


def salvar_resultados(dados):
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    agora = datetime.now()
    timestamp = agora.strftime("%Y-%m-%d %H:%M:%S")
    arquivo_dia = os.path.join(config.OUTPUT_DIR, f"precos_{agora.strftime('%Y%m%d')}.csv")
    arquivo_historico = os.path.join(config.OUTPUT_DIR, "historico_completo.csv")

    for caminho in (arquivo_dia, arquivo_historico):
        novo_arquivo = not os.path.exists(caminho)
        with open(caminho, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CAMPOS)
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
        (d["site"], d["produto"]): d.get("preco_pack", d.get("preco", ""))
        for d in dados_anteriores
    }

    mudancas = []
    for item in dados_hoje:
        chave = (item["site"], item["produto"])
        preco_antigo = precos_anteriores.get(chave)
        preco_novo = item["preco_pack"]
        if preco_antigo and preco_antigo != preco_novo:
            msg = (
                f"⚠️  MUDANÇA DE PREÇO: {item['produto']} ({item['site']}) "
                f"R$ {preco_antigo} → R$ {preco_novo}"
            )
            logging.info(msg)
            mudancas.append(msg)

    if not mudancas:
        logging.info("Nenhuma mudança de preço detectada em relação ao dia anterior.")


# ---------------------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# ---------------------------------------------------------------------------

def main():
    logging.info("=== Iniciando varredura de preços de cerveja ===")
    todos_resultados = []

    if config.SITES_ATIVOS.get("sonda"):
        todos_resultados.extend(buscar_sonda())

    if config.SITES_ATIVOS.get("sams_club"):
        todos_resultados.extend(buscar_sams_club())

    if config.SITES_ATIVOS.get("ze_delivery"):
        todos_resultados.extend(buscar_ze_delivery())

    if not todos_resultados:
        logging.warning("Nenhum produto encontrado. Verifique os parsers/seletores.")
        return

    logging.info(f"Total de produtos encontrados: {len(todos_resultados)}")
    for item in todos_resultados:
        unit_info = f" | unit: R$ {item['preco_unitario']}" if item.get("preco_unitario") else ""
        logging.info(
            f"  [{item['site']}] {item['produto']} "
            f"→ pack: R$ {item['preco_pack']} (x{item['quantidade']}){unit_info}"
        )

    arquivo_hoje = salvar_resultados(todos_resultados)
    comparar_com_dia_anterior(todos_resultados, arquivo_hoje)

    logging.info("=== Varredura concluída ===")


if __name__ == "__main__":
    main()
