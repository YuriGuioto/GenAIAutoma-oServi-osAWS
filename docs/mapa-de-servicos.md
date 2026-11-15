# Mapa de Serviços de GenAI na AWS, Emulação no Floci e Protocolo MCP (Etapa 1)

---

## 1. Os Três Papéis da IA Generativa na Nuvem

| Papel da IA | O que faz | Serviço AWS de Referência | Etapa no Roteiro |
| :--- | :--- | :--- | :--- |
| **Assistente** | Apoia o engenheiro humano a escrever código, consultar documentação, gerar templates IaC e diagnosticar problemas no terminal/IDE. | **Kiro** (IDE e CLI — sucessor do Amazon Q Developer) | Etapas 2 e 3 |
| **Componente** | É chamado por dentro do código da aplicação (via SDK `boto3`) como parte de um pipeline orientado a eventos para transformar, resumir ou classificar dados. | **Amazon Bedrock** (`bedrock-runtime` API `Converse`) | Etapa 4 |
| **Agente** | Decide autonomamente, em um laço de raciocínio, quais ferramentas de leitura e escrita invocar na infraestrutura, governado por IAM e aprovação humana. | **Amazon Bedrock AgentCore** | Etapa 5 |

---

## 2. Classificação em IaaS, PaaS ou SaaS (Competência 93)

### 2.1. Amazon Bedrock — **PaaS (*Platform as a Service*) / Serverless Model-as-a-Service**
- **Classificação:** **PaaS** (Plataforma como Serviço).
- **Justificativa técnica:** O desenvolvedor não gerencia máquinas virtuais, GPUs, drivers CUDA, sistema operacional nem escalonamento de clusters de inferência (o que seria IaaS, como uma instância EC2 `g5.xlarge`). Por outro lado, o Bedrock também não é um software pronto para o usuário final corporativo (SaaS): ele entrega uma **plataforma de APIs e SDKs** (`Converse`, `InvokeModel`, *Knowledge Bases*, *Guardrails*) para que engenheiros construam suas próprias aplicações em cima.

### 2.2. Amazon Bedrock AgentCore — **PaaS (*Platform as a Service*)**
- **Classificação:** **PaaS** (Plataforma como Serviço especializada em execução de agentes).
- **Justificativa técnica:** Fornece a camada gerenciada de tempo de execução (*Runtime*), gerenciamento de sessão/memória, identidade de agentes, observabilidade e governança para que desenvolvedores hospedem e operem agentes de código sem administrar servidores subjacentes, mas ainda exigindo que a equipe desenvolva a lógica do agente, suas ferramentas e políticas IAM.

### 2.3. Kiro (IDE e CLI, sucessor do Amazon Q Developer) — **SaaS (*Software as a Service*)**
- **Classificação:** **SaaS** (Software como Serviço).
- **Justificativa técnica:** É uma aplicação pronta para uso direto pelo profissional (engenheiro de software/nuvem), consumida mediante assinatura/licença por usuário, sem que o cliente precise programar o modelo, hospedar infraestrutura ou gerenciar APIs de inferência.

---

## 3. Tabela de Emulação no Floci vs. AWS Real

> **⚠ Verificar:** Consulte a página de serviços suportados na documentação oficial do Floci (`https://floci.io`) caso utilize uma versão mais recente da imagem `floci/floci:latest`, pois novos recursos são adicionados continuamente.

