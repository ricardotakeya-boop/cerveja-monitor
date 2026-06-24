# Monitor de Preços de Cerveja

Monitora diariamente o preço de marcas específicas de cerveja (Heineken, Spaten,
Michelob, Stella Artois Pure Gold) no Sonda Delivery, Zé Delivery e Sun's Club.

## Status atual

| Site          | Status                                                  |
|---------------|----------------------------------------------------------|
| Sonda Delivery| ✅ Implementado (varre a categoria Cervejas e filtra)     |
| Zé Delivery   | ⚠️ TODO - esqueleto pronto, precisa de implementação      |
| Sun's Club    | ⚠️ TODO - precisa confirmar a URL exata do site primeiro  |

## Como usar (com o Claude Code)

1. Abra esta pasta (`cerveja_monitor`) no Claude Code.
2. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```
3. Rode o script uma vez para testar:
   ```
   python price_monitor.py
   ```
4. Veja os resultados em `data/precos_AAAAMMDD.csv` e no log `monitor.log`.

## Próximos passos para completar o projeto

Peça ao Claude Code, que terá acesso real à internet, para te ajudar com:

1. **Validar o parser do Sonda**: o parser usa o padrão de URL
   `/delivery/produto/...` e o texto `R$ X,XX` para identificar produtos.
   Rode o script e confira se os preços batem com o site. Se algum produto
   não for capturado, peça para o Claude Code inspecionar o HTML real da
   página de categoria e ajustar a função `parse_sonda_html`.

2. **Implementar o Zé Delivery**: abra o site, aperte F12 (DevTools), vá na
   aba *Network*, filtre por "Fetch/XHR" e procure a chamada que retorna os
   produtos em JSON ao buscar por "cerveja". Se achar, é só chamar essa API
   direto com `requests` (mais rápido e estável que automatizar navegador).
   Se não achar nada óbvio, pode ser necessário usar Selenium ou Playwright.

3. **Implementar o Sun's Club**: primeiro confirme comigo (ou pesquise) qual
   é a URL exata do site - não tenho certeza de qual serviço é esse.
   Depois, implemente seguindo o mesmo padrão usado para o Sonda.

4. **Agendar a execução diária**:
   - **Windows**: edite o caminho em `agendar_tarefa.ps1` e rode-o no
     PowerShell como Administrador. Isso cria uma tarefa agendada que roda
     todo dia às 08:00.
   - Alternativa manual: Painel de Controle > Tarefas Agendadas > Criar
     Tarefa Básica > apontar para `python.exe` com argumento
     `price_monitor.py` e diretório de trabalho a pasta do projeto.

5. **(Opcional) Notificações**: hoje o script só registra mudanças de preço
   no log (`monitor.log`) e no console. Se quiser, dá pra evoluir isso para
   enviar um e-mail, mensagem no WhatsApp/Telegram, etc. quando o preço de
   alguma marca cair.

## Estrutura dos arquivos

```
cerveja_monitor/
├── config.py            # marcas monitoradas, CEP, sites ativos
├── price_monitor.py      # script principal
├── requirements.txt       # dependências Python
├── agendar_tarefa.ps1    # cria a tarefa agendada no Windows
├── data/                 # CSVs gerados (criado automaticamente)
│   ├── precos_AAAAMMDD.csv      # snapshot do dia
│   └── historico_completo.csv   # histórico acumulado de todos os dias
└── monitor.log           # log de execução
```

## Observações importantes

- Scraping de sites pode quebrar quando o site muda o layout. Trate este
  script como ponto de partida, não como algo "100% definitivo" -
  revise o `monitor.log` de vez em quando para garantir que ainda está
  encontrando produtos.
- Os preços podem variar por região de entrega (CEP). O parser atual do
  Sonda usa a página pública de categoria, que normalmente mostra o preço
  "padrão" da loja - pode não refletir exatamente o preço final calculado
  com seu CEP/endereço cadastrado.
- Respeite os termos de uso dos sites: o script faz poucas requisições por
  dia com um intervalo entre elas (`DELAY_ENTRE_REQUISICOES` em
  `config.py`), para uso pessoal e moderado.
