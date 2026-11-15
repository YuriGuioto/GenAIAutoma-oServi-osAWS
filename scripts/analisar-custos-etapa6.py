#!/usr/bin/env python3
"""
Calculadora de Custos e Ponto de Equilíbrio (Break-even) — Etapa 6 (Competência 98).
1. Lê os itens reais gravados na tabela DynamoDB 'triagem' (Etapa 4).
2. Calcula a média real de inputTokens e outputTokens por relatório.
3. Calcula o custo unitário e projeta para 500 relatórios/dia (15.000 relatórios/mês).
4. Compara 3 arquiteturas:
   - Opção A: Serverless GenAI (S3 + Lambda + Bedrock On-Demand + DynamoDB)
   - Opção B: Serverless Regras Fixas em Python (S3 + Lambda + DynamoDB, sem Bedrock)
   - Opção C: Modelo Local dedicado em EC2 com GPU (g5.xlarge ligada 24h = 730h/mês)

AVISO IMPORTANTE: Os valores abaixo são variáveis configuráveis de referência (us-east-1).
Você DEVE conferir a página oficial de preços da AWS (https://aws.amazon.com/bedrock/pricing/
e https://aws.amazon.com/ec2/pricing/on-demand/) na data do seu estudo e ajustar se necessário.
"""

import os
import boto3

PRECO_1K_INPUT_HAIKU_USD = float(os.environ.get("PRECO_1K_IN_HAIKU", "0.00025"))
PRECO_1K_OUTPUT_HAIKU_USD = float(os.environ.get("PRECO_1K_OUT_HAIKU", "0.00125"))

PRECO_1K_INPUT_NOVA_MICRO_USD = float(os.environ.get("PRECO_1K_IN_NOVA", "0.000035"))
PRECO_1K_OUTPUT_NOVA_MICRO_USD = float(os.environ.get("PRECO_1K_OUT_NOVA", "0.000140"))

PRECO_HORA_EC2_GPU_G4DN_USD = float(os.environ.get("PRECO_HORA_G4DN", "0.526"))
PRECO_HORA_EC2_GPU_G5_USD = float(os.environ.get("PRECO_HORA_G5", "1.006"))
HORAS_MES = 730

RELATORIOS_POR_DIA = 500
DIAS_MES = 30
RELATORIOS_POR_MES = RELATORIOS_POR_DIA * DIAS_MES


def obter_medias_dynamodb(nome_tabela: str = "triagem") -> tuple[float, float, int]:
    perfil = os.environ.get("AWS_PROFILE", "floci")
    sessao = boto3.Session(profile_name=perfil)
    ddb = sessao.resource("dynamodb")
    tabela = ddb.Table(nome_tabela)

    itens = tabela.scan().get("Items", [])
    if not itens:
        raise RuntimeError(
            f"A tabela '{nome_tabela}' está vazia. Execute ./scripts/testar-etapa4.sh primeiro."
        )

    total_in = sum(float(i.get("tokens_in", 0)) for i in itens)
    total_out = sum(float(i.get("tokens_out", 0)) for i in itens)
    qtd = len(itens)
    return total_in / qtd, total_out / qtd, qtd


def calcular_custo_modelo(media_in: float, media_out: float, preco_1k_in: float, preco_1k_out: float) -> dict:
    custo_por_relatorio = (media_in / 1000.0) * preco_1k_in + (media_out / 1000.0) * preco_1k_out
    custo_mensal_500_dia = custo_por_relatorio * RELATORIOS_POR_MES
    return {
        "custo_unitario_usd": custo_por_relatorio,
        "custo_mensal_15k_usd": custo_mensal_500_dia,
    }


def main():
    print("======================================================================")
    print(" ANÁLISE DE CUSTO REAL E PROJEÇÃO FINANCEIRA — ETAPA 6 (AG822)")
    print(" AVISO: Confira os preços vigentes em https://aws.amazon.com/bedrock/pricing/")
    print("======================================================================\n")

    media_in, media_out, qtd_amostras = obter_medias_dynamodb("triagem")
    print(f"1. Métricas Reais Lidas do DynamoDB (amostra de {qtd_amostras} relatórios):")
    print(f"   - Média de Tokens de Entrada (inputTokens):  {media_in:.2f} tokens/relatório")
    print(f"   - Média de Tokens de Saída   (outputTokens): {media_out:.2f} tokens/relatório")
    print(f"   - Volume projetado: {RELATORIOS_POR_DIA} relatórios/dia = {RELATORIOS_POR_MES} relatórios/mês\n")

    haiku = calcular_custo_modelo(media_in, media_out, PRECO_1K_INPUT_HAIKU_USD, PRECO_1K_OUTPUT_HAIKU_USD)
    nova = calcular_custo_modelo(media_in, media_out, PRECO_1K_INPUT_NOVA_MICRO_USD, PRECO_1K_OUTPUT_NOVA_MICRO_USD)

    custo_mensal_g4dn = PRECO_HORA_EC2_GPU_G4DN_USD * HORAS_MES
    custo_mensal_g5 = PRECO_HORA_EC2_GPU_G5_USD * HORAS_MES

    breakeven_haiku_g4dn = int(custo_mensal_g4dn / haiku["custo_unitario_usd"]) if haiku["custo_unitario_usd"] > 0 else 0
    breakeven_haiku_g5 = int(custo_mensal_g5 / haiku["custo_unitario_usd"]) if haiku["custo_unitario_usd"] > 0 else 0

    print("2. Comparativo Mensal para 500 relatórios/dia (15.000 relatórios/mês):")
    print(f"   [A1] Bedrock Claude 3 Haiku:  US$ {haiku['custo_unitario_usd']:.6f}/relatório | US$ {haiku['custo_mensal_15k_usd']:.4f}/mês")
    print(f"   [A2] Bedrock Nova Micro:      US$ {nova['custo_unitario_usd']:.6f}/relatório | US$ {nova['custo_mensal_15k_usd']:.4f}/mês")
    print("   [B]  Regras Fixas (Python):   US$ 0.000000/relatório em IA | US$ 0.00/mês (dentro do Free Tier de Lambda/S3/DDB)")
    print(f"   [C1] EC2 GPU g4dn.xlarge 24h: US$ {custo_mensal_g4dn:.2f}/mês ({HORAS_MES}h x US$ {PRECO_HORA_EC2_GPU_G4DN_USD}/h)")
    print(f"   [C2] EC2 GPU g5.xlarge 24h:   US$ {custo_mensal_g5:.2f}/mês ({HORAS_MES}h x US$ {PRECO_HORA_EC2_GPU_G5_USD}/h)\n")

    print("3. Ponto de Equilíbrio (A partir de que volume a EC2 com GPU 24h compensa vs. Claude 3 Haiku):")
    print(f"   - Para empatar com g4dn.xlarge (US$ {custo_mensal_g4dn:.2f}/mês): ~{breakeven_haiku_g4dn:,} relatórios/mês (~{breakeven_haiku_g4dn // 30:,}/dia)")
    print(f"   - Para empatar com g5.xlarge   (US$ {custo_mensal_g5:.2f}/mês): ~{breakeven_haiku_g5:,} relatórios/mês (~{breakeven_haiku_g5 // 30:,}/dia)")


if __name__ == "__main__":
    main()
