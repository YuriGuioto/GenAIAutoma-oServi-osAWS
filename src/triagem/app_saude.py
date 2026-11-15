"""
Variante Saúde (Desafio Extra da Etapa 4 e LGPD da Etapa 6):
Triagem de chamados de manutenção de equipamentos hospitalares.
Remove/anonimiza automaticamente dados pessoais sensíveis (CPF, RG, telefone, e-mail,
nomes de pacientes e números de prontuário) ANTES de enviar o texto ao modelo do Bedrock.
"""

import json
import os
import re
import boto3

bedrock = boto3.client("bedrock-runtime")
MODELO = os.environ.get("MODELO_ID", "anthropic.claude-3-haiku-20240307-v1:0")


def anonimizar_dados_lgpd(texto: str) -> str:
    """Mascara dados pessoais e de pacientes antes da chamada ao LLM."""
    texto = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "[CPF_REDIGIDO]", texto)
    texto = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b", "[EMAIL_REDIGIDO]", texto)
    texto = re.sub(r"\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b", "[TELEFONE_REDIGIDO]", texto)
    texto = re.sub(
        r"(?i)(paciente|prontu[aá]rio|titular)\s*:\s*[^\n,;]+",
        r"\1: [DADO_PESSOAL_REDIGIDO_LGPD]",
        texto,
    )
    return texto


def classificar_chamado_hospitalar(texto_bruto: str) -> dict:
    texto_seguro = anonimizar_dados_lgpd(texto_bruto)
    resp = bedrock.converse(
        modelId=MODELO,
        system=[
            {
                "text": (
                    "Você realiza triagem de manutenção de equipamentos hospitalares (engenharia clínica). "
                    "Responda apenas em JSON puro: "
                    '{"equipamento": str, "resumo": str, "urgencia": "baixa|media|alta"}'
                )
            }
        ],
        messages=[{"role": "user", "content": [{"text": texto_seguro}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0},
    )
    conteudo = resp["output"]["message"]["content"][0]["text"]
    inicio, fim = conteudo.find("{"), conteudo.rfind("}")
    dados = json.loads(conteudo[inicio : fim + 1]) if inicio != -1 else {"resumo": conteudo, "urgencia": "revisao_humana"}
    return {
        "texto_anonimizado_enviado_ao_llm": texto_seguro,
        "classificacao": dados,
        "tokens_in": resp["usage"]["inputTokens"],
        "tokens_out": resp["usage"]["outputTokens"],
    }


if __name__ == "__main__":
    with open("exemplos/chamado-saude-01.txt", "r", encoding="utf-8") as arq:
        chamado = arq.read()
    resultado = classificar_chamado_hospitalar(chamado)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
