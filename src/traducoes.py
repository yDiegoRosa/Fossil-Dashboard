"""
src/traducoes.py
================
Nomes em portugues para exibicao no app.

O dataset processado guarda periodos, continentes e paises em ingles,
como vem da PBDB e do pycountry; o app traduz ao carregar os dados.
Valores sem traducao (ex.: "Desconhecido") ficam como estao.
"""

import unicodedata
from collections.abc import Iterable

import pandas as pd

# Em ordem cronologica
ERAS = {
    "Triassic": "Triássico",
    "Jurassic": "Jurássico",
    "Cretaceous": "Cretáceo",
}

CONTINENTES = {
    "Africa": "África",
    "Antarctica": "Antártida",
    "Asia": "Ásia",
    "Europe": "Europa",
    "North America": "América do Norte",
    "Oceania": "Oceania",
    "South America": "América do Sul",
}

# Nome oficial do pycountry (ISO 3166) -> nome usual no Brasil
PAISES = {
    "Afghanistan": "Afeganistão",
    "Algeria": "Argélia",
    "Angola": "Angola",
    "Antarctica": "Antártida",
    "Argentina": "Argentina",
    "Armenia": "Armênia",
    "Australia": "Austrália",
    "Austria": "Áustria",
    "Belgium": "Bélgica",
    "Bolivia, Plurinational State of": "Bolívia",
    "Botswana": "Botsuana",
    "Brazil": "Brasil",
    "Bulgaria": "Bulgária",
    "Cambodia": "Camboja",
    "Cameroon": "Camarões",
    "Canada": "Canadá",
    "Chile": "Chile",
    "China": "China",
    "Colombia": "Colômbia",
    "Congo, The Democratic Republic of the": "República Democrática do Congo",
    "Croatia": "Croácia",
    "Cuba": "Cuba",
    "Czechia": "Tchéquia",
    "Denmark": "Dinamarca",
    "Ecuador": "Equador",
    "Egypt": "Egito",
    "Ethiopia": "Etiópia",
    "Falkland Islands (Malvinas)": "Ilhas Malvinas",
    "France": "França",
    "Georgia": "Geórgia",
    "Germany": "Alemanha",
    "Guyana": "Guiana",
    "Honduras": "Honduras",
    "Hungary": "Hungria",
    "Iceland": "Islândia",
    "India": "Índia",
    "Iran, Islamic Republic of": "Irã",
    "Israel": "Israel",
    "Italy": "Itália",
    "Japan": "Japão",
    "Jordan": "Jordânia",
    "Kazakhstan": "Cazaquistão",
    "Korea, Democratic People's Republic of": "Coreia do Norte",
    "Korea, Republic of": "Coreia do Sul",
    "Kyrgyzstan": "Quirguistão",
    "Lao People's Democratic Republic": "Laos",
    "Lebanon": "Líbano",
    "Lesotho": "Lesoto",
    "Libya": "Líbia",
    "Luxembourg": "Luxemburgo",
    "Madagascar": "Madagascar",
    "Malawi": "Malawi",
    "Malaysia": "Malásia",
    "Mali": "Mali",
    "Mexico": "México",
    "Mongolia": "Mongólia",
    "Morocco": "Marrocos",
    "Myanmar": "Mianmar",
    "Namibia": "Namíbia",
    "Netherlands": "Países Baixos",
    "New Zealand": "Nova Zelândia",
    "Niger": "Níger",
    "Norway": "Noruega",
    "Oman": "Omã",
    "Pakistan": "Paquistão",
    "Palestine, State of": "Palestina",
    "Paraguay": "Paraguai",
    "Peru": "Peru",
    "Poland": "Polônia",
    "Portugal": "Portugal",
    "Romania": "Romênia",
    "Russian Federation": "Rússia",
    "Slovenia": "Eslovênia",
    "South Africa": "África do Sul",
    "Spain": "Espanha",
    "Sudan": "Sudão",
    "Svalbard and Jan Mayen": "Svalbard e Jan Mayen",
    "Sweden": "Suécia",
    "Switzerland": "Suíça",
    "Syrian Arab Republic": "Síria",
    "Tajikistan": "Tadjiquistão",
    "Tanzania, United Republic of": "Tanzânia",
    "Thailand": "Tailândia",
    "Tunisia": "Tunísia",
    "Turkmenistan": "Turcomenistão",
    "Ukraine": "Ucrânia",
    "United Kingdom": "Reino Unido",
    "United States": "Estados Unidos",
    "Uruguay": "Uruguai",
    "Uzbekistan": "Uzbequistão",
    "Venezuela, Bolivarian Republic of": "Venezuela",
    "Viet Nam": "Vietnã",
    "Yemen": "Iêmen",
    "Zambia": "Zâmbia",
    "Zimbabwe": "Zimbábue",
}


def traduzir(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna uma copia com as colunas era, continente e pais em portugues."""
    df = df.copy()
    for coluna, nomes in (
        ("era", ERAS),
        ("continente", CONTINENTES),
        ("pais", PAISES),
    ):
        df[coluna] = df[coluna].map(nomes).fillna(df[coluna])
    return df


def ordenar(nomes: Iterable[str]) -> list[str]:
    """
    Ordem alfabetica ignorando acentos: no sorted() puro, nomes com
    letra acentuada ("África do Sul", "Índia") iriam para o fim da lista.
    """
    def chave(nome: str) -> str:
        sem_acento = unicodedata.normalize("NFKD", nome)
        return sem_acento.encode("ascii", "ignore").decode().casefold()

    return sorted(nomes, key=chave)
