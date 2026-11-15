#!/usr/bin/env bash
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-floci}"
CONTA="000000000000"
FUNC_INTEGRADOR="triagem-irrigacao"
ROLE_NAME="triagem-lambda"

echo "======================================================================"
echo " SUBINDO PROJETO INTEGRADOR COMPLETO NO FLOCI (AGRONEGÓCIO IRRIGAÇÃO)"
echo "======================================================================"

echo "=== 1. Garantindo que os containers Floci e Ollama estão ativos ==="
docker compose up -d

echo "=== 2. Validando conta 000000000000 no Floci ==="
CONTA_ATUAL=$(aws sts get-caller-identity --query "Account" --output text)
if [ "$CONTA_ATUAL" != "$CONTA" ]; then
  echo "ERRO DE SEGURANÇA: Conta ($CONTA_ATUAL) não é o Floci ($CONTA)."
  exit 1
fi

echo "=== 3. Validando e implantando a stack CloudFormation 'integrador-agro' ==="
cfn-lint infra/integrador.yaml
aws cloudformation deploy \
  --template-file infra/integrador.yaml \
  --stack-name integrador-agro

echo "=== 4. Garantindo Role IAM e Permissões para a Lambda '${FUNC_INTEGRADOR}' ==="
ASSUME_ROLE_POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document "$ASSUME_ROLE_POLICY" >/dev/null 2>&1 || true

POLITICA_INTEGRADOR=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::alertas-irrigacao/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem", "dynamodb:Scan"],
      "Resource": "arn:aws:dynamodb:us-east-1:${CONTA}:table/alertas-irrigacao-ddb"
    },
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:Converse"],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:us-east-1:${CONTA}:log-group:/aws/lambda/${FUNC_INTEGRADOR}:*"
    }
  ]
}
EOF
)

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "IntegradorIrrigacaoPermissions" \
  --policy-document "$POLITICA_INTEGRADOR"

echo "=== 5. Empacotando e implantando a Lambda '${FUNC_INTEGRADOR}' (timeout 120s) ==="
python3 -c "
import zipfile
with zipfile.ZipFile('funcao_integrador.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write('src/integrador/lambda_alerta.py', arcname='lambda_alerta.py')
"

if aws lambda get-function --function-name "$FUNC_INTEGRADOR" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FUNC_INTEGRADOR" --zip-file fileb://funcao_integrador.zip >/dev/null
else
  aws lambda create-function \
    --function-name "$FUNC_INTEGRADOR" \
    --runtime python3.12 \
    --handler lambda_alerta.handler \
    --zip-file fileb://funcao_integrador.zip \
    --timeout 120 \
    --role "arn:aws:iam::${CONTA}:role/${ROLE_NAME}" \
    --environment "Variables={TABELA_ALERTAS=alertas-irrigacao-ddb}" >/dev/null
fi

NOTIF_INTEGRADOR=$(cat <<EOF
{
  "LambdaFunctionConfigurations": [
    {
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:${CONTA}:function:${FUNC_INTEGRADOR}",
      "Events": ["s3:ObjectCreated:*"]
    }
  ]
}
EOF
)

aws s3api put-bucket-notification-configuration \
  --bucket alertas-irrigacao \
  --notification-configuration "$NOTIF_INTEGRADOR"

echo "=== 6. Enviando os 3 alertas de sensores de irrigação para s3://alertas-irrigacao/ ==="
for ARQ in sensor-pivo-01.json sensor-pivo-02.json sensor-pivo-03.json; do
  echo " -> Enviando ${ARQ}..."
  aws s3 cp "exemplos/alertas-irrigacao/${ARQ}" "s3://alertas-irrigacao/${ARQ}"
  sleep 15
done

echo "=== 7. Consultando alertas classificados na tabela DynamoDB 'alertas-irrigacao-ddb' ==="
aws dynamodb scan \
  --table-name alertas-irrigacao-ddb \
  --query "Items[].{ID:id_alerta.S,Equipamento:equipamento.S,Urgencia:urgencia.S,Resumo:resumo_tecnico.S}" \
  --output table

echo "=== 8. Gerando Resumo Diário via Bedrock e enviando para SNS -> SQS ==="
python3 src/integrador/resumo_diario.py

echo "=== 9. Lendo o Boletim Diário recebido na fila SQS do Engenheiro Agrônomo ==="
URL_FILA=$(aws sqs get-queue-url --queue-name fila-engenheiro-agronomo --query "QueueUrl" --output text)
aws sqs receive-message --queue-url "$URL_FILA" --max-number-of-messages 1 --output json

echo ""
echo "[SUCESSO] Fluxo automático concluído! Para demonstrar o Agente interativo com aprovação humana, rode:"
echo "  python3 src/integrador/agente_irrigacao.py"
