#!/usr/bin/env python3
"""
Simulador de incidente de CPU alta no Auto Scaling Group 'asg-campo' (Etapa 5).
Publica uma série histórica de pontos de CPUUtilization no namespace AWS/EC2
subindo gradualmente de 30% a 95% ao longo dos últimos minutos para que:
  1. O alarme CloudWatch ('AlarmeCpuAltaAsgCampo') entre em estado ALARM e notifique SNS -> SQS.
  2. O agente possa analisar uma tendência consistente (vários pontos acima de 80%),
     e não apenas um único pico isolado.
"""

import os
from datetime import datetime, timedelta, timezone
import boto3


def publicar_serie_cpu(asg_name: str = "asg-campo") -> None:
    perfil = os.environ.get("AWS_PROFILE", "floci")
    sessao = boto3.Session(profile_name=perfil)
    cw = sessao.client("cloudwatch")

    valores_cpu = [30.0, 45.0, 62.0, 78.0, 85.0, 90.0, 93.0, 95.0]
    agora = datetime.now(timezone.utc)

    metric_data = []
    for indice, valor in enumerate(valores_cpu):
        instante = agora - timedelta(minutes=(len(valores_cpu) - 1 - indice))
        metric_data.append(
            {
                "MetricName": "CPUUtilization",
                "Dimensions": [{"Name": "AutoScalingGroupName", "Value": asg_name}],
                "Timestamp": instante,
                "Value": valor,
                "Unit": "Percent",
            }
        )

    cw.put_metric_data(Namespace="AWS/EC2", MetricData=metric_data)
    print(f"[OK] Publicados {len(valores_cpu)} pontos de CPUUtilization (30% -> 95%) para '{asg_name}'.")


if __name__ == "__main__":
    publicar_serie_cpu()
