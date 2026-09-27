# radar-vagas

Bot que monitora feeds de vagas, filtra pelo perfil desejado e notifica no Telegram. Roda todo dia útil às 9h via GitHub Actions.

## O problema

Alertas de vaga chegam por e-mail em volume alto e a maior parte não é do perfil: cargo sênior, área errada, implantação funcional de ERP. A triagem manual consome tempo todo dia e as vagas boas se perdem no meio.

## A solução

1. Três alertas do Google configurados como feed RSS cobrem vagas publicadas em sites de carreira e agregadores.
2. O script lê os feeds, normaliza o texto (remove acento, tag HTML e caixa alta) e aplica dois filtros: termos obrigatórios e termos de exclusão.
3. O que passa e ainda não foi enviado vai para o Telegram com título e link direto.
4. O histórico de itens já enviados é versionado no próprio repositório, o que evita notificação repetida.

## Como rodar

### Local

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="seu_token"
export TELEGRAM_CHAT_ID="seu_chat_id"
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

## Configuração

Toda a regra de negócio está em `config.yml`, fora do código:

```yaml
feeds:      # URLs dos feeds RSS
incluir:    # precisa conter ao menos um destes termos
excluir:    # descarta se contiver qualquer um destes
```

Ajustar o filtro não exige mexer em Python.

## Decisões técnicas

**Feed RSS em vez de scraping.** LinkedIn, Gupy e Indeed bloqueiam scraping e mudam o HTML com frequência, o que tornaria a coleta instável e violaria os termos de uso. Feed RSS é um contrato estável e público.

**Regra em YAML, fora do código.** O filtro muda toda semana no começo, conforme o ruído aparece. Separar configuração de lógica evita commit de código para cada ajuste de palavra-chave.

**Histórico em arquivo versionado em vez de banco.** O volume é de dezenas de itens por dia e o estado precisa sobreviver entre execuções de um runner efêmero. Um JSON commitado pelo próprio workflow resolve sem infraestrutura adicional. A lista é truncada nos 800 registros mais recentes para o arquivo não crescer indefinidamente.

**Normalização antes do filtro.** Vagas vêm com acentuação inconsistente e HTML embutido. Comparar texto normalizado evita que "implantação" e "implantacao" sejam tratados como termos diferentes.

**Link limpo.** O Google Alerts embrulha o destino em uma URL de redirecionamento. O script extrai o link real antes de notificar.

## Próximos passos

- [ ] Testes com pytest no módulo de filtro
- [ ] Pontuação de aderência por quantidade de termos encontrados
- [ ] Provisionamento com Terraform para rodar em instância própria
- [ ] Métricas de volume diário com Prometheus e Grafana
