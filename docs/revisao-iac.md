# Relatório de Auditoria de IaC Gerada por IA (Etapa 3)

---

## 1. Especificação em Linguagem Natural Usada no Prompt (até 10 linhas)

> Crie um template AWS CloudFormation em YAML (`infra/vpc.yaml`) para a região `us-east-1` contendo:
> 1. Uma VPC (`10.0.0.0/16`) com suporte a DNS, Internet Gateway, sub-rede pública (`10.0.1.0/24`) com rota de saída para a internet e sub-rede privada (`10.0.2.0/24`).
> 2. Um Security Group na VPC que libere entrada **apenas** na porta TCP 80 (HTTP) e nada mais.
> 3. Uma instância EC2 `t3.micro` na sub-rede pública com Apache HTTP instalado via `UserData` e AMI Amazon Linux 2023 obtida via parâmetro SSM.
> 4. Um bucket S3 (`relatorios-campo-iac`) com bloqueio de acesso público e uma tabela DynamoDB (`triagem-iac`, chave de partição `arquivo` tipo String, modo `PAY_PER_REQUEST`).
> 5. Inclua tags de custo (`Project` e `CostCenter`) em todos os recursos e `Outputs` com o IP público da EC2, nome do bucket S3 e ARN da tabela DynamoDB.

---

## 2. Checklist de Revisão do Código Gerado pela IA e Problemas Reais Corrigidos

| Item do Checklist | Problema Real Comum no Template Original da IA | Risco na AWS Real | Correção Aplicada em `infra/vpc.yaml` |
| :--- | :--- | :--- | :--- |
| **1. Security Group libera `0.0.0.0/0` em porta diferente de 80/443?** | Modelos de linguagem frequentemente adicionam por hábito uma regra `FromPort: 22, ToPort: 22, CidrIp: 0.0.0.0/0` ("para facilitar o acesso SSH de administração"). | Exposição direta da porta 22 (SSH) para toda a internet, sujeita a ataques de força bruta e exploração de credenciais. Na AWS real, o acesso administrativo deve usar **AWS Systems Manager Session Manager**. | Removida qualquer regra de porta 22. Mantida exclusivamente a regra de entrada TCP `80` (`HTTP`) com descrição explícita. |
| **2. A AMI está fixa (hardcoded) ou vem de parâmetro SSM?** | Sem instrução explícita (e às vezes mesmo com ela), a IA insere um ID fixo antigo como `ImageId: ami-0c55b159cbfafe1f0` (que pertence a outra região ou já foi depreciado). | Falha imediata no deploy (`InvalidAMIID.NotFound`) na AWS real ou uso de imagem desatualizada com vulnerabilidades de kernel. | Declarado o parâmetro `LatestAmiId` do tipo `AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>` apontando para `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64`. |
| **3. Existem `Outputs` úteis?** | Templates gerados rapidamente costumam omitir a seção `Outputs:` ou exportar apenas o ID da VPC, esquecendo atributos derivados com `!GetAtt`. | Dificulta a automação pós-deploy e a integração com scripts que precisam do ARN da tabela ou do IP público da instância. | Adicionados 4 `Outputs`: `VpcId` (`!Ref LabVPC`), `WebServerPublicIp` (`!GetAtt WebServerInstance.PublicIp`), `BucketNameOutput` (`!Ref RelatoriosBucket`) e `DynamoDBTableArn` (`!GetAtt TriagemTable.Arn`). |
| **4. Há tags para identificar custo por projeto (Unidade II)?** | A IA costuma colocar apenas a tag `Name` na VPC e na EC2, omitindo tags financeiras no S3, DynamoDB e Security Group. | Impossibilita rastrear gastos no **AWS Cost Explorer** por projeto ou centro de custo (Unidade II — FinOps). | Adicionadas as tags `Project` e `CostCenter` parametrizadas em todos os recursos suportados. |
| **5. Alucinação de propriedades ou dependências implícitas?** | Dois erros clássicos de IA em CloudFormation: (a) usar `SecurityGroups` (nomes) em vez de `SecurityGroupIds` quando a EC2 está em uma `SubnetId` customizada; (b) esquecer `DependsOn: LabVPCGatewayAttachment` na `AWS::EC2::Route`. | Na AWS real, `SecurityGroups` com `SubnetId` falha na validação da API EC2, e criar a rota `0.0.0.0/0` antes de o IGW estar anexado à VPC gera condição de corrida (`Gateway.NotAttached`). | Usado `SecurityGroupIds: [!GetAtt WebServerSecurityGroup.GroupId]` na EC2 e adicionado `DependsOn: LabVPCGatewayAttachment` no recurso `PublicDefaultRoute`. |
| **6. Comportamento e limitações no Floci** | Parâmetros do tipo `AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>` dependem de que o caminho SSM público exista no emulador, e o atributo `PublicIp` da EC2 emulada é sintético. | No emulador, se o caminho SSM não existir previamente, pode ser necessário criá-lo ou o Floci resolve com valor emulado. | No script de validação, garantimos que o parâmetro SSM `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64` esteja populado no SSM do Floci antes do deploy. |

---

## 3. Resposta da Pergunta de Checagem (Etapa 3)

> **Pergunta:** *Um template que implanta sem erro no Floci está pronto para a AWS real? Cite duas coisas que só a AWS verificaria (pense em cotas, AMIs existentes, permissões e custo).*

**Resposta:**
**Não.** Um template que implanta sem erro no Floci valida apenas a estrutura sintática básica e os recursos emulados localmente, mas **não garante** sucesso nem segurança financeira na AWS real. Quatro exemplos concretos do que só a AWS real verificaria:
1. **Existência real de AMIs e disponibilidade por Zona de Disponibilidade (AZ):** O Floci aceita qualquer string com formato `ami-xxxxxxxx` sem verificar se a imagem realmente existe no catálogo da região `us-east-1`, se é pública/privada ou se sua arquitetura (`x86_64` vs. `arm64`) é compatível com o `InstanceType: t3.micro`. Na AWS real, um ID de AMI inexistente ou de outra região interrompe a stack com `CREATE_FAILED`.
2. **Cotas de Serviço (*Service Quotas*) e Limites da Conta:** A AWS real impõe limites rígidos por região (ex.: máximo padrão de 5 VPCs por região, limite de vCPUs para instâncias sob demanda e limite de Elastic IPs). O Floci não aplica esses limites de conta.
3. **Unicidade Global de Nomes de Buckets S3:** Na AWS real, o namespace do Amazon S3 é global entre todas as contas do mundo; um bucket com nome fixo simples (como `relatorios-campo`) quase certamente falhará com `BucketAlreadyExists`.
4. **Execução Real do `UserData` e Cobrança Contínua:** No Floci, a instância EC2 é apenas um registro emulado no plano de controle (ela não inicializa um kernel Linux real para rodar `dnf install -y httpd` nem gera fatura horária); na AWS real, um erro no script `UserData` deixa a aplicação fora do ar mesmo com a stack `CREATE_COMPLETE`, e a instância gera custo por segundo até ser encerrada.
