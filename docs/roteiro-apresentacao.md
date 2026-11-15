# Roteiro da Apresentação de 10 Minutos — Projeto Integrador (Agronegócio)

**Tema:** Monitoramento e Triagem Inteligente de Sensores de Irrigação em Ribeirão Preto/SP com Amazon Bedrock, S3, Lambda, DynamoDB, CloudWatch e SNS no Ambiente Floci.

---

## Cronograma Minuto a Minuto (10 Minutos)

### Minuto 0:00 – 1:30 | Problema Regional e Arquitetura dos 3 Papéis da IA
- Contextualizar o problema agrícola na região de Ribeirão Preto/SP (cana-de-açúcar, soja e café irrigado): dezenas de pivôs centrais geram telemetria contínua, e falhas hidráulicas sob calor extremo (> 38 °C) exigem resposta imediata.
- Mostrar o diagrama Mermaid do `README.md` / `GUIA_DE_COMMITS.md` destacando como o projeto combina os **3 papéis da IA Generativa**:
  1. **Assistente:** geração e auditoria do CloudFormation (`infra/integrador.yaml`) com MCP e `cfn-lint`.
  2. **Componente:** triagem orientada a eventos (`S3 -> Lambda -> Bedrock -> DynamoDB`) + geração do Boletim Executivo Diário enviado via **Amazon SNS -> Amazon SQS**.
  3. **Agente:** investigação autônoma de alertas críticos e métricas de pressão (`CloudWatch`) com aprovação humana para disparo de ordem de manutenção.

### Minuto 1:30 – 3:00 | Auditoria Crítica da IA e Infraestrutura como Código
- Abrir rapidamente `docs/diario-de-prompts.md` e `docs/revisao-iac.md`.
- Mostrar **2 erros reais** que a IA cometeu durante a geração de código/IaC (ex.: porta 22 aberta no Security Group, AMI hardcoded ou falta de tratamento de JSON inválido de modelos pequenos) e como a equipe revisou e corrigiu.
- Mostrar `cfn-lint infra/integrador.yaml` passando sem erros.

### Minuto 3:00 – 6:00 | Demonstração ao Vivo Parte 1: Fluxo Serverless e Boletim SNS
- Executar `aws sts get-caller-identity` provando que tudo roda na conta `000000000000` (Floci).
- Mostrar a saída de `./scripts/subir-tudo.sh` (ou `make integrador`):
  - Os 3 arquivos JSON (`sensor-pivo-01.json`, `sensor-pivo-02.json` e `sensor-pivo-03.json`) acionam a Lambda `triagem-irrigacao`.
  - Mostrar a tabela `alertas-irrigacao-ddb` preenchida com urgências `baixa`, `media` e `alta` (rompimento de adutora no Pivô 03).
  - Mostrar o Boletim Diário gerado por `src/integrador/resumo_diario.py` e recebido na fila SQS `fila-engenheiro-agronomo` via SNS.

### Minuto 6:00 – 8:30 | Demonstração ao Vivo Parte 2: Agente com IAM Restrito e Aprovação Humana
- Executar `python3 src/integrador/agente_irrigacao.py` (ou `make agente-integrador`).
- Mostrar no terminal o laço ReAct: o agente consulta o DynamoDB, verifica a série de 5 pontos de queda de pressão no CloudWatch e **para pedindo aprovação humana (`[s/N]`)** antes de publicar a Ordem de Manutenção no SNS.
- Mostrar os registros de auditoria gerados no CloudWatch Logs (`aws logs tail /aws/integrador/agente`).

### Minuto 8:30 – 10:00 | Governança: Custos Reais, Segurança (*Prompt Injection*) e TI Verde
- Apresentar os números medidos em `docs/relatorio-custo-riscos.md`:
  - Custo por relatório no Bedrock (< US$ 0,0002) vs. instância EC2 GPU 24h (> US$ 380/mês) e o ponto de equilíbrio (*break-even*).
  - Demonstração rápida do bloqueio de *Prompt Injection* (`scripts/testar-injection.py`) e da política IAM de menor privilégio com `FLOCI_SERVICES_IAM_ENFORCEMENT_ENABLED=true`.
  - Conclusão sobre sustentabilidade (TI Verde) e o que mudaria na AWS real.
