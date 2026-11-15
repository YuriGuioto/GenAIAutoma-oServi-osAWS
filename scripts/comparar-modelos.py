#!/usr/bin/env python3
"""
Script de comparação empírica entre dois modelos locais via proxy do Floci (Etapa 4).
Associação configurada em FLOCI_SERVICES_BEDROCK_RUNTIME_PROXY_MODEL_MAPPING:
  - anthropic.claude-3-haiku-20240307-v1:0   -> llama3.2
  - anthropic.claude-3-5-sonnet-20240620-v1:0 -> qwen2.5:3b

Mede para cada modelo nos 3 relatórios de campo:
  1. Acerto da classificação de urgência (baixa, media, alta)
  2. Validade do JSON na primeira tentativa
  3. Latência de resposta em segundos
  4. Tokens de entrada e saída
"""

import json
import os
import time
import boto3

MODELOS_EM_TESTE = [
    ("llama3.2 (via Haiku ID)", "anthropic.claude-3-haiku-20240307-v1:0"),
    ("qwen2.5:3b (via Sonnet ID)", "anthropic.claude-3-5-sonnet-20240620-v1:0"),
]

CASOS_DE_TESTE = [
    ("exemplos/relatorio-baixa.txt", "baixa"),
    ("exemplos/relatorio-media.txt", "media"),
    ("exemplos/relatorio-alta.txt", "alta"),
]

SYSTEM_PROMPT = (
    'Responda só em JSON válido: {"resumo": str, "urgencia": "baixa|media|alta"}'
)


def avaliar_modelo(bedrock_client, nome_amigavel: str, model_id: str) -> list[dict]:
    resultados = []
    for caminho, urgencia_esperada in CASOS_DE_TESTE:
        with open(caminho, "r", encoding="utf-8") as f:
            texto = f.read()

        inicio = time.perf_counter()
        resp = bedrock_client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": texto}]}],
            inferenceConfig={"maxTokens": 300, "temperature": 0},
        )
        latencia_s = round(time.perf_counter() - inicio, 2)

        bruto = resp["output"]["message"]["content"][0]["text"].strip()
        uso = resp.get("usage", {})
        json_ok = False
        urgencia_obtida = "erro_json"

        try:
            ini_j, fim_j = bruto.find("{"), bruto.rfind("}")
            dados = json.loads(bruto[ini_j : fim_j + 1] if ini_j != -1 else bruto)
            urgencia_obtida = str(dados.get("urgencia", "")).lower().replace("é", "e")
            json_ok = True
        except Exception:
            json_ok = False

        acertou = urgencia_obtida == urgencia_esperada
        resultados.append(
            {
                "modelo": nome_amigavel,
                "arquivo": os.path.basename(caminho),
                "esperado": urgencia_esperada,
                "obtido": urgencia_obtida,
                "acertou": acertou,
                "json_valido": json_ok,
                "latencia_s": latencia_s,
                "tokens_in": uso.get("inputTokens", 0),
                "tokens_out": uso.get("outputTokens", 0),
            }
        )
    return resultados


def main():
    perfil = os.environ.get("AWS_PROFILE", "floci")
    sessao = boto3.Session(profile_name=perfil)
    bedrock = sessao.client("bedrock-runtime")

    print("=== Comparativo de Modelos Locais via Bedrock Runtime Proxy (Floci) ===\n")
    cabecalho = f"{'Modelo':<28} | {'Arquivo':<20} | {'Esp.':<6} | {'Obt.':<10} | {'JSON?':<5} | {'Lat.(s)':<7} | {'In/Out Tokens'}"
    print(cabecalho)
    print("-" * len(cabecalho))

    for nome_amigavel, model_id in MODELOS_EM_TESTE:
        linhas = avaliar_modelo(bedrock, nome_amigavel, model_id)
        for r in linhas:
            print(
                f"{r['modelo']:<28} | {r['arquivo']:<20} | {r['esperado']:<6} | "
                f"{r['obtido']:<10} | {str(r['json_valido']):<5} | {r['latencia_s']:<7.2f} | "
                f"{r['tokens_in']}/{r['tokens_out']}"
            )


if __name__ == "__main__":
    main()
