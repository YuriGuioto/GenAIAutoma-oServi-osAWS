#!/usr/bin/env bash
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-floci}"

echo "=== 1. Verificando identidade no Floci ==="
CONTA=$(aws sts get-caller-identity --query "Account" --output text)
if [ "$CONTA" != "000000000000" ]; then
  echo "ERRO DE SEGURANÇA: Conta detectada ($CONTA) não é o Floci (000000000000). Abortando!"
  exit 1
fi
echo "Conectado com segurança à conta $CONTA (Floci)."

echo "=== 2. Criando buckets S3 de partida ==="
aws s3 mb s3://relatorios || true
aws s3 mb s3://imagens-drone || true
echo "Inspeção talhão 12: sem pragas" | aws s3 cp - s3://relatorios/inspecao-001.txt

echo "=== 3. Criando tabela DynamoDB 'sensores' ==="
if ! aws dynamodb describe-table --table-name sensores >/dev/null 2>&1; then
  aws dynamodb create-table \
    --table-name sensores \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  echo "Tabela 'sensores' criada."
else
  echo "Tabela 'sensores' já existe."
fi

echo "=== 4. Criando usuário IAM 'tecnico-campo' ==="
if ! aws iam get-user --user-name tecnico-campo >/dev/null 2>&1; then
  aws iam create-user --user-name tecnico-campo >/dev/null
  echo "Usuário 'tecnico-campo' criado."
else
  echo "Usuário 'tecnico-campo' já existe."
fi

echo "=== 5. Conferindo recursos criados ==="
echo "--- Buckets S3 ---"
aws s3 ls
echo "--- Tabelas DynamoDB ---"
aws dynamodb list-tables --output table
echo "--- Usuários IAM ---"
aws iam list-users --output table
