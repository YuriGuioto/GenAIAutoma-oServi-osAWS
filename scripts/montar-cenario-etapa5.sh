#!/usr/bin/env bash
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-floci}"
CONTA="000000000000"
ASG_NAME="asg-campo"
LC_NAME="lc-monitoramento-campo"
TOPICO_SNS="alarme-cpu-alta"
FILA_SQS="fila-incidentes"
USUARIO_AGENTE="agente-operacional"
POLITICA_AGENTE="PoliticaAgenteAsgCampo"
ARN_POLITICA="arn:aws:iam::${CONTA}:policy/${POLITICA_AGENTE}"

echo "=== 1. Validando conta 000000000000 no Floci ==="
CONTA_ATUAL=$(aws sts get-caller-identity --query "Account" --output text)
if [ "$CONTA_ATUAL" != "$CONTA" ]; then
  echo "ERRO: Conta detectada ($CONTA_ATUAL) não é o Floci ($CONTA)."
  exit 1
fi

echo "=== 2. Criando Launch Configuration '${LC_NAME}' e Auto Scaling Group '${ASG_NAME}' ==="
aws autoscaling create-launch-configuration \
  --launch-configuration-name "$LC_NAME" \
  --image-id ami-0al2023floci00001 \
  --instance-type t3.micro >/dev/null 2>&1 || true

if ! aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$ASG_NAME" --query "AutoScalingGroups[0].AutoScalingGroupName" --output text 2>/dev/null | grep -q "$ASG_NAME"; then
  aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name "$ASG_NAME" \
    --launch-configuration-name "$LC_NAME" \
    --min-size 1 \
    --max-size 4 \
    --desired-capacity 1 \
    --availability-zones us-east-1a
  echo "Auto Scaling Group '${ASG_NAME}' criado (min=1, max=4, desejado=1)."
else
  aws autoscaling update-auto-scaling-group \
    --auto-scaling-group-name "$ASG_NAME" \
    --min-size 1 \
    --max-size 4 \
    --desired-capacity 1
  echo "Auto Scaling Group '${ASG_NAME}' atualizado para min=1, max=4, desejado=1."
fi

echo "=== 3. Criando Tópico SNS '${TOPICO_SNS}' e Fila SQS '${FILA_SQS}' ==="
ARN_TOPICO=$(aws sns create-topic --name "$TOPICO_SNS" --query "TopicArn" --output text)
URL_FILA=$(aws sqs create-queue --queue-name "$FILA_SQS" --query "QueueUrl" --output text)
ARN_FILA=$(aws sqs get-queue-attributes --queue-url "$URL_FILA" --attribute-names QueueArn --query "Attributes.QueueArn" --output text)

aws sns subscribe \
  --topic-arn "$ARN_TOPICO" \
  --protocol sqs \
  --notification-endpoint "$ARN_FILA" >/dev/null

echo "Tópico SNS (${ARN_TOPICO}) inscrito na fila SQS (${ARN_FILA})."

echo "=== 4. Criando Alarme CloudWatch 'AlarmeCpuAltaAsgCampo' (> 80%) ==="
aws cloudwatch put-metric-alarm \
  --alarm-name "AlarmeCpuAltaAsgCampo" \
  --alarm-description "Dispara quando CPUUtilization media de asg-campo ultrapassa 80%" \
  --metric-name "CPUUtilization" \
  --namespace "AWS/EC2" \
  --statistic Average \
  --period 60 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --dimensions "Name=AutoScalingGroupName,Value=${ASG_NAME}" \
  --evaluation-periods 2 \
  --alarm-actions "$ARN_TOPICO"

echo "=== 5. Criando Log Group de Auditoria '/aws/agente/diagnostico' ==="
aws logs create-log-group --log-group-name "/aws/agente/diagnostico" 2>/dev/null || true

echo "=== 6. Criando Usuário IAM restrito '${USUARIO_AGENTE}' para o Agente ==="
aws iam create-user --user-name "$USUARIO_AGENTE" >/dev/null 2>&1 || true

if ! aws iam get-policy --policy-arn "$ARN_POLITICA" >/dev/null 2>&1; then
  aws iam create-policy \
    --policy-name "$POLITICA_AGENTE" \
    --policy-document file://policies/iam-agente-asg.json >/dev/null
else
  aws iam put-user-policy \
    --user-name "$USUARIO_AGENTE" \
    --policy-name "$POLITICA_AGENTE" \
    --policy-document file://policies/iam-agente-asg.json >/dev/null
fi

aws iam attach-user-policy \
  --user-name "$USUARIO_AGENTE" \
  --policy-arn "$ARN_POLITICA" 2>/dev/null || true

CHAVES_ANTIGAS=$(aws iam list-access-keys --user-name "$USUARIO_AGENTE" --query "AccessKeyMetadata[].AccessKeyId" --output text)
for k in $CHAVES_ANTIGAS; do
  aws iam delete-access-key --user-name "$USUARIO_AGENTE" --access-key-id "$k"
done

aws iam create-access-key --user-name "$USUARIO_AGENTE" --output json > credenciais-temp.json
echo "[OK] Cenário da Etapa 5 montado e credenciais do agente salvas em credenciais-temp.json (ignorado pelo Git)."