| Serviço / Recurso | Papel no Roteiro | Nível de Emulação no Floci | O que funciona no Floci e o que difere da AWS real |
| :--- | :--- | :--- | :--- |
| **Amazon Bedrock Runtime (`Converse` / `ConverseStream`)** | Componente e Agente | **Parcial** | No modo `proxy`, traduz e repassa chamadas `Converse` (incluindo `toolConfig` / *tool use*) para um endpoint compatível com OpenAI (Ollama). `InvokeModel` retorna resposta fixa (*stub*) e a listagem do plano de controle não reflete o catálogo real da AWS. |
| **Amazon Bedrock AgentCore** | Agente (Plano de Controle) | **Parcial** | Emula apenas o registro de recursos no plano de controle (ex.: `AWS::BedrockAgentCore::Runtime` no CloudFormation fica `READY`), mas **não executa** agentes de fato. |
| **Kiro (IDE / CLI)** | Assistente | **Não emulado** | É uma ferramenta cliente/SaaS da AWS usada na máquina do desenvolvedor; pode apontar comandos locais para o Floci se `AWS_PROFILE=floci` estiver definido. |
| **Agent Toolkit for AWS (AWS MCP Server gerenciado)** | Ponte | **Não emulado** | Serviço gerenciado que opera exclusivamente sobre contas reais da AWS com registro no CloudTrail. |
| **`awslabs/mcp` (Servidores MCP Open Source)** | Ponte (Aberta) | **Completo (externo ao Floci)** | Roda localmente na máquina do aluno via `uvx` (`stdio`) ou conecta ao endpoint público de documentação (`aws-knowledge`). Servidores locais de IaC funcionam com `AWS_PROFILE=floci`. |
| **AWS Lambda** | Computação Serverless | **Completo (para o roteiro)** | Executa funções em containers Docker reais via `/var/run/docker.sock` e injeta `AWS_ENDPOINT_URL` automaticamente quando `FLOCI_HOSTNAME=floci`. Atenção ao timeout padrão de 3 s. |
| **Amazon S3 e S3 Event Notifications** | Armazenamento e Gatilho | **Completo (para o roteiro)** | Criação de buckets, upload/download de objetos e disparo de eventos `s3:ObjectCreated:*` para funções Lambda funcionam como esperado. |
| **Amazon DynamoDB** | Banco NoSQL | **Completo (para o roteiro)** | Criação de tabelas (`create-table`), `put-item`, `scan` e `get-item` totalmente suportados. |
| **Amazon CloudWatch (Métricas, Alarmes e Logs)** | Observabilidade | **Parcial** | Armazena métricas enviadas com `put-metric-data`, avalia alarmes (`put-metric-alarm`), dispara notificações SNS e grava grupos/streams de logs. Não coleta métricas reais de hardware EC2 sozinho. |
| **EC2 Auto Scaling** | Elasticidade | **Parcial** | Cria *Launch Configurations* e grupos de Auto Scaling, reconciliando a capacidade desejada a cada ~10 segundos com instâncias EC2 emuladas. |
| **AWS IAM** | Segurança e Controle de Acesso | **Parcial (Opt-in)** | Só avalia políticas IAM e bloqueia ações não autorizadas quando a variável `FLOCI_SERVICES_IAM_ENFORCEMENT_ENABLED=true` está ativa no container. Na AWS real, a avaliação é sempre obrigatória. |

### Por que um emulador consegue imitar a API do Bedrock, mas não a qualidade de um modelo grande?
Imitar a API HTTP/JSON do Bedrock Runtime (`POST /model/{modelId}/converse`) é um problema determinístico de engenharia de software: basta receber o contrato JSON documentado pela AWS, validar os campos (`messages`, `system`, `inferenceConfig`, `toolConfig`), traduzi-los para o formato OpenAI `/v1/chat/completions` e converter a resposta de volta. Já a **qualidade cognitiva da resposta** (capacidade de seguir instruções complexas, não errar formatação JSON e raciocinar em múltiplas etapas) depende da quantidade de parâmetros (bilhões ou trilhões) e do treinamento do modelo de linguagem subjacente, exigindo dezenas de gigabytes de VRAM em GPUs dedicadas que não cabem em um notebook comum rodando um modelo compacto de 3 bilhões de parâmetros (`llama3.2` ou `qwen2.5:3b`).

---

## 4. Diferença entre Servidor MCP Local (`stdio`) e Remoto (em 5 linhas)

1. O **servidor MCP local (`stdio`)** roda como um subprocesso na própria máquina do usuário (iniciado por comandos como `uvx` ou `npx`), comunicando-se com o IDE via entrada e saída padrão (*stdin/stdout*).
2. Por rodar localmente, o servidor `stdio` tem acesso direto a arquivos do projeto, variáveis de ambiente locais (`AWS_PROFILE=floci`) e à rede local (`localhost:4566`), mas consome CPU/RAM da máquina do desenvolvedor.
3. Já o **servidor MCP remoto (HTTP / Streamable HTTP / SSE)** roda hospedado em nuvem e é acessado pelo cliente de IA por meio de uma URL HTTPS (como `https://knowledge-mcp.global.api.aws`).
4. O servidor remoto dispensa instalação de dependências locais (`python`, `uv`, `node`) e está sempre atualizado pelo provedor, porém não enxerga serviços em `localhost` da máquina do usuário.
5. Em resumo: usa-se MCP **remoto** para consultar bases públicas/centralizadas de conhecimento e MCP **`stdio` local** quando a ferramenta precisa ler arquivos locais ou interagir com emuladores locais como o Floci.

---

## 5. Resposta da Pergunta de Checagem (Etapa 1)

> **Pergunta:** *Se um modelo responde com o nome de um serviço AWS que não existe, que técnica desta etapa reduziria o problema e por quê?*

**Resposta:**
A técnica que reduziria drasticamente esse problema é o **RAG (*Retrieval-Augmented Generation* — Geração Aumentada por Recuperação)**, operacionalizado na prática para assistentes de código pelo uso de um **servidor MCP conectado à documentação oficial da AWS** (como o `aws-documentation-mcp-server` ou o `aws-knowledge`).
**Por quê:** Um LLM responde por padrão com base nos pesos probabilísticos do seu treinamento estático, o que o leva a "alucinar" nomes de serviços ou combinar termos parecidos quando não tem certeza. Com o RAG via MCP, antes de o modelo formular a resposta, uma ferramenta faz uma busca semântica/textual na documentação oficial vigente da AWS e injeta os trechos reais na janela de contexto do prompt, ancorando (*grounding*) a geração nos serviços que realmente existem.
