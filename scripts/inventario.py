#!/usr/bin/env python3
"""
Script de inventário de recursos AWS (S3, DynamoDB e IAM).
Regra de qualidade: NÃO utiliza endpoint_url fixo (hardcoded) no código.
O boto3 resolve automaticamente o endpoint http://localhost:4566 a partir
do perfil configurado em AWS_PROFILE=floci (~/.aws/config) ou de AWS_ENDPOINT_URL.
"""

import os
import sys
import boto3
from botocore.exceptions import BotoCoreError, ClientError


def validar_ambiente_floci(sessao: boto3.Session) -> str:
    """Garante que o script está executando na conta fictícia 000000000000 do Floci."""
    sts = sessao.client("sts")
    identidade = sts.get_caller_identity()
    conta = identidade.get("Account", "")
    if conta != "000000000000":
        raise RuntimeError(
            f"BLOQUEIO DE SEGURANÇA: Conta {conta} detectada! "
            "Defina AWS_PROFILE=floci antes de rodar o script."
        )
    return identidade.get("Arn", "")


def listar_inventario() -> None:
    perfil = os.environ.get("AWS_PROFILE", "floci")
    sessao = boto3.Session(profile_name=perfil)

    arn_atual = validar_ambiente_floci(sessao)
    print(f"[OK] Conectado ao Floci | Identidade: {arn_atual} (perfil: {perfil})\n")

    # 1. Listar Buckets S3
    s3 = sessao.client("s3")
    resp_s3 = s3.list_buckets()
    buckets = [b["Name"] for b in resp_s3.get("Buckets", [])]
    print(f"=== Buckets S3 ({len(buckets)}) ===")
    for nome_bucket in buckets:
        print(f"  - s3://{nome_bucket}")
    print()

    # 2. Listar Tabelas DynamoDB
    dynamodb = sessao.client("dynamodb")
    resp_ddb = dynamodb.list_tables()
    tabelas = resp_ddb.get("TableNames", [])
    print(f"=== Tabelas DynamoDB ({len(tabelas)}) ===")
    for nome_tabela in tabelas:
        print(f"  - {nome_tabela}")
    print()

    # 3. Listar Usuários IAM
    iam = sessao.client("iam")
    resp_iam = iam.list_users()
    usuarios = resp_iam.get("Users", [])
    print(f"=== Usuários IAM ({len(usuarios)}) ===")
    for u in usuarios:
        print(f"  - {u['UserName']} (ARN: {u['Arn']})")


if __name__ == "__main__":
    try:
        listar_inventario()
    except (BotoCoreError, ClientError, RuntimeError) as erro:
        print(f"[ERRO] Falha ao consultar inventário: {erro}", file=sys.stderr)
        sys.exit(1)
