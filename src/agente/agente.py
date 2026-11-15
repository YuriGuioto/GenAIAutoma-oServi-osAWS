#!/usr/bin/env python3
"""
Agente de Diagnóstico e Operação de Auto Scaling (Etapa 5).
Regras de segurança implementadas:
  1. Opera com as credenciais IAM restritas do usuário 'agente-operacional' (geradas em credenciais-temp.json),
     sob FLOCI_SERVICES_IAM_ENFORCEMENT_ENABLED=true.
  2. Laço ReAct com limite estrito de 6 iterações (while iteracao < 6).
  3. Aprovação humana obrigatória no terminal antes de executar 'ajustar_capacidade'.
  4. Registro de auditoria de cada chamada de ferramenta no CloudWatch Logs (/aws/agente/diagnostico).
  5. System Prompt exigindo análise de múltiplos pontos de métrica (proibido decidir por um único ponto).
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
import boto3
from botocore.exceptions import ClientError

MODELO = os.environ.get("MODELO_AGENTE", "anthropic.claude-3-haiku-20240307-v1:0")
LOG_GROUP = "/aws/agente/diagnostico"
LOG_STREAM = f"execucao-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

SYSTEM_PROMPT = (
    "Você é um engenheiro SRE e agente de diagnóstico operacional AWS responsável pelo grupo "
    "de Auto Scaling 'asg-campo'.\n"
    "REGRAS OBRIGATÓRIAS DE RACIOCÍNIO E SEGURANÇA:\n"
    "1. Antes de propor qualquer mudança de capacidade, você DEVE consultar as métricas de CPU "
    "('ler_metricas'), o estado atual do grupo ('descrever_asg') e o histórico recente ('listar_atividades').\n"
    "2. NUNCA decida escalar com base em um único ponto isolado de métrica! Verifique quantos pontos "
    "foram retornados por 'ler_metricas' e só recomende/execute 'ajustar_capacidade' se houver tendência "
    "sustentada (pelo menos 3 pontos consecutivos acima de 80% de CPU).\n"
    "3. Ao final, responda sempre em português do Brasil explicando: (a) o que aconteceu, "
    "(b) a causa provável e (c) a ação recomendada ou executada."
)

FERRAMENTAS = [
    {
        "toolSpec": {
            "name": "ler_metricas",
            "description": "Lê a série histórica recente de CPUUtilization (média por minuto) de um Auto Scaling Group no CloudWatch.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "nome_asg": {
                            "type": "string",
                            "description": "Nome do grupo de Auto Scaling (ex.: asg-campo)",
                        },
                        "minutos": {
                            "type": "integer",
                            "description": "Janela de tempo em minutos para buscar os pontos (padrão: 15)",
                        },
                    },
                    "required": ["nome_asg"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "descrever_asg",
            "description": "Obtém a configuração atual (min, max, desiredCapacity e instâncias) de um grupo de Auto Scaling.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "nome_asg": {
                            "type": "string",
                            "description": "Nome do grupo de Auto Scaling (ex.: asg-campo)",
                        }
                    },
                    "required": ["nome_asg"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "listar_atividades",
            "description": "Lista as atividades recentes de escalonamento de um grupo de Auto Scaling.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "nome_asg": {
                            "type": "string",
                            "description": "Nome do grupo de Auto Scaling (ex.: asg-campo)",
                        }
                    },
                    "required": ["nome_asg"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "ajustar_capacidade",
            "description": "Altera a capacidade desejada (desiredCapacity) do grupo de Auto Scaling. Ação de escrita sujeita a aprovação humana.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "nome_asg": {
                            "type": "string",
                            "description": "Nome do grupo de Auto Scaling (ex.: asg-campo)",
                        },
                        "nova_capacidade": {
                            "type": "integer",
                            "description": "Novo número desejado de instâncias (entre min e max do ASG)",
                        },
                    },
                    "required": ["nome_asg", "nova_capacidade"],
                }
            },
        }
    },
]


def criar_sessao_agente() -> boto3.Session:
    """Cria sessão boto3 usando as credenciais IAM restritas do agente, sem hardcode de endpoint."""
    perfil = os.environ.get("AWS_PROFILE", "floci")
    sessao_base = boto3.Session(profile_name=perfil)

    if os.path.exists("credenciais-temp.json"):
        with open("credenciais-temp.json", "r", encoding="utf-8") as f:
            dados = json.load(f)["AccessKey"]
        endpoint_resolvido = sessao_base.client("sts").meta.endpoint_url
        os.environ["AWS_ENDPOINT_URL"] = endpoint_resolvido
        return boto3.Session(
            aws_access_key_id=dados["AccessKeyId"],
            aws_secret_access_key=dados["SecretAccessKey"],
            region_name=sessao_base.region_name or "us-east-1",
        )
    return sessao_base


sessao = criar_sessao_agente()
bedrock = sessao.client("bedrock-runtime")
cloudwatch = sessao.client("cloudwatch")
autoscaling = sessao.client("autoscaling")
logs_client = sessao.client("logs")


def registrar_auditoria(evento: dict) -> None:
    """Registra cada decisão/chamada de ferramenta do agente no CloudWatch Logs."""
    try:
        logs_client.create_log_group(logGroupName=LOG_GROUP)
    except ClientError:
        pass
    try:
        logs_client.create_log_stream(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM)
    except ClientError:
        pass

    logs_client.put_log_events(
        logGroupName=LOG_GROUP,
        logStreamName=LOG_STREAM,
        logEvents=[
            {
                "timestamp": int(time.time() * 1000),
                "message": json.dumps(evento, ensure_ascii=False, default=str),
            }
        ],
    )


def executar(nome_ferramenta: str, parametros: dict) -> dict:
    """Executa a ferramenta AWS solicitada pelo modelo e retorna um dicionário serializável."""
    nome_asg = parametros.get("nome_asg", "asg-campo")

    try:
        if nome_ferramenta == "ler_metricas":
            minutos = int(parametros.get("minutos", 15))
            agora = datetime.now(timezone.utc)
            inicio = agora - timedelta(minutes=minutos)
            resp = cloudwatch.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "AutoScalingGroupName", "Value": nome_asg}],
                StartTime=inicio,
                EndTime=agora,
                Period=60,
                Statistics=["Average", "Maximum"],
            )
            pontos = sorted(resp.get("Datapoints", []), key=lambda x: x["Timestamp"])
            serie = [
                {
                    "horario_utc": p["Timestamp"].strftime("%H:%M:%S"),
                    "media_cpu": round(p.get("Average", 0.0), 1),
                    "max_cpu": round(p.get("Maximum", 0.0), 1),
                }
                for p in pontos
            ]
            return {
                "nome_asg": nome_asg,
                "quantidade_pontos": len(serie),
                "pontos": serie,
            }

        if nome_ferramenta == "descrever_asg":
            resp = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[nome_asg])
            grupos = resp.get("AutoScalingGroups", [])
            if not grupos:
                return {"erro": f"Grupo {nome_asg} não encontrado."}
            g = grupos[0]
            return {
                "nome_asg": g["AutoScalingGroupName"],
                "min_size": g["MinSize"],
                "max_size": g["MaxSize"],
                "desired_capacity": g["DesiredCapacity"],
                "instancias_ativas": len(g.get("Instances", [])),
            }

        if nome_ferramenta == "listar_atividades":
            resp = autoscaling.describe_scaling_activities(
                AutoScalingGroupName=nome_asg, MaxRecords=5
            )
            atividades = [
                {
                    "causa": a.get("Cause", ""),
                    "status": a.get("StatusCode", ""),
                    "descricao": a.get("Description", ""),
                }
                for a in resp.get("Activities", [])[:5]
            ]
            return {"nome_asg": nome_asg, "atividades_recentes": atividades}

        if nome_ferramenta == "ajustar_capacidade":
            nova_cap = int(parametros["nova_capacidade"])
            autoscaling.set_desired_capacity(
                AutoScalingGroupName=nome_asg,
                DesiredCapacity=nova_cap,
                HonorCooldown=False,
            )
            return {
                "status": "sucesso",
                "nome_asg": nome_asg,
                "nova_capacidade_aplicada": nova_cap,
            }

        return {"erro": f"Ferramenta desconhecida: {nome_ferramenta}"}
    except ClientError as erro:
        return {"erro_aws": str(erro)}


def rodar_agente() -> None:
    msgs = [
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "Disparou um alarme de CPU alta para o grupo de Auto Scaling 'asg-campo'. "
                        "Investigue as métricas de CPU dos últimos 15 minutos, a configuração atual do ASG "
                        "e as atividades de escalonamento. Se houver tendência sustentada de sobrecarga "
                        "(múltiplos pontos acima de 80%), proponha o ajuste da capacidade desejada para 2 instâncias."
                    )
                }
            ],
        }
    ]

    iteracao = 0
    print(f"=== Iniciando Agente de Diagnóstico (LogStream: {LOG_STREAM}) ===")

    while iteracao < 6:
        resp = bedrock.converse(
            modelId=MODELO,
            system=[{"text": SYSTEM_PROMPT}],
            messages=msgs,
            toolConfig={"tools": FERRAMENTAS},
            inferenceConfig={"maxTokens": 600, "temperature": 0},
        )
        msg = resp["output"]["message"]
        msgs.append(msg)

        if resp["stopReason"] != "tool_use":
            texto_final = msg["content"][0].get("text", "")
            registrar_auditoria({"iteracao": iteracao, "evento": "resposta_final", "texto": texto_final})
            print("\n=== Diagnóstico Final do Agente ===\n")
            print(texto_final)
            break

        blocos_resultado = []
        for bloco in msg["content"]:
            if "toolUse" in bloco:
                uso = bloco["toolUse"]
                nome_tool = uso["name"]
                entrada_tool = uso["input"]
                print(f"[Iteração {iteracao + 1}] Agente solicitou ferramenta: {nome_tool}({json.dumps(entrada_tool, ensure_ascii=False)})")

                if nome_tool == "ajustar_capacidade":
                    confirmacao = input(f"Aprovar {entrada_tool}? [s/N] ").strip().lower()
                    if confirmacao != "s":
                        resultado = {"erro": "ação negada pelo operador"}
                        aprovado = False
                    else:
                        resultado = executar(nome_tool, entrada_tool)
                        aprovado = True
                else:
                    resultado = executar(nome_tool, entrada_tool)
                    aprovado = True

                registrar_auditoria(
                    {
                        "iteracao": iteracao + 1,
                        "ferramenta": nome_tool,
                        "entrada": entrada_tool,
                        "aprovado_pelo_operador": aprovado,
                        "resultado": resultado,
                    }
                )

                blocos_resultado.append(
                    {
                        "toolResult": {
                            "toolUseId": uso["toolUseId"],
                            "content": [{"json": resultado}],
                        }
                    }
                )

        msgs.append({"role": "user", "content": blocos_resultado})
        iteracao += 1


if __name__ == "__main__":
    rodar_agente()
