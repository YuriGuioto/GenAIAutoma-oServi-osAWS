# GenAI na Automação de Serviços AWS (Ambiente Floci)

Repositório de autoestudo prático da disciplina **AG822 — Computação em Nuvem** (Engenharia de Computação — UNAERP).
Todo o projeto executa localmente sobre o emulador open source **Floci** (`http://localhost:4566`) integrado ao **Ollama** (`llama3.2`), reproduzindo chamadas da AWS CLI v2 e `boto3` sem custo e sem risco em conta real.

## Arquitetura dos 3 Papéis da IA Generativa na Nuvem

1. **Assistente (Etapas 2 e 3):** Apoia o engenheiro na consulta à documentação oficial via MCP (`awslabs/mcp`), inventário de recursos e geração/auditoria de templates CloudFormation.
2. **Componente (Etapa 4):** Invocado programaticamente dentro de uma arquitetura orientada a eventos (`S3 -> Lambda -> Bedrock Runtime Converse -> DynamoDB`) para resumir e classificar relatórios de campo.
3. **Agente (Etapa 5):** Raciocina em laço (*ReAct / Tool Use*) sobre alarmes do CloudWatch e grupos de Auto Scaling, sujeito a menor privilégio no IAM, limite de iterações, aprovação humana para escrita e trilha de auditoria no CloudWatch Logs.

## Checagem Obrigatória de Segurança

Antes de rodar qualquer comando, configure o perfil `floci` em `~/.aws/config` e valide:

```bash
export AWS_PROFILE=floci
aws sts get-caller-identity
```

A saída **deve** exibir `"Account": "000000000000"`.

## Como Subir o Ambiente Base (Etapa 0)

```bash
docker compose up -d
docker compose exec ollama ollama pull llama3.2
```

## Estrutura de Documentação e Entregas

- [`GUIA_DE_COMMITS.md`](GUIA_DE_COMMITS.md) — Guia passo a passo commit por commit do projeto completo.
- [`docs/glossario.md`](docs/glossario.md) — Glossário com 10 termos fundamentais de GenAI ligados a serviços AWS.
- [`docs/mapa-de-servicos.md`](docs/mapa-de-servicos.md) — Classificação IaaS/PaaS/SaaS, matriz de emulação do Floci e comparativo MCP.
- [`docs/diario-de-prompts.md`](docs/diario-de-prompts.md) — Registro real de prompts, respostas da IA, erros detectados e correções humanas.
- [`docs/revisao-iac.md`](docs/revisao-iac.md) — Auditoria de segurança e boas práticas do template CloudFormation (`infra/vpc.yaml`).
- [`docs/relatorio-custo-riscos.md`](docs/relatorio-custo-riscos.md) — Análise financeira por token, segurança contra *Prompt Injection*, LGPD e TI Verde.
- [`docs/roteiro-apresentacao.md`](docs/roteiro-apresentacao.md) — Roteiro de 10 minutos para apresentação e demonstração do Projeto Integrador.
