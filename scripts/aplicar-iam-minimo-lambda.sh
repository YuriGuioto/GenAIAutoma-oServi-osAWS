#!/usr/bin/env bash
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-floci}"
ROLE_NAME="triagem-lambda"

echo "=== 1. Substituindo a política da Role '${ROLE_NAME}' pelo menor privilégio estrito ==="
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "TriagemLambdaPermissions" \
  --policy-document file://policies/lambda-triagem-minima.json

echo "=== 2. Enviando relatório de teste para confirmar que o fluxo S3 -> Lambda -> Bedrock -> DynamoDB continua funcionando ==="
aws s3 cp exemplos/relatorio-injection.txt s3://relatorios-campo/relatorio-injection.txt
echo "Aguardando execução da Lambda (15s)..."
sleep 15

echo "=== 3. Verificando registro gravado no DynamoDB com suspeita_prompt_injection=true ==="
aws dynamodb get-item \
  --table-name triagem \
  --key '{"arquivo":{"S":"relatorio-injection.txt"}}' \
  --output json
