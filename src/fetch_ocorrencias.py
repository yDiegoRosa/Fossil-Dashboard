"""
fetch_ocorrencias.py
Busca todas as ocorrências de Dinosauria com coordenadas
geográficas e dados temporais da API PaleobioDB v1.2.

Salva o JSON bruto em data/raw/ocorrencias.json.
"""

import json
import os
import requests

BASE_URL = "https://paleobiodb.org/data1.2"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ocorrencias.json")

PARAMS = {
    "base_name": "Dinosauria",
    "show": "coords,coll,time",
    "limit": "all",
}

COLUNAS_OBRIGATORIAS = {"lat", "lng", "oei"}


def fetch():
    print("=" * 60)
    print("Buscando ocorrências de Dinosauria...")
    print(f"Endpoint: {BASE_URL}/occs/list.json")
    print(f"Parâmetros: {PARAMS}")
    print("=" * 60)

    response = requests.get(
        f"{BASE_URL}/occs/list.json",
        params=PARAMS,
        timeout=120,
    )
    response.raise_for_status()

    dados = response.json()
    registros = dados.get("records", [])

    total = len(registros)
    print(f"\n[OK] Status: {response.status_code}")
    print(f"[DADOS] Total de registros retornados: {total}")

    # ------------------------------------------
    # Validação das colunas obrigatórias
    # ------------------------------------------
    if registros:
        colunas = set(registros[0].keys())
        print(f"[COLS] Colunas: {sorted(colunas)}")

        faltando = COLUNAS_OBRIGATORIAS - colunas
        if faltando:
            print(f"\n[ERRO] Colunas obrigatorias ausentes: {faltando}")
            raise SystemExit(1)

        print(f"[OK] Colunas obrigatorias presentes: {sorted(COLUNAS_OBRIGATORIAS)}")
    else:
        print("[AVISO] Nenhum registro retornado.")
        raise SystemExit(1)

    # ------------------------------------------
    # Salvar JSON bruto
    # ------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    tamanho_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"\n[SALVO] {OUTPUT_FILE}")
    print(f"[TAMANHO] {tamanho_mb:.1f} MB")
    print(f"[TOTAL] {total} registros")


if __name__ == "__main__":
    fetch()
