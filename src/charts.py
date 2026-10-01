"""
src/charts.py
=============
Funcoes de visualizacao para o Fossil Dashboard.

Cada funcao recebe um DataFrame (ja filtrado) e retorna
um objeto de visualizacao (folium.Map ou plotly Figure).

Tarefas:
  4.1  criar_mapa_calor        — HeatMap + FastMarkerCluster (Folium)
  4.2  criar_timeline_diversidade — barras empilhadas      (Plotly)
  4.3  criar_ranking_paises     — barras horizontais       (Plotly)
       criar_treemap_clados     — treemap hierarquico      (Plotly)
  4.4  criar_timeline_generos   — Gantt de generos         (Plotly)
"""

import html

import folium
from folium import MacroElement
from folium.plugins import FastMarkerCluster, HeatMap
from folium.template import Template
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd

from src.traducoes import ERAS

# ── Paleta de cores ─────────────────────────────────────────────────
# Os nomes dos periodos ja chegam traduzidos (ver src/traducoes.py)
ERA_COLORS = {
    ERAS["Triassic"]: "#E07A5F",     # terracotta
    ERAS["Jurassic"]: "#3D405B",     # dark blue-grey
    ERAS["Cretaceous"]: "#81B29A",   # sage green
    "Desconhecido": "#999999",
}

ERA_ORDER = [*ERAS.values(), "Desconhecido"]

# Tema escuro com numeros no formato brasileiro (1.234,5)
_PLOTLY_TEMPLATE = go.layout.Template(pio.templates["plotly_dark"])
_PLOTLY_TEMPLATE.layout.separators = ",."


# =====================================================================
# 4.1 — Mapa de calor de ocorrencias
# =====================================================================

# As coordenadas da PBDB raramente tem precisao melhor que algumas centenas
# de metros, e o mapa base escuro da Esri so tem tiles ate o zoom 16
_MAPA_MAX_ZOOM = 14


class _CorrecaoHeatMap(MacroElement):
    """
    Substitui o _redraw do leaflet.heat distribuido pelo folium.

    A versao do folium agrupa TODOS os pontos (inclusive os fora da tela) em
    arrays aninhados indexados pela posicao em pixels. Como o mundo dobra de
    tamanho a cada nivel de zoom, esses arrays ficam gigantes e esparsos e o
    navegador trava (~6 s por zoom no nivel 13). Aqui a grade e um Map com
    apenas as celulas ocupadas: o custo depende so do numero de pontos, nao
    do zoom, e o desenho resultante e o mesmo.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        L.HeatLayer.prototype._redraw = function () {
            if (!this._map) { return; }
            var r = this._heat._r,
                size = this._map.getSize(),
                bounds = new L.Bounds(L.point([-r, -r]), size.add([r, r])),
                cellSize = r / 2,
                panePos = this._map._getMapPanePos(),
                offsetX = panePos.x % cellSize,
                offsetY = panePos.y % cellSize,
                grid = new Map(),
                max = 1,
                data = [];

            for (var i = 0, len = this._latlngs.length; i < len; i++) {
                var latlng = this._latlngs[i],
                    p = this._map.latLngToContainerPoint(latlng),
                    key = Math.floor((p.x - offsetX) / cellSize) + ":" +
                          Math.floor((p.y - offsetY) / cellSize),
                    k = latlng.alt !== undefined ? latlng.alt :
                        latlng[2] !== undefined ? +latlng[2] : 1,
                    cell = grid.get(key);
                if (cell) {
                    cell[0] = (cell[0] * cell[2] + p.x * k) / (cell[2] + k);
                    cell[1] = (cell[1] * cell[2] + p.y * k) / (cell[2] + k);
                    cell[2] += k;
                } else {
                    cell = [p.x, p.y, k];
                    cell.p = p;
                    grid.set(key, cell);
                }
                if (cell[2] > max) { max = cell[2]; }
            }

            this._max = max;
            this._heat.max(max);
            grid.forEach(function (cell) {
                if (bounds.contains(cell.p)) {
                    data.push([
                        Math.round(cell[0]),
                        Math.round(cell[1]),
                        Math.min(cell[2], max),
                    ]);
                }
            });
            this._heat.data(data).draw(this.options.minOpacity);
            this._frame = null;
        };
        {% endmacro %}
    """)


