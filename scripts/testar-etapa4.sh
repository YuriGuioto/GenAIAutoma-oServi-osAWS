#!/usr/bin/env bash
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-floci}"
BUCKET="relatorios-campo"
TABELA="triagem"

echo "=== 1. Enviando os 3 relatórios de campo para s3://${BUCKET}/ ==="
for ARQUIVO in relatorio-baixa.txt relatorio-media.txt relatorio-alta.txt; do
  echo " -> Enviando ${ARQUIVO}..."
  aws s3 cp "exemplos/${ARQUIVO}" "s3://${BUCKET}/${ARQUIVO}"
  echo "    Aguardando processamento da Lambda + Ollama (15s)..."
  sleep 15
done

echo ""
echo "=== 2. Consultando itens gravados na tabela DynamoDB '${TABELA}' ==="
aws dynamodb scan \
  --table-name "$TABELA" \
  --query "Items[].{Arquivo:arquivo.S,Urgencia:urgencia.S,Status:status_processamento.S,TokensIn:tokens_in.N,TokensOut:tokens_out.N,Resumo:resumo.S}" \
  --output table

echo ""
echo "=== 3. Testando a Variante Saúde (anonimização LGPD antes do Bedrock) ==="
python3 src/triagem/app_saude.py
