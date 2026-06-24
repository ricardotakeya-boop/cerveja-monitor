"""
Configurações do monitor de preços de cerveja.
Edite este arquivo para ajustar marcas monitoradas, CEP e sites ativos.
"""

# Marcas/termos de busca.
# O filtro é por substring no nome do produto, sem distinção de maiúsculas/minúsculas.
# Ajuste os nomes se o produto aparecer com grafia diferente no site
# (ex: "Spaten" em vez de "Spartem", "Stella Artois Pure Gold" em vez de "Stella Gold").
MARCAS = [
    "Heineken",
    "Spaten",
    "Michelob",
    "Stella Artois",
]

# CEP usado para consultas que dependem de região de entrega (formato só números)
CEP = "09766690"

# Pasta onde os arquivos CSV de histórico serão salvos
OUTPUT_DIR = "data"

# Sites ativos no monitoramento.
# Defina como True quando o site estiver implementado e testado.
SITES_ATIVOS = {
    "sonda": True,
    "ze_delivery": False,   # requer: pip install playwright && playwright install chromium
    "suns_club": True,      # Sam's Club (samsclub.com.br) - API VTEX, sem autenticação
}

# Categorias do Sonda Delivery a varrer em busca das marcas
SONDA_CATEGORIAS = ["Cervejas"]

# Tempo de espera (segundos) entre requisições, para não sobrecarregar o site
DELAY_ENTRE_REQUISICOES = 1.5

# Máximo de páginas a varrer por categoria (segurança contra loop infinito)
MAX_PAGINAS_POR_CATEGORIA = 15
