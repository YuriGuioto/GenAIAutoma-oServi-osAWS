#!/usr/bin/env python3
"""
Alternativa sem IA (Baseline determinístico por palavras-chave em Python — Etapa 6).
Classifica os mesmos relatórios de campo sem custo de tokens do Bedrock,
permitindo comparar acurácia, latência (< 1 ms) e custo operacional mensal.
"""

import time

PALAVRAS_ALTA = {
    "urgente",
    "crítico",
    "critico",
    "curto-circuito",
    "parou completamente",
    "perda severa",
    "risco iminente",
    "foco severo",
    "bicho-mineiro",
}

PALAVRAS_MEDIA = {
    "queda de pressão",
    "entupimento parcial",
    "preventiva",
    "48 horas",
    "deficiência",
    "moderada",
}


def classificar_por_regras(texto: str) -> dict:
    texto_lower = texto.lower()
    linhas = [l.strip() for l in texto.strip().splitlines() if l.strip()]
    resumo_simples = linhas[-1][:160] if linhas else "Sem conteúdo"

    for termo in PALAVRAS_ALTA:
        if termo in texto_lower:
            return {"resumo": resumo_simples, "urgencia": "alta", "metodo": "regras_fixas"}

    for termo in PALAVRAS_MEDIA:
        if termo in texto_lower:
            return {"resumo": resumo_simples, "urgencia": "media", "metodo": "regras_fixas"}

    return {"resumo": resumo_simples, "urgencia": "baixa", "metodo": "regras_fixas"}


if __name__ == "__main__":
    arquivos = [
        ("exemplos/relatorio-baixa.txt", "baixa"),
        ("exemplos/relatorio-media.txt", "media"),
        ("exemplos/relatorio-alta.txt", "alta"),
    ]
    print("=== Classificador por Regras Fixas (Sem IA / Custo Zero de Tokens) ===")
    for caminho, esperado in arquivos:
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read()
        t0 = time.perf_counter()
        saida = classificar_por_regras(conteudo)
        ms = (time.perf_counter() - t0) * 1000
        print(
            f"Arquivo: {caminho:<28} | Esperado: {esperado:<6} | "
            f"Obtido: {saida['urgencia']:<6} | Latência: {ms:.3f} ms"
        )
