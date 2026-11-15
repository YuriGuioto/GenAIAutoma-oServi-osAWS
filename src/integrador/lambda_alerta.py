"""
Função AWS Lambda do Projeto Integrador (Papel: Componente em Tempo Real).
Disparada por novos arquivos JSON no bucket S3 'alertas-irrigacao'.
Classifica cada alerta via Amazon Bedrock (Converse API) e grava no DynamoDB 'alertas-irrigacao-ddb'.
"""

import json
import logging
import os
import urllib.parse
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
tabela = dynamodb.Table(os.environ.get("TABELA_ALERTAS", "alertas-irrigacao-ddb"))
MODELO = os.environ.get("MODELO_ID", "anthropic.claude-3-haiku-20240307-v1:0")

SYSTEM_PROMPT = (
    "Você é um especialista em engenharia de irrigação agrícola.\n"
    "Analise os dados do sensor de irrigação dentro de <telemetria_sensor> e responda "
    "APENAS com um JSON válido no formato:\n"
    '{"resumo_tecnico": "diagnóstico curto em 1 frase", '
    '"urgencia": "baixa|media|alta", '
    '"acao_imediata": "recomendação objetiva para a equipe de campo"}'
)


def extrair_json_alerta(texto: str) -> dict:
    ini, fim = texto.find("{"), texto.rfind("}")
    if ini == -1 or fim == -1:
        raise ValueError("Sem delimitadores JSON")
    dados = json.loads(texto[ini : fim + 1])
    urg = str(dados.get("urgencia", "revisao_humana")).lower().replace("é", "e")
    if urg not in {"baixa", "media", "alta"}:
        urg = "revisao_humana"
    return {
        "resumo_tecnico": str(dados.get("resumo_tecnico", "Sem resumo")).strip(),
        "urgencia": urg,
        "acao_imediata": str(dados.get("acao_imediata", "Verificar em campo")).strip(),
    }


def handler(event, context):
    processados = []
    for reg in event.get("Records", []):
        bucket = reg["s3"]["bucket"]["name"]
        chave = urllib.parse.unquote_plus(reg["s3"]["object"]["key"])
        corpo = s3.get_object(Bucket=bucket, Key=chave)["Body"].read().decode("utf-8")
        payload_sensor = json.loads(corpo)

        id_alerta = payload_sensor.get("id_alerta", chave)
        prompt = f"<telemetria_sensor>\n{json.dumps(payload_sensor, ensure_ascii=False)}\n</telemetria_sensor>"

        tokens_in, tokens_out = 0, 0
        classificacao = {
            "resumo_tecnico": "Encaminhado para revisão humana.",
            "urgencia": "revisao_humana",
            "acao_imediata": "Inspecionar sensor manualmente.",
        }

        for tentativa in range(1, 3):
            resp = bedrock.converse(
                modelId=MODELO,
                system=[{"text": SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 250, "temperature": 0},
            )
            tokens_in += int(resp.get("usage", {}).get("inputTokens", 0))
            tokens_out += int(resp.get("usage", {}).get("outputTokens", 0))
            texto_resp = resp["output"]["message"]["content"][0]["text"]
            try:
                classificacao = extrair_json_alerta(texto_resp)
                break
            except Exception as erro:
                logger.warning("Tentativa %d falhou na extração JSON: %s", tentativa, erro)

        item = {
            "id_alerta": id_alerta,
            "equipamento": payload_sensor.get("equipamento", "Desconhecido"),
            "cultura": payload_sensor.get("cultura", "Desconhecida"),
            "umidade_solo_percent": str(payload_sensor.get("umidade_solo_percent", "")),
            "pressao_bar": str(payload_sensor.get("pressao_bar", "")),
            "resumo_tecnico": classificacao["resumo_tecnico"],
            "urgencia": classificacao["urgencia"],
            "acao_imediata": classificacao["acao_imediata"],
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
        tabela.put_item(Item=item)
        processados.append(item)

    return {"statusCode": 200, "processados": processados}
