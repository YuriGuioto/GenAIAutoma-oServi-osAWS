#!/usr/bin/env bash
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-floci}"
BUCKET="relatorios-campo"
TABELA="triagem"
ROLE_NAME="triagem-lambda"
FUNC_NAME="triagem"
CONTA="000000000000"

echo "=== 1. Validando identidade no Floci ==="
CONTA_ATUAL=$(aws sts get-caller-identity --query "Account" --output text)
if [ "$CONTA_ATUAL" != "$CONTA" ]; then
  echo "ERRO: Conta detectada ($CONTA_ATUAL) não é o Floci ($CONTA)."
  exit 1
fi

echo "=== 2. Criando bucket S3 '${BUCKET}' e tabela DynamoDB '${TABELA}' ==="
aws s3 mb "s3://${BUCKET}" || true

if ! aws dynamodb describe-table --table-name "$TABELA" >/dev/null 2>&1; then
  aws dynamodb create-table \
    --table-name "$TABELA" \
    --attribute-definitions AttributeName=arquivo,AttributeType=S \
    --key-schema AttributeName=arquivo,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  echo "Tabela '${TABELA}' criada."
fi

echo "=== 3. Criando Role IAM '${ROLE_NAME}' com permissões necessárias ==="
ASSUME_ROLE_POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$ASSUME_ROLE_POLICY" >/dev/null
fi

POLITICA_INICIAL=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::${BUCKET}/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem"],
      "Resource": "arn:aws:dynamodb:us-east-1:${CONTA}:table/${TABELA}"
    },
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:Converse"],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:us-east-1:${CONTA}:log-group:/aws/lambda/${FUNC_NAME}:*"
    }
  ]
}
EOF
)

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "TriagemLambdaPermissions" \
  --policy-document "$POLITICA_INICIAL"

echo "=== 4. Empacotando src/triagem/app.py em funcao.zip ==="
python3 -c "
import zipfile
with zipfile.ZipFile('funcao.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write('src/triagem/app.py', arcname='app.py')
print('Arquivo funcao.zip gerado com sucesso.')
"

echo "=== 5. Criando ou atualizando a função Lambda '${FUNC_NAME}' (timeout 120s) ==="
if aws lambda get-function --function-name "$FUNC_NAME" >/dev/null 2>&1; then
  aws lambda update-function-code \
    --function-name "$FUNC_NAME" \
    --zip-file fileb://funcao.zip >/dev/null
  aws lambda update-function-configuration \
    --function-name "$FUNC_NAME" \
    --timeout 120 \
    --environment "Variables={TABELA=${TABELA}}" >/dev/null
  echo "Função Lambda '${FUNC_NAME}' atualizada."
else
  aws lambda create-function \
    --function-name "$FUNC_NAME" \
    --runtime python3.12 \
    --handler app.handler \
    --zip-file fileb://funcao.zip \
    --timeout 120 \
    --role "arn:aws:iam::${CONTA}:role/${ROLE_NAME}" \
    --environment "Variables={TABELA=${TABELA}}" >/dev/null
  echo "Função Lambda '${FUNC_NAME}' criada."
fi

echo "=== 6. Configurando notificação de eventos do S3 para a Lambda ==="
NOTIF_CONFIG=$(cat <<EOF
{
  "LambdaFunctionConfigurations": [
    {
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:${CONTA}:function:${FUNC_NAME}",
      "Events": ["s3:ObjectCreated:*"]
    }
  ]
}
EOF
)

aws s3api put-bucket-notification-configuration \
  --bucket "$BUCKET" \
  --notification-configuration "$NOTIF_CONFIG"

echo "[OK] Implantação da Etapa 4 concluída com sucesso!"
