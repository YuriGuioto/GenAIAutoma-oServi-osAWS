#!/usr/bin/env bash
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-floci}"
ENDPOINT_FLOCI="http://localhost:4566"
USUARIO="tecnico-campo"
NOME_POLITICA="LeituraBucketRelatoriosPolicy"
ARN_POLITICA="arn:aws:iam::000000000000:policy/${NOME_POLITICA}"

echo "=== 1. Validando conta 000000000000 no Floci ==="
CONTA=$(aws sts get-caller-identity --query "Account" --output text)
if [ "$CONTA" != "000000000000" ]; then
  echo "ERRO: Conta ($CONTA) não é o Floci. Abortando!"
  exit 1
fi

echo "=== 2. Garantindo que o usuário '${USUARIO}' e a política existem ==="
aws iam create-user --user-name "$USUARIO" >/dev/null 2>&1 || true

if ! aws iam get-policy --policy-arn "$ARN_POLITICA" >/dev/null 2>&1; then
  aws iam create-policy \
    --policy-name "$NOME_POLITICA" \
    --policy-document file://policies/s3-leitura-relatorios.json >/dev/null
  echo "Política IAM '$NOME_POLITICA' criada."
else
  echo "Política IAM '$NOME_POLITICA' já existe."
fi

aws iam attach-user-policy \
  --user-name "$USUARIO" \
  --policy-arn "$ARN_POLITICA"

echo "=== 3. Gerando Access Key exclusiva para '${USUARIO}' ==="
CHAVES_ANTIGAS=$(aws iam list-access-keys --user-name "$USUARIO" --query "AccessKeyMetadata[].AccessKeyId" --output text)
for k in $CHAVES_ANTIGAS; do
  aws iam delete-access-key --user-name "$USUARIO" --access-key-id "$k"
done

CRED_JSON=$(aws iam create-access-key --user-name "$USUARIO" --output json)
AK_ID=$(echo "$CRED_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['AccessKey']['AccessKeyId'])")
SK_SECRET=$(echo "$CRED_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['AccessKey']['SecretAccessKey'])")

echo "AccessKeyId gerada: $AK_ID"

echo "=== 4. Testando LEITURA (s3api get-object) — DEVE PASSAR ==="
AWS_ACCESS_KEY_ID="$AK_ID" \
AWS_SECRET_ACCESS_KEY="$SK_SECRET" \
AWS_DEFAULT_REGION="us-east-1" \
AWS_ENDPOINT_URL="$ENDPOINT_FLOCI" \
aws s3api get-object \
  --bucket relatorios \
  --key inspecao-001.txt \
  /tmp/inspecao-baixada.txt >/dev/null

echo "[SUCESSO] Leitura permitida! Conteúdo lido do S3:"
cat /tmp/inspecao-baixada.txt
rm -f /tmp/inspecao-baixada.txt

echo ""
echo "=== 5. Testando ESCRITA (s3api put-object) — DEVE FALHAR (AccessDenied) ==="
echo "Tentativa de escrita não autorizada" > /tmp/nao-autorizado.txt

set +e
SAIDA_PUT=$(AWS_ACCESS_KEY_ID="$AK_ID" \
  AWS_SECRET_ACCESS_KEY="$SK_SECRET" \
  AWS_DEFAULT_REGION="us-east-1" \
  AWS_ENDPOINT_URL="$ENDPOINT_FLOCI" \
  aws s3api put-object \
    --bucket relatorios \
    --key invasao.txt \
    --body /tmp/nao-autorizado.txt 2>&1)
CODIGO_SAIDA=$?
set -e
rm -f /tmp/nao-autorizado.txt

if [ $CODIGO_SAIDA -ne 0 ]; then
  echo "[SUCESSO] Escrita bloqueada pela política IAM conforme esperado!"
  echo "Detalhe do bloqueio: $SAIDA_PUT"
else
  echo "[FALHA DE SEGURANÇA] O put-object passou! Verifique se FLOCI_SERVICES_IAM_ENFORCEMENT_ENABLED=true está ativo no container floci."
  exit 1
fi
