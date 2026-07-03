"""
Configurações do monitor de preços de cerveja.
Edite este arquivo para ajustar marcas monitoradas, CEP e sites ativos.
"""

# Marcas/termos de busca.
# Filtro por substring no nome do produto, sem distinção de maiúsculas/minúsculas.
MARCAS = [
    "Heineken",
    "Spaten",
    "Michelob",
    "Stella Artois Pure Gold",
]

# CEP usado para consultas que dependem de região de entrega (formato só números)
CEP = "09766690"

# Pasta onde os arquivos CSV de histórico serão salvos
OUTPUT_DIR = "data"

# Sites ativos no monitoramento
SITES_ATIVOS = {
    "sonda": True,
    "sams_club": True,
    "ze_delivery": False,   # TODO: inspecionar API interna do site
}

# Categorias do Sonda Delivery a varrer
SONDA_CATEGORIAS = ["Cervejas"]

# Categorias do Sam's Club a varrer
SAMS_CATEGORIAS = [
    "categoria/bebidas/cervejas",
    "categoria/bebidas/cervejas/importadas",
]

# Tempo de espera (segundos) entre requisições
DELAY_ENTRE_REQUISICOES = 1.5

# Máximo de páginas a varrer por categoria
MAX_PAGINAS_POR_CATEGORIA = 15