# Cria cada marcador no navegador a partir de uma linha de dados:
# [lat, lng, nome, pais, ocorrencias, idade_max, idade_min, taxons].
# O popup so e montado quando o usuario clica.
_JS_MARCADOR = """
function (row) {
    var marker = L.circleMarker(new L.LatLng(row[0], row[1]), {
        radius: 5,
        weight: 1,
        color: "#fd8d3c",
        fillColor: "#fd8d3c",
        fillOpacity: 0.8,
        ocorrencias: row[4]
    });
    marker.bindPopup(function () {
        var fmt = function (v) {
            return v.toLocaleString("pt-BR", {maximumFractionDigits: 1});
        };
        return "<b>" + row[2] + "</b><br>" + row[3] + "<br>"
            + fmt(row[4]) + (row[4] === 1 ? " ocorrência" : " ocorrências") + "<br>"
            + "Idade: " + fmt(row[5]) + " a " + fmt(row[6]) + " Ma<br>"
            + "Táxons: <i>" + row[7] + "</i>";
    }, {maxWidth: 280});
    return marker;
}
"""

# Rotulo do cluster = soma das ocorrencias dos sitios agrupados
# (e nao o numero de marcadores), para bater com o mapa de calor e os cards
_JS_ICONE_CLUSTER = """
function (cluster) {
    var total = 0;
    cluster.getAllChildMarkers().forEach(function (m) {
        total += m.options.ocorrencias;
    });
    var tamanho = total < 100 ? "small" : total < 1000 ? "medium" : "large";
    var rotulo = total >= 10000 ? Math.round(total / 1000) + "k"
        : total >= 1000 ? (total / 1000).toFixed(1).replace(".", ",") + "k"
        : total;
    return L.divIcon({
        html: "<div><span>" + rotulo + "</span></div>",
        className: "marker-cluster marker-cluster-" + tamanho,
        iconSize: new L.Point(40, 40)
    });
}
"""


def _agregar_por_local(df: pd.DataFrame) -> pd.DataFrame:
    """
    Uma linha por coordenada (varias coletas podem dividir o mesmo ponto),
    com nome do sitio, pais, numero de ocorrencias, faixa de idade e os
    tres taxons mais frequentes. Textos ja escapados para HTML.
    """
    chaves = ["lat", "lng"]
    locais = df.groupby(chaves, sort=False).agg(
        nome=("cnm", "first"),
        pais=("pais", "first"),
        ocorrencias=("oid", "size"),
        idade_max=("eag", "max"),
        idade_min=("lag", "min"),
    )
    locais["taxons"] = (
        df.groupby([*chaves, "tna"]).size().reset_index(name="n")
        .sort_values("n", ascending=False, kind="stable")
        .groupby(chaves, sort=False).head(3)
        .groupby(chaves, sort=False)["tna"]
        .agg(", ".join)
    )
    for coluna in ("nome", "pais", "taxons"):
        locais[coluna] = locais[coluna].astype(str).map(html.escape)
    return locais.reset_index()


def criar_mapa_calor(df: pd.DataFrame) -> folium.Map:
    """
    Mapa de calor global + clusters de sitios com popups.

    Parametros
    ----------
    df : DataFrame filtrado com colunas lat, lng, oid, cnm, pais, eag, lag, tna.

    Retorna
    -------
    folium.Map
    """
    # prefer_canvas: os marcadores sao desenhados num unico <canvas>
    # em vez de milhares de elementos SVG
    mapa = folium.Map(
        location=[20, 0],
        zoom_start=2,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
    )
    # Com tiles=None o folium ignora min_zoom/max_zoom do Map; o Leaflet
    # usa os limites das camadas de tiles, entao eles vao em cada uma
    limites_zoom = {"min_zoom": 2, "max_zoom": _MAPA_MAX_ZOOM}
    # Mapa base escuro da Esri: gratuito e sem chave de API
    # (os tiles da CARTO passaram a exigir chave e exibiam "API KEY REQUIRED")
    folium.TileLayer(
        tiles=(
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        ),
        attr="Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
        name="Escuro (Esri)",
        **limites_zoom,
    ).add_to(mapa)
    # show=False: sem isso o OSM fica por cima e o mapa abre claro
    folium.TileLayer(
        "OpenStreetMap",
        name="Claro (OpenStreetMap)",
        show=False,
        **limites_zoom,
    ).add_to(mapa)

    locais = _agregar_por_local(df)

    # Precisa vir antes do HeatMap para valer desde o primeiro desenho
    _CorrecaoHeatMap().add_to(mapa)

    # Um ponto por local com peso = ocorrencias: o leaflet.heat soma os pesos
    # de cada celula, entao o resultado e igual a passar todas as ocorrencias
    HeatMap(
        locais[["lat", "lng", "ocorrencias"]].values.tolist(),
        name="Mapa de calor",
        radius=8,
        blur=12,
        max_zoom=6,
        gradient={
            0.2: "#ffffb2",
            0.4: "#fecc5c",
            0.6: "#fd8d3c",
            0.8: "#f03b20",
            1.0: "#bd0026",
        },
    ).add_to(mapa)

    # Todos os locais (e nao uma amostra), criados no navegador via JS:
    # o HTML enviado ao Streamlit fica ~5x menor do que com um
    # folium.CircleMarker + Popup por ponto
    colunas = [
        "lat", "lng", "nome", "pais",
        "ocorrencias", "idade_max", "idade_min", "taxons",
    ]
    FastMarkerCluster(
        locais[colunas].values.tolist(),
        callback=_JS_MARCADOR,
        icon_create_function=_JS_ICONE_CLUSTER,
        name="Sítios fósseis",
    ).add_to(mapa)

    # Enquadra os dados quando eles cobrem so parte do mundo (ex.: ao
    # filtrar um pais); com dados globais fica a visao inicial acima
    if locais["lng"].max() - locais["lng"].min() < 180:
        mapa.fit_bounds(
            [
                [locais["lat"].min(), locais["lng"].min()],
                [locais["lat"].max(), locais["lng"].max()],
            ],
            padding=(30, 30),
            max_zoom=8,
        )

    folium.LayerControl().add_to(mapa)
    return mapa


