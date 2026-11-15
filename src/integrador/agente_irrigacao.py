#!/usr/bin/env python3
"""
Agente Operacional de Irrigação (Papel: Agente no Projeto Integrador).
Investiga alertas críticos no DynamoDB e métricas de pressão das bombas no CloudWatch,
e propõe o disparo de ordem de manutenção emergencial via SNS mediante aprovação humana.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
import boto3
from botocore.exceptions import ClientError

MODELO = os.environ.get("MODELO_ID", "anthropic.claude-3-haiku-20240307-v1:0")
LOG_GROUP = "/aws/integrador/agente"
LOG_STREAM = f"execucao-irrigacao-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

SYSTEM_PROMPT = (
    "Você é o Agente de Operações de Irrigação da Fazenda Vale do Pardo.\n"
    "1. Primeiro, chame 'consultar_alertas_criticos' para identificar pivôs com urgência alta ou média.\n"
    "2. Em seguida, chame 'verificar_metricas_bomba' para confirmar se há múltiplos pontos de queda de pressão no CloudWatch.\n"
    "3. Só proponha 'acionar_manutencao_sns' após comprovar o problema nos dados.\n"
    "4. Responda em português detalhando o diagnóstico e a ação tomada."
)

FERRAMENTAS = [
    {
        "toolSpec": {
            "name": "consultar_alertas_criticos",
            "description": "Lista todos os alertas de sensores gravados na tabela DynamoDB alertas-irrigacao-ddb.",
            "inputSchema": {"json": {"type": "object", "properties": {}}},
        }
    },
    {
        "toolSpec": {
            "name": "verificar_metricas_bomba",
            "description": "Consulta a série histórica de PressaoBar de um pivô no CloudWatch (namespace Agro/Irrigacao).",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "equipamento": {
                            "type": "string",
                            "description": "Nome do equipamento (ex.: Pivô Central 03)",
                        }
                    },
                    "required": ["equipamento"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "acionar_manutencao_sns",
            "description": "Envia ordem de serviço emergencial no tópico SNS boletim-irrigacao-diario (exige aprovação humana).",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "equipamento": {"type": "string"},
                        "motivo": {"type": "string"},
                    },
                    "required": ["equipamento", "motivo"],
                }
            },
        }
    },
]


def popular_metricas_pressao_pivo03(cw) -> None:
    """Publica 5 pontos de pressão caindo de 4.0 bar para 0.4 bar no Pivô Central 03."""
    agora = datetime.now(timezone.utc)
    pontos = [4.0, 2.5, 0.9, 0.5, 0.4]
    dados = [
        {
            "MetricName": "PressaoBar",
            "Dimensions": [{"Name": "Equipamento", "Value": "Pivô Central 03"}],
            "Timestamp": agora - timedelta(minutes=(len(pontos) - 1 - i)),
            "Value": v,
            "Unit": "None",
        }
        for i, v in enumerate(pontos)
    ]
    cw.put_metric_data(Namespace="Agro/Irrigacao", MetricData=dados)


def main():
    perfil = os.environ.get("AWS_PROFILE", "floci")
    sessao = boto3.Session(profile_name=perfil)
    bedrock = sessao.client("bedrock-runtime")
    ddb = sessao.resource("dynamodb").Table("alertas-irrigacao-ddb")
    cw = sessao.client("cloudwatch")
    sns = sessao.client("sns")
    logs = sessao.client("logs")

    popular_metricas_pressao_pivo03(cw)

    try:
        logs.create_log_group(logGroupName=LOG_GROUP)
    except ClientError:
        pass
    try:
        logs.create_log_stream(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM)
    except ClientError:
        pass

    def auditar(evento: dict):
        logs.put_log_events(
            logGroupName=LOG_GROUP,
            logStreamName=LOG_STREAM,
            logEvents=[{"timestamp": int(time.time() * 1000), "message": json.dumps(evento, ensure_ascii=False, default=str)}],
        )

    def executar(nome: str, entrada: dict) -> dict:
        if nome == "consultar_alertas_criticos":
            return {"alertas": ddb.scan().get("Items", [])}
        if nome == "verificar_metricas_bomba":
            eq = entrada.get("equipamento", "Pivô Central 03")
            agora = datetime.now(timezone.utc)
            r = cw.get_metric_statistics(
                Namespace="Agro/Irrigacao",
                MetricName="PressaoBar",
                Dimensions=[{"Name": "Equipamento", "Value": eq}],
                StartTime=agora - timedelta(minutes=15),
                EndTime=agora,
                Period=60,
                Statistics=["Average"],
            )
            pts = sorted(r.get("Datapoints", []), key=lambda x: x["Timestamp"])
            return {"equipamento": eq, "pontos_pressao_bar": [round(p["Average"], 2) for p in pts]}
        if nome == "acionar_manutencao_sns":
            arn = sns.create_topic(Name="boletim-irrigacao-diario")["TopicArn"]
            pub = sns.publish(
                TopicArn=arn,
                Subject=f"ORDEM DE MANUTENCAO EMERGENCIAL - {entrada.get('equipamento')}",
                Message=f"Equipamento: {entrada.get('equipamento')}\nMotivo: {entrada.get('motivo')}",
            )
            return {"status": "ordem_enviada", "messageId": pub["MessageId"]}
        return {"erro": "Ferramenta desconhecida"}

    msgs = [
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "Verifique os alertas de sensores de irrigação de hoje, confira as métricas de pressão "
                        "do equipamento crítico e acione uma ordem de manutenção via SNS se necessário."
                    )
                }
            ],
        }
    ]

    iteracao = 0
    while iteracao < 6:
        resp = bedrock.converse(
            modelId=MODELO,
            system=[{"text": SYSTEM_PROMPT}],
            messages=msgs,
            toolConfig={"tools": FERRAMENTAS},
            inferenceConfig={"maxTokens": 500, "temperature": 0},
        )
        msg = resp["output"]["message"]
        msgs.append(msg)

        if resp["stopReason"] != "tool_use":
            print("\n=== Relatório Final do Agente de Irrigação ===\n")
            print(msg["content"][0].get("text", ""))
            break

        resultados_bloco = []
        for bloco in msg["content"]:
            if "toolUse" in bloco:
                uso = bloco["toolUse"]
                nome_f = uso["name"]
                inp = uso["input"]
                print(f"[Iteração {iteracao + 1}] Ferramenta solicitada: {nome_f}({json.dumps(inp, ensure_ascii=False)})")

                if nome_f == "acionar_manutencao_sns" and input(f"Aprovar envio de Ordem de Manutenção {inp}? [s/N] ").strip().lower() != "s":
                    res = {"erro": "ação negada pelo operador"}
                else:
                    res = executar(nome_f, inp)

                auditar({"iteracao": iteracao + 1, "ferramenta": nome_f, "entrada": inp, "resultado": res})
                resultados_bloco.append({"toolResult": {"toolUseId": uso["toolUseId"], "content": [{"json": res}]}})

        msgs.append({"role": "user", "content": resultados_bloco})
        iteracao += 1


if __name__ == "__main__":
    main()
