# Monitor de cervejas — v2

Versao nova do relatorio diario, equivalente ao que a tarefa do Claude faz no
computador. Substitui o fluxo v1 (`relatorio-diario.yml`, desativado).

## O que mudou em relacao a v1

| | v1 | v2 |
|---|---|---|
| Lojas | Sonda + Sam's | Sonda + Sam's + **Ze Delivery** |
| Marcas | 4 | 9 (Heineken, Spaten, Michelob, Stella Artois, Beck's, Amstel, Colorado, Therezopolis, Patagonia) |
| Criterio de decisao | preco do pack | **preco por litro** |
| `Lata 8x350ml` | lido como **1** unidade (preco/un 8x maior) | lido como 8 unidades |
| `Barril 5l` | sem volume | 5 L, entra no ranking |
| Zero alcool / Ultra / Pure Gold | misturados com a tradicional | versao identificada e exibida separada |
| Chopeira, copo, balde | entravam como cerveja | descartados |
| Historico | preco do dia anterior | minimas de 7 e 30 dias + minima historica |
| Secoes do e-mail | tabela por marca | 7 secoes (ver abaixo) |
| Cabecalho de tabela | cinza claro sobre texto claro | `bgcolor` + inline, legivel no modo escuro do Gmail |
| Segredos | gravados em `email_config.py` no runner | lidos do ambiente, nunca em disco |

## Secoes do relatorio

1. Melhor custo-beneficio do dia
2. Todas as ofertas, ordenadas por preco/litro (3 primeiras destacadas)
3. Melhores promocoes
4. Melhor preco por marca (as 9; "nao encontrada" quando faltar)
5. Comparacao com dias anteriores — minimas de 7/30 dias e minima historica
6. Recomendacao: o que comprar e o que esperar
7. Limitacoes: o que nao pode ser consultado e por que

## Arquivos

| Arquivo | Papel |
|---|---|
| `cerveja_parse.py` | le o nome do produto: marca, versao, unidades, volume, precos |
| `config_v2.py` | marcas, CEP, sites ativos, caminhos |
| `coleta_v2.py` | Sonda e Sam's (scraping) + Ze Delivery (API) + enriquecimento |
| `relatorio_v2.py` | monta o HTML do e-mail |
| `executar_v2.py` | orquestra: coleta -> CSV -> HTML -> commit -> e-mail |
| `.github/workflows/cervejas-v2.yml` | agendamento diario |

Os arquivos da v1 continuam no repositorio e nao sao usados pela v2.

## Dados

- `data/historico_v2.csv` — schema novo, separador `;`:
  `data;hora;loja;marca;versao;embalagem;unidades;volume_total_l;preco_total;preco_unidade;preco_litro;estoque;desconto_pct;produto;link`
- `data/historico_completo.csv` — historico da v1. **Nao e alterado.** O
  relatorio le os dois: o antigo e convertido em memoria, entao as minimas de
  7/30 dias ja nascem com os meses coletados desde junho/2026.

## Rodar na mao

```bash
pip install -r requirements.txt
python executar_v2.py --sem-email --sem-git   # so gera relatorio_cervejas.html
python executar_v2.py                          # coleta, commita e envia
```

Credenciais: variaveis `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `DESTINATARIO`
(ou um `email_config.py` local, que fica fora do git).

## Ze Delivery

Funciona, via a API GraphQL publica do site (`POST https://api.ze.delivery/public-api`,
operacao `newSearch`). Nao precisa de login nem de cookie.

O detalhe que trava quem tenta: **o preco depende do endereco de entrega**, e o
endereco nao vai no corpo da requisicao — fica guardado no backend atrelado ao
header `x-visitorid`. Com o visitorId certo, a API devolve o preco da regiao;
sem ele, devolve vitrine vazia. Os demais headers (`x-session-id`,
`x-session-id-amplitude`) podem ser gerados a cada execucao.

Por isso o id vai num secret, `ZE_VISITOR_ID`, e nao no codigo: ele identifica
um visitante e o endereco associado, o que nao deve ficar num repositorio.

### Como obter ou renovar o ZE_VISITOR_ID

1. Abra `https://www.ze.delivery` no navegador e defina o endereco de entrega.
2. Abra o DevTools (F12) → aba Network → filtre por `public-api`.
3. Clique em qualquer requisicao e veja os Request Headers.
4. Copie o valor de `x-visitorid` (formato UUID).
5. No GitHub: Settings → Secrets and variables → Actions → New repository secret,
   nome `ZE_VISITOR_ID`.

Se o id expirar, o Ze volta a aparecer em "Limitacoes" com a mensagem de que a
API respondeu mas nao veio preco — sinal de refazer os passos acima. As outras
duas lojas seguem normalmente nesse meio tempo.

## Agendamento

Quatro horarios (09:00, 10:00, 11:30 e 14:00 de Brasilia) porque o agendador
gratuito do GitHub atrasa ou pula execucoes. A primeira que rodar grava a data
em `historico_v2.csv`; as seguintes veem que o dia ja foi coletado e saem sem
fazer nada — um e-mail por dia. Para forcar, use "Run workflow" com a opcao
`forcar`.