# =====================================================================
# 4.2 — Timeline de diversidade por periodo geologico
# =====================================================================

def criar_timeline_diversidade(df: pd.DataFrame) -> go.Figure:
    """
    Barras empilhadas: contagem de especies unicas por era e familia.
    Inclui anotacao do evento K-Pg.
    """
    # Agrupar por era + familia, contar especies unicas
    # Apenas táxons em nível de espécie (rnk = 3); grupos como "Theropoda" não contam
    agrupado = (
        df[df["rnk"] == 3].groupby(["era", "familia"])["tna"]
        .nunique()
        .reset_index(name="especies")
    )

    # Top 10 familias para legibilidade
    top_familias = (
        agrupado.groupby("familia")["especies"]
        .sum()
        .nlargest(10)
        .index.tolist()
    )
    agrupado["familia_plot"] = agrupado["familia"].where(
        agrupado["familia"].isin(top_familias), "Outras"
    )

    # Ordem das eras
    agrupado["era"] = pd.Categorical(
        agrupado["era"], categories=ERA_ORDER, ordered=True
    )
    agrupado = agrupado.sort_values("era")

    fig = px.bar(
        agrupado,
        x="era",
        y="especies",
        color="familia_plot",
        template=_PLOTLY_TEMPLATE,
        labels={
            "era": "Período Geológico",
            "especies": "Espécies Únicas",
            "familia_plot": "Família",
        },
        title="Diversidade de Espécies por Período Geológico",
        color_discrete_sequence=px.colors.qualitative.Set3,
    )

    fig.update_layout(
        barmode="stack",
        legend_title_text="Família",
        xaxis_title="",
        yaxis_title="Espécies Únicas",
        margin=dict(t=60, b=40),
    )

    # Anotacao K-Pg
    fig.add_annotation(
        x=ERAS["Cretaceous"],
        y=0,
        yref="y",
        text="K-Pg (66 Ma) - Extinção em massa",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#ff6b6b",
        font=dict(color="#ff6b6b", size=11),
        ax=0,
        ay=-50,
    )

    return fig


# =====================================================================
# 4.3 — Ranking de paises e treemap de clados
# =====================================================================

def criar_ranking_paises(df: pd.DataFrame) -> go.Figure:
    """Top 15 paises com mais registros de fosseis."""
    contagem = (
        df.groupby("pais")
        .size()
        .reset_index(name="registros")
        .nlargest(15, "registros")
        .sort_values("registros")
    )

    fig = px.bar(
        contagem,
        x="registros",
        y="pais",
        orientation="h",
        template=_PLOTLY_TEMPLATE,
        title="Top 15 Países com Mais Fósseis de Dinossauros",
        labels={"registros": "Registros", "pais": ""},
        color="registros",
        color_continuous_scale="YlOrRd",
    )

    fig.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(t=60, b=40, l=120),
        yaxis=dict(tickfont=dict(size=12)),
    )

    return fig


