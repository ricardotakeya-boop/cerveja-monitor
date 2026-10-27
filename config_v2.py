"""
Configuracao do monitor de cervejas v2.

A v2 segue o escopo da tarefa do Claude: 9 marcas, preco por litro como
criterio principal, historico com minimas de 7 e 30 dias e relatorio completo.
"""

# --- Marcas monitoradas (termos usados na busca dos sites) -------------------
# O reconhecimento fino de marca/versao fica em cerveja_parse.py; aqui ficam
# apenas os termos de BUSCA enviados aos sites.
TERMOS_BUSCA = [
    "Heineken",
    "Spaten",
    "Michelob",
    "Stella Artois",
    "Beck's",
    "Amstel",
    "Colorado",
    "Therezopolis",
    "Patagonia",
]

# Marcas que devem aparecer no quadro "melhor preco por marca", na ordem.
# Quando nenhuma oferta for encontrada, a linha sai como "nao encontrada".
MARCAS_RELATORIO = [
    "Heineken",
    "Spaten",
    "Michelob",
    "Stella Artois",
    "Beck's",
    "Amstel",
    "Colorado",
    "Therezópolis",
    "Patagonia",
]

# --- Regiao ------------------------------------------------------------------
CEP = "09760-280"          # Sao Bernardo do Campo, SP
CEP_DIGITOS = "09760280"

# --- Sites -------------------------------------------------------------------
# ze_delivery exige geolocalizacao e API autenticada; sem navegador real o
# GitHub Actions nao consegue consultar. Fica desligado e o relatorio informa
# isso na secao "Limitacoes" em vez de omitir silenciosamente.
SITES_ATIVOS = {
    "sonda": True,
    "sams_club": True,
    "ze_delivery": False,
}

MOTIVO_SITE_INATIVO = {
    "ze_delivery": (
        "Ze Delivery exige geolocalizacao e API autenticada; nao e acessivel "
        "a partir do GitHub Actions sem navegador real. Continua coberto pela "
        "tarefa do Claude que roda no Chrome do computador."
    ),
}

SAMS_CATEGORIAS = [
    "categoria/bebidas/cervejas",
    "categoria/bebidas/cervejas/importadas",
]

# --- Coleta ------------------------------------------------------------------
DELAY_ENTRE_REQUISICOES = 1.5
MAX_PAGINAS_POR_CATEGORIA = 15
TIMEOUT = 25
TENTATIVAS = 3

# --- Arquivos ----------------------------------------------------------------
OUTPUT_DIR = "data"
HISTORICO_V2 = "data/historico_v2.csv"      # schema novo, separador ';'
HISTORICO_ANTIGO = "data/historico_completo.csv"  # schema v1, separador ','
RELATORIO_HTML = "relatorio_cervejas.html"

# --- E-mail ------------------------------------------------------------------
ASSUNTO_PREFIXO = "Precos de cervejas"
