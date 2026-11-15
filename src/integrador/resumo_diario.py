#!/usr/bin/env python3
"""
Gerador de Resumo Diário de Irrigação via Bedrock e Envio por SNS (Projeto Integrador).
1. Lê todos os alertas classificados na tabela DynamoDB 'alertas-irrigacao-ddb'.
2. Chama o Amazon Bedrock (Converse API) para redigir o Boletim Diário Executivo para o Engenheiro Agrônomo.
3. Publica o boletim no tópico SNS 'boletim-irrigacao-diario' (entregue na fila SQS 'fila-engenheiro-agronomo').
"""

import json
import os
import boto3

MODELO = os.environ.get("MODELO_ID", "anthropic.claude-3-haiku-20240307-v1:0")
TABELA_NOME = "alertas-irrigacao-ddb"
TOPICO_NOME = "boletim-irrigacao-diario"


def gerar_e_publicar_resumo() -> None:
    perfil = os.environ.get("AWS_PROFILE", "floci")
    sessao = boto3.Session(profile_name=perfil)
    ddb = sessao.resource("dynamodb")
    bedrock = sessao.client("bedrock-runtime")
    sns = sessao.client("sns")

    tabela = ddb.Table(TABELA_NOME)
    itens = tabela.scan().get("Items", [])
    if not itens:
        raise RuntimeError("Nenhum alerta encontrado em 'alertas-irrigacao-ddb'.")

    prompt_boletim = (
        "Com base nos alertas de sensores de irrigação processados hoje (JSON abaixo), "
        "elabore um Boletim Diário Executivo em português para o Engenheiro Agrônomo Chefe.\n"
        "Destaque primeiro os alertas de urgência ALTA, depois os de urgência MÉDIA e por fim os de urgência BAIXA, "
        "incluindo recomendações práticas de manutenção e manejo hídrico:\n"
        f"{json.dumps(itens, ensure_ascii=False, default=str)}"
    )

    resp = bedrock.converse(
        modelId=MODELO,
        system=[
            {
                "text": "Você é um consultor sênior de engenharia agronômica e irrigação em Ribeirão Preto/SP."
            }
        ],
        messages=[{"role": "user", "content": [{"text": prompt_boletim}]}],
        inferenceConfig={"maxTokens": 500, "temperature": 0},
    )

    boletim_texto = resp["output"]["message"]["content"][0]["text"]
    arn_topico = sns.create_topic(Name=TOPICO_NOME)["TopicArn"]

    pub = sns.publish(
        TopicArn=arn_topico,
        Subject="Boletim Diario de Irrigacao - Fazenda Vale do Pardo",
        Message=boletim_texto,
    )

    print("=== Boletim Diário Gerado pelo Bedrock e Publicado no SNS ===")
    print(f"TopicArn:  {arn_topico}")
    print(f"MessageId: {pub['MessageId']}\n")
    print(boletim_texto)


if __name__ == "__main__":
    gerar_e_publicar_resumo()