def criar_treemap_clados(df: pd.DataFrame) -> go.Figure:
    """Treemap hierarquico: familia -> especie com contagem de ocorrencias."""
    agrupado = (
        df.groupby(["familia", "tna"])
        .size()
        .reset_index(name="ocorrencias")
    )

    # Filtrar para familias com pelo menos 5 ocorrencias para legibilidade
    familias_relevantes = (
        agrupado.groupby("familia")["ocorrencias"]
        .sum()
        .loc[lambda s: s >= 5]
        .index
    )
    agrupado = agrupado[agrupado["familia"].isin(familias_relevantes)]

    fig = px.treemap(
        agrupado,
        path=["familia", "tna"],
        values="ocorrencias",
        template=_PLOTLY_TEMPLATE,
        title="Distribuição Taxonômica — Família / Táxon",
        color="ocorrencias",
        color_continuous_scale="Viridis",
    )

    fig.update_layout(
        margin=dict(t=60, b=20, l=10, r=10),
        coloraxis_showscale=False,
    )

    return fig


# =====================================================================
# 4.4 — Linha do tempo de surgimento e extincao de generos
# =====================================================================

def criar_timeline_generos(df: pd.DataFrame) -> go.Figure:
    """
    Gantt horizontal mostrando a duracao de cada genero no registro fossil.
    Limitado aos 30 generos com mais ocorrencias.

    Usa eag (early_age, Ma) como inicio e lag (late_age, Ma) como fim.
    """
    # Extrair genero (primeiro nome do tna)
    # Apenas nomes em nível de gênero ou abaixo (rnk <= 5); evita que clados
    # como "Theropoda" ou "Dinosauria" apareçam como se fossem gêneros
    df = df[df["rnk"] <= 5].copy()
    df["genero"] = df["tna"].str.split().str[0]

    # Top 30 generos por contagem de ocorrencias
    top_generos = (
        df["genero"]
        .value_counts()
        .head(30)
        .index.tolist()
    )
    df_top = df[df["genero"].isin(top_generos)]

    # Para cada genero: eag max (mais antigo) e lag min (mais recente)
    resumo = (
        df_top.groupby("genero")
        .agg(
            inicio=("eag", "max"),
            fim=("lag", "min"),
            ocorrencias=("oid", "count"),
        )
        .reset_index()
        .sort_values("inicio", ascending=True)
    )

    # Converter Ma para datas ficticias para o timeline do Plotly
    # Plotly timeline precisa de datetime, entao usamos uma escala linear
    # Alternativa: usar barras horizontais com go.Bar

    fig = go.Figure()

    def fmt_ma(valor: float) -> str:
        """Idade com virgula decimal (ex.: 201,3)."""
        return f"{valor:.1f}".replace(".", ",")

    colors = px.colors.qualitative.Alphabet
    for i, row in resumo.iterrows():
        idx = i % len(colors)
        fig.add_trace(go.Bar(
            y=[row["genero"]],
            x=[row["inicio"] - row["fim"]],
            base=[row["fim"]],
            orientation="h",
            marker=dict(color=colors[idx], opacity=0.85),
            hovertemplate=(
                f"<b>{row['genero']}</b><br>"
                f"Surgimento: {fmt_ma(row['inicio'])} Ma<br>"
                f"Último registro: {fmt_ma(row['fim'])} Ma<br>"
                f"Ocorrências: {row['ocorrencias']}<br>"
                "<extra></extra>"
            ),
            showlegend=False,
        ))

    fig.update_layout(
        template=_PLOTLY_TEMPLATE,
        title="Surgimento e Extinção dos 30 Gêneros Mais Registrados",
        xaxis=dict(
            title="Milhões de anos atrás (Ma)",
            autorange="reversed",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.1)",
        ),
        yaxis=dict(
            title="",
            tickfont=dict(size=11),
            autorange="reversed",
        ),
        margin=dict(t=60, b=40, l=150),
        height=700,
        barmode="overlay",
    )

    # Linhas verticais para limites de eras
    era_limits = [
        (252, "Início Triássico", "#E07A5F"),
        (201, "Início Jurássico", "#3D405B"),
        (145, "Início Cretáceo", "#81B29A"),
        (66, "Extinção K-Pg", "#ff6b6b"),
    ]

    for ma, label, color in era_limits:
        fig.add_vline(
            x=ma,
            line=dict(color=color, width=1.5, dash="dash"),
            annotation_text=label,
            annotation_position="top",
            annotation_font_color=color,
            annotation_font_size=10,
        )

    return fig
