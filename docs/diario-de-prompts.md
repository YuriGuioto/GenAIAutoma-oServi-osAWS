# Diário de Prompts e Auditoria Crítica da IA

> **Instrução de preenchimento:** Este diário deve ser preenchido **por você** ao longo das Etapas 2 a 6 e do Projeto Integrador com os prompts reais enviados ao assistente, o resumo do que a IA respondeu, os erros ou omissões que você identificou e a correção aplicada antes de executar.

---

## 1. Registro de Interações com o Assistente de IA

| Etapa | Atividade | Prompt Enviado (exato) | Resumo da Resposta da IA | Erro / Omissão Encontrado na Resposta da IA | Correção Aplicada por Mim |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **Etapa 2** | Comparação Security Group vs. NACL (**SEM** MCP ativo) | *(Preencher com seu prompt)* | *(Preencher com o resumo da resposta)* | *(Preencher com o que faltou ou foi impreciso)* | *(Preencher com sua correção)* |
| **Etapa 2** | Comparação Security Group vs. NACL (**COM** `#aws-docs #aws-knowledge`) | *(Preencher com seu prompt)* | *(Preencher com o resumo da resposta e páginas citadas)* | *(Preencher com sua análise)* | *(Preencher com sua correção)* |
| **Etapa 2** | Geração do script de inventário (`boto3`) | *(Preencher com seu prompt)* | *(Preencher com o resumo da resposta)* | *(Verificar se a IA colocou endpoint hardcoded ou esqueceu o perfil Floci)* | *(Preencher com sua correção)* |
| **Etapa 2** | Geração da política IAM de menor privilégio (`relatorios`) | *(Preencher com seu prompt)* | *(Preencher com o resumo da resposta)* | *(Verificar se a IA usou `s3:*` ou `Resource: "*"`)* | *(Preencher com sua correção)* |
| **Etapa 3** | Geração do template CloudFormation (`infra/vpc.yaml`) | *(Preencher com sua especificação de até 10 linhas)* | *(Preencher com o resumo do template gerado)* | *(Anotar portas abertas, AMI fixa, ausência de tags/Outputs)* | *(Preencher com sua correção)* |
| **Etapa 4** | Tratamento de JSON inválido na Lambda (`src/triagem/app.py`) | *(Preencher com seu prompt)* | *(Preencher com o resumo da resposta)* | *(Preencher com o erro encontrado)* | *(Preencher com sua correção)* |
| **Etapa 5** | Definição de `toolConfig` e System Prompt do Agente | *(Preencher com seu prompt)* | *(Preencher com o resumo da resposta)* | *(Preencher com o erro encontrado)* | *(Preencher com sua correção)* |
| **Etapa 6** | Mitigação de *Prompt Injection* e revisão da Role da Lambda | *(Preencher com seu prompt)* | *(Preencher com o resumo da resposta)* | *(Preencher com o erro encontrado)* | *(Preencher com sua correção)* |
| **Integrador** | Automação de alertas de irrigação (Agronegócio) | *(Preencher com seu prompt)* | *(Preencher com o resumo da resposta)* | *(Preencher com o erro encontrado)* | *(Preencher com sua correção)* |

---

## 2. Análise Obrigatória da Etapa 2

### 2.1. O que mudou na explicação de Security Group vs. NACL com e sem os servidores MCP de documentação?
- **Sem MCP:** *(Anote aqui o que você observou ao rodar sem o MCP ativo)*
- **Com MCP (`#aws-docs #aws-knowledge`):** *(Anote aqui quais chamadas de ferramenta como `search_documentation` apareceram e quais detalhes técnicos oficiais foram acrescentados)*

### 2.2. O que aconteceria se o script de inventário esquecesse o endpoint/perfil do Floci em uma máquina com credenciais reais configuradas?
Quando um script `boto3` ou comando AWS CLI é executado sem `AWS_PROFILE=floci` (e sem `AWS_ENDPOINT_URL`), a cadeia padrão de resolução de credenciais do SDK busca o perfil `[default]` em `~/.aws/credentials` ou variáveis de ambiente (`AWS_ACCESS_KEY_ID`) e envia todas as requisições para os endpoints reais da AWS (`s3.amazonaws.com`, `dynamodb.us-east-1.amazonaws.com`, `iam.amazonaws.com`). Em operações de leitura (`list_buckets`), isso exporia dados reais de produção/laboratório; já em scripts de criação, alteração ou limpeza (`delete-bucket`, `terminate-instances`), causaria destruição de recursos reais ou cobrança financeira imediata na conta AWS.
