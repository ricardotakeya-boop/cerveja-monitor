"""
Interpretacao do nome do produto: marca, versao, embalagem, unidades e volume.

Este modulo e a base do monitor v2. Ele resolve os problemas da versao antiga:
  - "Lata 8x350ml" era lido como 1 unidade (preco/unidade saia 8x maior);
  - "Barril 5l" ficava sem volume (nao dava para calcular preco por litro);
  - "6 garrafas de 330ml" era lido como 1 unidade;
  - versoes zero alcool / Ultra / Pure Gold eram misturadas com a tradicional;
  - acessorios (chopeira, copo, balde) entravam como se fossem cerveja.

Nao faz rede: e puro texto, o que permite testar com o historico ja coletado.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# NORMALIZACAO
# ---------------------------------------------------------------------------

def sem_acento(texto: str) -> str:
    """'Zero Alcool' e 'Zero Álcool' viram a mesma coisa."""
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Minusculas, sem acento, espacos colapsados."""
    return re.sub(r"\s+", " ", sem_acento(texto or "").lower()).strip()


# ---------------------------------------------------------------------------
# O QUE NAO E CERVEJA
# ---------------------------------------------------------------------------

# Nunca sao cerveja, apareca a palavra onde aparecer.
NUNCA_CERVEJA = [
    "beertender", "abridor", "camiseta", "kit presente", "porta-copo",
    "bolsa termica", "dispenser", "growler", "refil co2", "cilindro",
    "cartao presente",
]

# Excluem apenas quando sao o proprio produto, isto e, no inicio do nome.
# "Chopeira Eletrica Heineken..." e aparelho;
# "Barril Spaten 6L - exclusivo para Chopeiras PerfectDraft" e cerveja.
ACESSORIO_SE_NO_INICIO = [
    "chopeira", "copo", "taca", "caneca", "balde", "cooler",
]

_INICIO = 30   # caracteres considerados "inicio do nome"


def eh_cerveja(nome: str) -> bool:
    n = normalizar(nome)
    if not n:
        return False
    if any(p in n for p in NUNCA_CERVEJA):
        return False
    inicio = n[:_INICIO]
    return not any(p in inicio for p in ACESSORIO_SE_NO_INICIO)


# ---------------------------------------------------------------------------
# MARCA
# ---------------------------------------------------------------------------

# Ordem importa: a primeira que casar vence. "michelob" antes de nada generico.
MARCAS = [
    ("Heineken",     ["heineken"]),
    ("Spaten",       ["spaten"]),
    ("Michelob",     ["michelob"]),
    ("Stella Artois", ["stella artois", "stella"]),
    ("Beck's",       ["beck's", "becks", "beck s"]),
    ("Amstel",       ["amstel"]),
    ("Colorado",     ["colorado"]),
    ("Therezópolis", ["therezopolis", "therezopolis", "thereza"]),
    ("Patagonia",    ["patagonia"]),
]


def detectar_marca(nome: str):
    n = normalizar(nome)
    for marca, termos in MARCAS:
        for t in termos:
            if normalizar(t) in n:
                return marca
    return None


# ---------------------------------------------------------------------------
# VERSAO (linha do produto)
# ---------------------------------------------------------------------------

# Ordem importa: "pure gold" antes de "gold"; "zero" antes de "tradicional".
VERSOES = [
    # "Heineken Zero 330ml" e "Heineken Zero Sleek" tambem sao sem alcool:
    # por isso "zero" solto entra aqui, antes de qualquer outra versao.
    ("Zero álcool", ["zero alcool", "0,0%", "0.0%", "sem alcool", "shot zero",
                     "zero %", "zero", "0%"]),
    ("Ultra",       ["ultra"]),
    ("Pure Gold",   ["pure gold"]),
    ("Gold",        ["gold"]),
    ("Ultimate",    ["ultimate"]),
    ("IPA",         ["ipa"]),
    ("Weiss",       ["weiss", "weizen"]),
    ("Puro malte",  ["puro malte", "munich helles", "munich"]),
    ("Lager",       ["lager", "pilsen"]),
]


def detectar_versao(nome: str) -> str:
    n = normalizar(nome)
    for versao, termos in VERSOES:
        if any(t in n for t in termos):
            return versao
    return "Tradicional"


def sem_gluten(nome: str) -> bool:
    return "sem gluten" in normalizar(nome)


# ---------------------------------------------------------------------------
# EMBALAGEM: UNIDADES E VOLUME
# ---------------------------------------------------------------------------

