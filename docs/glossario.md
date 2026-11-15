# Glossário de Fundamentos de GenAI Aplicada à Nuvem (Etapa 1)

Este glossário reúne 10 conceitos fundamentais de Inteligência Artificial Generativa aplicados à computação em nuvem, conectando cada termo a um serviço AWS trabalhado na disciplina **AG822**.

---

## 1. Modelo de Fundação (*Foundation Model* — FM) e LLM
- **Definição:** Modelo de inteligência artificial de grande escala, pré-treinado em vastos volumes de dados não rotulados, capaz de ser adaptado para múltiplas tarefas (resumo, tradução, geração de código, classificação) sem necessidade de treinar uma rede neural do zero. Quando focado em texto e código, é chamado de *Large Language Model* (LLM).
- **Exemplo ligado à AWS (AG822):** No **Amazon Bedrock**, consumimos modelos de fundação como *Anthropic Claude 3 Haiku* ou *Meta Llama 3* por meio de uma chamada de API (`bedrock-runtime:Converse`), sem provisionar servidores **Amazon EC2** com GPUs.

## 2. Token
- **Definição:** Unidade básica de processamento de texto de um LLM (correspondendo, em média, a cerca de 3 a 4 caracteres ou três quartos de uma palavra em português). Tanto o texto enviado (*input*) quanto o texto gerado (*output*) são contabilizados em tokens, que determinam o custo financeiro e o consumo computacional da inferência.
- **Exemplo ligado à AWS (AG822):** Na Etapa 4, a função **AWS Lambda** lê `resp["usage"]["inputTokens"]` e `resp["usage"]["outputTokens"]` devolvidos pelo **Amazon Bedrock** e grava esses contadores em uma tabela do **Amazon DynamoDB** para auditoria de custos (Unidade II).

## 3. Prompt e *System Prompt* (Instrução de Sistema)
- **Definição:** O *prompt* é a instrução ou pergunta enviada pelo usuário ou aplicação ao modelo. O *System Prompt* é uma instrução de mais alto nível passada separadamente da mensagem do usuário para definir o papel, o tom, as restrições de segurança e o formato de saída (como exigir resposta exclusivamente em JSON).
- **Exemplo ligado à AWS (AG822):** Na função **AWS Lambda** da Etapa 4, usamos o campo `system=[{"text": "Responda só em JSON..."}]` da API `Converse` do **Amazon Bedrock** para garantir que a saída possa ser convertida com `json.loads()` antes de ser salva no **Amazon DynamoDB**.

## 4. Janela de Contexto (*Context Window*)
- **Definição:** Quantidade máxima de tokens (somando *System Prompt*, histórico de conversa, documentos anexados, definições de ferramentas e resposta gerada) que um modelo consegue processar em uma única requisição.
- **Exemplo ligado à AWS (AG822):** Ao processar arquivos grandes armazenados no **Amazon S3**, enviar um log inteiro de 50 MB diretamente para o **Amazon Bedrock** estouraria a janela de contexto e elevaria drasticamente o custo; por isso, filtramos ou quebramos os dados em partes menores na **AWS Lambda**.

## 5. Temperatura (*Temperature*) e Parâmetros de Inferência
- **Definição:** Hiperparâmetro (geralmente entre `0.0` e `1.0`) que controla a aleatoriedade na escolha dos próximos tokens pelo modelo. Valores próximos de `0` tornam a saída mais determinística e previsível, enquanto valores mais altos estimulam variações criativas.
- **Exemplo ligado à AWS (AG822):** Em automações de infraestrutura e triagem de incidentes via **Amazon Bedrock**, configuramos `inferenceConfig={"maxTokens": 300, "temperature": 0}` dentro da **AWS Lambda** para obter classificações consistentes de urgência (`baixa`, `media`, `alta`).

## 6. Alucinação (*Hallucination*)
- **Definição:** Fenômeno em que um LLM gera informações factuais incorretas, parâmetros inexistentes de API ou nomes de serviços inventados com aparência gramaticalmente confiável e plausível.
- **Exemplo ligado à AWS (AG822):** Ao pedir a um assistente de IA um template do **AWS CloudFormation** para criar uma **Amazon VPC** e uma instância **Amazon EC2** (Unidades V e VI), o modelo pode inventar uma propriedade YAML inexistente ou um ID de AMI (`ami-12345678`) inválido para a região `us-east-1`, exigindo validação com `cfn-lint`.

## 7. RAG (*Retrieval-Augmented Generation* — Geração Aumentada por Recuperação)
- **Definição:** Técnica arquitetural em que o sistema primeiro busca trechos relevantes em uma base de conhecimento confiável e atualizada (documentação oficial, banco vetorial ou arquivos corporativos) e os injeta no contexto do prompt antes de o modelo gerar a resposta.
- **Exemplo ligado à AWS (AG822):** Na Etapa 2, quando o assistente consulta o servidor MCP de documentação oficial da AWS antes de responder sobre **Security Groups** e **NACLs** (Unidade V), ele aplica RAG sobre a documentação da AWS para não depender apenas da memória estática do treinamento.

## 8. *Tool Use* (Uso de Ferramentas / *Function Calling*)
- **Definição:** Capacidade de um LLM analisar uma solicitação, decidir qual função externa declarada no parâmetro `toolConfig` deve ser chamada e gerar um objeto JSON estruturado com os argumentos para que o código da aplicação execute a ação e devolva o resultado (`toolResult`).
- **Exemplo ligado à AWS (AG822):** Na Etapa 5, o modelo acessado via **Amazon Bedrock** solicita a execução da ferramenta `ler_metricas`, que no código Python chama `cloudwatch.get_metric_statistics()` no **Amazon CloudWatch** para inspecionar o uso de CPU de um grupo de **EC2 Auto Scaling**.

## 9. Agente de IA (*AI Agent*)
- **Definição:** Sistema autônomo ou semiautônomo que utiliza um LLM como motor de raciocínio em um laço iterativo (*perceber -> raciocinar -> chamar ferramenta -> observar resultado*), escolhendo dinamicamente quais ferramentas invocar e em que ordem para atingir um objetivo operacional.
- **Exemplo ligado à AWS (AG822):** Na Etapa 5, nosso agente investiga um alarme de CPU alta consultando o **Amazon CloudWatch** e o **EC2 Auto Scaling**, operando sob uma política restrita do **AWS IAM** (Unidade IV) e registrando cada passo no **Amazon CloudWatch Logs**.

## 10. MCP (*Model Context Protocol*)
- **Definição:** Protocolo aberto que padroniza a comunicação entre clientes/assistentes de IA (como VS Code, Kiro ou Cursor) e servidores externos que fornecem contexto, documentação e ferramentas de execução sobre APIs e bancos de dados.
- **Exemplo ligado à AWS (AG822):** Conectamos o VS Code aos servidores `awslabs.aws-documentation-mcp-server` (via `stdio`) e `aws-knowledge` (via HTTP remoto) para auditar configurações de **AWS IAM**, **Amazon VPC** e **AWS CloudFormation** com base na documentação oficial vigente.
