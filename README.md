# radar-vagas

Bot que monitora feeds de vagas, filtra pelo perfil desejado e notifica no Telegram. Roda todo dia útil às 9h via GitHub Actions.

## O problema

Alertas de vaga chegam por e-mail em volume alto e a maior parte não é do perfil: cargo sênior, área errada, implantação funcional de ERP. A triagem manual consome tempo todo dia e as vagas boas se perdem no meio.

## A solução

Duas fontes alimentam o mesmo filtro:

1. **Feeds RSS** — três alertas do Google configurados como feed cobrem vagas publicadas em sites de carreira.
2. **Gmail via IMAP** — os alertas de LinkedIn, Indeed, Glassdoor e Gupy caem numa etiqueta própria; o script lê apenas os não lidos, extrai os links de vaga do HTML e marca como lido o que processou.

Em seguida o script normaliza o texto (remove acento, tag HTML e caixa alta) e aplica dois filtros: termos obrigatórios e termos de exclusão.
3. O que passa e ainda não foi enviado vai para o Telegram com título e link direto.
4. O histórico de itens já enviados é versionado no próprio repositório, o que evita notificação repetida.

## Como rodar

### Local

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="seu_token"
export TELEGRAM_CHAT_ID="seu_chat_id"
export GMAIL_USER="seu_email@gmail.com"
export GMAIL_APP_PASSWORD="senha_de_app_de_16_caracteres"
python src/radar.py
```

### Docker

```bash
docker build -t radar-vagas .
docker run --rm \
  -e TELEGRAM_TOKEN="seu_token" \
  -e TELEGRAM_CHAT_ID="seu_chat_id" \
  radar-vagas
```

### GitHub Actions

O workflow roda de segunda a sexta às 12h UTC (9h em São Paulo) e também pode ser disparado manualmente pela aba Actions. As credenciais ficam em repository secrets, nunca no código.

## Modo diagnóstico

Para calibrar o filtro sem disparar notificação: na aba Actions, ao rodar o workflow manualmente, marque a opção **diagnostico**. O job lê as duas fontes e imprime no log todas as vagas encontradas, separadas em aprovadas e descartadas, com o termo que decidiu cada caso. Nada é enviado ao Telegram e o histórico não é gravado, então dá para repetir quantas vezes for preciso.

Local:

```bash
MODO_DIAGNOSTICO=true python src/radar.py
```

## Configuração

Toda a regra de negócio está em `config.yml`, fora do código:

```yaml
feeds:      # URLs dos feeds RSS
incluir:    # precisa conter ao menos um destes termos
excluir:    # descarta se contiver qualquer um destes
```

Ajustar o filtro não exige mexer em Python.

## Decisões técnicas

**IMAP em vez da API do Gmail.** A API exigiria fluxo OAuth com refresh token, o que significa um servidor para o callback ou um token de longa duração no repositório. IMAP com senha de app resolve o mesmo problema de leitura com uma credencial revogável, escopo restrito à caixa e nenhuma infraestrutura extra. Para escrita ou uso por terceiros a escolha seria outra.

**Marcar como lido só depois de processar.** O fetch usa `BODY.PEEK[]`, que não altera a flag. A marcação acontece ao final, apenas para as mensagens lidas sem erro — se o job falhar no meio, nada é perdido na próxima execução.

**Feed RSS em vez de scraping.** LinkedIn, Gupy e Indeed bloqueiam scraping e mudam o HTML com frequência, o que tornaria a coleta instável e violaria os termos de uso. Feed RSS é um contrato estável e público.

**Regra em YAML, fora do código.** O filtro muda toda semana no começo, conforme o ruído aparece. Separar configuração de lógica evita commit de código para cada ajuste de palavra-chave.

**Histórico em arquivo versionado em vez de banco.** O volume é de dezenas de itens por dia e o estado precisa sobreviver entre execuções de um runner efêmero. Um JSON commitado pelo próprio workflow resolve sem infraestrutura adicional. A lista é truncada nos 800 registros mais recentes para o arquivo não crescer indefinidamente.

**Normalização antes do filtro.** Vagas vêm com acentuação inconsistente e HTML embutido. Comparar texto normalizado evita que "implantação" e "implantacao" sejam tratados como termos diferentes.

**Link limpo.** O Google Alerts embrulha o destino em uma URL de redirecionamento. O script extrai o link real antes de notificar.

## Próximos passos

- [x] Leitura dos alertas de e-mail via IMAP
- [ ] Testes com pytest no módulo de filtro
- [ ] Pontuação de aderência por quantidade de termos encontrados
- [ ] Provisionamento com Terraform para rodar em instância própria
- [ ] Métricas de volume diário com Prometheus e Grafana
