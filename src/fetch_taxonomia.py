"""
fetch_taxonomia.py
Busca a hierarquia taxonomica completa de Dinosauria
(familia, ordem, clado) via API PaleobioDB v1.2.

Salva o resultado em data/raw/taxonomia.json para
ser usado no enriquecimento do dataset principal.
"""

import json
import os
import requests

BASE_URL = "https://paleobiodb.org/data1.2"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "taxonomia.json")

PARAMS = {
    "base_name": "Dinosauria",
    "rel": "all_children",
    "show": "attr,size",
    "limit": "all",
}

COLUNAS_ESPERADAS = {"oid", "nam", "rnk"}


def fetch():
    print("=" * 60)
    print("Buscando hierarquia taxonomica de Dinosauria...")
    print(f"Endpoint: {BASE_URL}/taxa/list.json")
    print(f"Parametros: {PARAMS}")
    print("=" * 60)

    response = requests.get(
        f"{BASE_URL}/taxa/list.json",
        params=PARAMS,
        timeout=120,
    )
    response.raise_for_status()

    dados = response.json()
    registros = dados.get("records", [])
    total = len(registros)

    print(f"\n[OK] Status: {response.status_code}")
    print(f"[DADOS] Total de taxa retornados: {total}")

    # ------------------------------------------
    # Validacao das colunas esperadas
    # ------------------------------------------
    if registros:
        colunas = set(registros[0].keys())
        print(f"[COLS] Colunas: {sorted(colunas)}")

        faltando = COLUNAS_ESPERADAS - colunas
        if faltando:
            print(f"[ERRO] Colunas esperadas ausentes: {faltando}")
            raise SystemExit(1)

        print(f"[OK] Colunas esperadas presentes: {sorted(COLUNAS_ESPERADAS)}")

        # Distribuicao por rank taxonomico
        ranks = {}
        for r in registros:
            rank = r.get("rnk", "desconhecido")
            ranks[rank] = ranks.get(rank, 0) + 1

        print("\n[RANKS] Distribuicao por rank taxonomico:")
        for rank, count in sorted(ranks.items(), key=lambda x: -x[1])[:10]:
            print(f"  {rank:<25} {count:>5} taxa")
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
    print(f"[TOTAL] {total} taxa")


if __name__ == "__main__":
    fetch()