_TIPOS = r"(?:latas?|latinhas?|garrafas?|long\s*necks?|longnecks?|unidades?|un\b|und\b|pack|cervejas?)"


def _volume_ml(texto: str):
    """
    Extrai o volume de UMA unidade, em ml.
    Aceita '350ml', '330 ml', '5l', '5 litros', '1,5 l', '600ML'.
    """
    n = normalizar(texto)

    m = re.search(r"(\d{2,4})\s*ml\b", n)
    if m:
        return float(m.group(1))

    # litros: 'barril 5l', '5 litros', '1,5l'
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:l|lt|lts|litros?)\b", n)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000

    return None


def _unidades(texto: str) -> int:
    """
    Quantas unidades vem na embalagem.
    Cobre, nesta ordem:
      '8x350ml' / '8 x 350 ml'          -> 8
      'pack 12 latas' / 'pack com 6 un' -> 12 / 6
      '6 garrafas de 330ml'             -> 6
      'c/ 12 unidades'                  -> 12
      'leve 6 pague 5'                  -> 6
    """
    n = normalizar(texto)

    # 8x350ml  (o numero ANTES do x e a quantidade)
    m = re.search(r"(\d{1,2})\s*[x×]\s*\d{2,4}\s*ml", n)
    if m:
        return int(m.group(1))

    # pack 12 latas / pack com 6 unidades / pack 6 long neck
    m = re.search(rf"pack\s+(?:com\s+)?(\d{{1,2}})\s*{_TIPOS}", n)
    if m:
        return int(m.group(1))

    # 6 garrafas de 330ml / 12 latas 350ml / 8 unidades de 350ml
    m = re.search(rf"(\d{{1,2}})\s*{_TIPOS}", n)
    if m:
        return int(m.group(1))

    # c/ 12  |  com 12 unidades
    m = re.search(r"(?:c/|com)\s*(\d{1,2})\s*(?:un|unid)", n)
    if m:
        return int(m.group(1))

    # leve 6 pague 5 -> o cliente leva 6
    m = re.search(r"leve\s*(\d{1,2})", n)
    if m:
        return int(m.group(1))

    return 1


def descrever_embalagem(unidades: int, vol_ml) -> str:
    """'6x330ml', '1x5000ml' -> 'Barril 5L', '1x350ml' -> 'Lata 350ml'."""
    if not vol_ml:
        return f"{unidades}x?" if unidades > 1 else "avulso"
    if vol_ml >= 1000:
        litros = f"{vol_ml / 1000:g}".replace(".", ",")
        base = f"{litros}L"
    else:
        base = f"{vol_ml:g}ml"
    return f"{unidades}x{base}" if unidades > 1 else base


def interpretar(nome: str) -> dict:
    """
    Converte o nome do produto num registro estruturado.
    Retorna sempre as chaves; valores podem ser None quando nao der para inferir.
    """
    unidades = _unidades(nome)
    vol_ml = _volume_ml(nome)
    volume_total_l = (unidades * vol_ml / 1000) if vol_ml else None

    return {
        "marca": detectar_marca(nome),
        "versao": detectar_versao(nome),
        "sem_gluten": sem_gluten(nome),
        "unidades": unidades,
        "volume_ml": vol_ml,
        "volume_total_l": volume_total_l,
        "embalagem": descrever_embalagem(unidades, vol_ml),
        "eh_cerveja": eh_cerveja(nome),
    }


# ---------------------------------------------------------------------------
# PRECOS
# ---------------------------------------------------------------------------

def preco_para_float(valor) -> float:
    """'1.394,90' -> 1394.90 ; '35,98' -> 35.98 ; '' -> 0.0"""
    if valor is None:
        return 0.0
    s = str(valor).strip()
    if not s:
        return 0.0
    s = re.sub(r"[^\d.,]", "", s)
    if "," in s:                      # formato brasileiro
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def formatar_brl(valor) -> str:
    """1394.9 -> 'R$ 1.394,90'"""
    if valor is None:
        return "—"
    inteiro, _, decimal = f"{float(valor):,.2f}".partition(".")
    return "R$ " + inteiro.replace(",", ".") + "," + decimal


def calcular(preco_total, unidades: int, volume_total_l):
    """Devolve (preco_unidade, preco_litro), ambos float ou None."""
    total = preco_para_float(preco_total)
    if total <= 0:
        return None, None
    unidade = total / unidades if unidades and unidades > 0 else total
    litro = total / volume_total_l if volume_total_l and volume_total_l > 0 else None
    return unidade, litro
