import streamlit as st
import ee
import geemap.foliumap as geemap
import folium
from streamlit_folium import st_folium
from streamlit_folium import folium_static
import folium


# ---------------------------------------------------------------------------- #
# 1. Inicialização do Earth Engine
# ---------------------------------------------------------------------------- #
# Certifique-se de ter executado previamente: earthengine authenticate
# try:
#     ee.Initialize()
# except Exception as e:
#     ee.Authenticate()
#     ee.Initialize()

# Defina a configuração de página para "wide"
st.set_page_config(layout="wide")

##Login GEE 
m=geemap.Map()


# ---------------------------------------------------------------------------- #
# 2. Definição das variáveis principais
# ---------------------------------------------------------------------------- #
firstYear = 1985
lastYear = 2023
totalYears = lastYear - firstYear + 1

mapbiomasCollection = 'collection9'  # Versão da collection do MapBiomas
mappingVersion = 'v7'                # Versão do mapeamento (sua escolha)
assetFolder = 'users/ybyrabr/public' # Pasta de destino dos assets no GEE

# Delimitação do Brasil (Asset que você tem no GEE)
brazil = ee.FeatureCollection("users/celsohlsj/brazil")

# Dados do MapBiomas (Collection 9)
# Link oficial do MapBiomas no GEE: 
# "projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1"
mapbiomas = ee.Image('projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1')

# ---------------------------------------------------------------------------- #
# 3. Reclassificação das bandas de floresta e máscara antrópica
# ---------------------------------------------------------------------------- #
# 3.1 Reclassificando para Floresta (bandas para cada ano) 
empty_forest = ee.Image().byte()
for i in range(totalYears):
    y = firstYear + i
    band_name = 'classification_{}'.format(y)
    # Reclassifica para classe "1" se for (3,4,5,6,49,11,12,32,50), senão 0
    forest = mapbiomas.select(band_name).remap(
        [3, 4, 5, 6, 49, 11, 12, 32, 50], 
        [1, 1, 1, 1, 1, 1, 1, 1, 1],
        0
    )
    empty_forest = empty_forest.addBands(forest.rename(band_name))

# Seleciona apenas as bandas criadas
mapbiomas_forest = empty_forest.select(empty_forest.bandNames())

# 3.2 Máscara antrópica (bandas para cada ano)
empty_anthropic = ee.Image().byte()
for i in range(totalYears):
    y = firstYear + i
    band_name = 'classification_{}'.format(y)
    # Reclassifica para classe "1" se for (15,19,39,20,40,62,41,46,47,35,48,9,21), senão 0
    anthropic = mapbiomas.select(band_name).remap(
        [15, 19, 39, 20, 40, 62, 41, 46, 47, 35, 48, 9, 21],
        [1, 1, 1,  1,  1,  1,  1,  1,  1,  1,  1, 1,  1],
        0
    ).rename(band_name)
    empty_anthropic = empty_anthropic.addBands(anthropic)

anthropic_mask = empty_anthropic.select(empty_anthropic.bandNames())

# ---------------------------------------------------------------------------- #
# 4. Mapeamento do Incremento Anual de Floresta Secundária
# ---------------------------------------------------------------------------- #
# sforest_all contém para cada ano (a partir de 1986) se houve surgimento de floresta secundária
empty_sforest_all = ee.Image().byte()
for i in range(totalYears - 1):
    y1 = firstYear + i
    y2 = y1 + 1

    band_name1 = 'classification_{}'.format(y1)
    band_name2 = 'classification_{}'.format(y2)

    a_mask = anthropic_mask.select(band_name1)
    # forest1 = mapbiomas_forest no ano anterior, mas remapeada 0->0,1->2
    forest1 = mapbiomas_forest.select(band_name1).remap([0, 1], [0, 2])
    forest2 = mapbiomas_forest.select(band_name2)

    # Se era 2 (floresta no ano anterior) + 1 (floresta no ano atual) = 3 -> esse local "apareceu" este ano
    # Ajuste: sforest=1 quando 2+1=3. Do contrário 0
    sforest = forest1.add(forest2).remap([0, 1, 2, 3], [0, 1, 0, 0])
    # Multiplica pela máscara antrópica do ano anterior (só conta onde era antrópico)
    sforest = sforest.multiply(a_mask).rename(band_name2)

    empty_sforest_all = empty_sforest_all.addBands(sforest)

sforest_all = empty_sforest_all.select(empty_sforest_all.bandNames())

# ---------------------------------------------------------------------------- #
# 5. Mapeamento da Extensão Anual de Floresta Secundária
# ---------------------------------------------------------------------------- #
empty_sforest_ext = ee.Image().byte()

# A primeira banda para 1986 (primeiro ano que podemos ter incremento)
# Pegamos o 'classification_1986' da sforest_all diretamente
ext1986 = sforest_all.select('classification_1986')
empty_sforest_ext = empty_sforest_ext.addBands(ext1986.rename('classification_1986'))

# Para anos subsequentes
for i in range(1, totalYears - 1):
    y = firstYear + 1 + i
    band_name = 'classification_{}'.format(y)
    band_name_prev = 'classification_{}'.format(y - 1)

    sforest = sforest_all.select(band_name)
    acm_forest = empty_sforest_ext.select(band_name_prev).add(sforest)
    
    # se acm_forest != 0 então há floresta secundária acumulada
    remap = acm_forest.neq(0)
    # multiplica pela floresta do mapbiomas (garantindo que ainda é floresta)
    remap = remap.multiply(mapbiomas_forest.select(band_name))
    
    empty_sforest_ext = empty_sforest_ext.addBands(remap.rename(band_name))

sforest_ext = empty_sforest_ext.select(empty_sforest_ext.bandNames())

# ---------------------------------------------------------------------------- #
# 6. Mapeamento da Perda de Floresta Secundária
# ---------------------------------------------------------------------------- #
empty_sforest_loss = ee.Image().byte()
empty_temp = ee.Image().byte()

# Inicia com a banda 1986
ext1986 = sforest_all.select('classification_1986').rename('classification_1986')
empty_temp = empty_temp.addBands(ext1986)

for i in range(1, totalYears - 1):
    y = firstYear + 1 + i
    band_name = 'classification_{}'.format(y)
    band_name_prev = 'classification_{}'.format(y - 1)

    sforest = sforest_all.select(band_name)
    acm_forest = empty_temp.select(band_name_prev).add(sforest)
    
    remap = acm_forest.neq(0)
    # se mapbiomas_forest == 1 => 1, se 0 => 500
    mask = mapbiomas_forest.select(band_name).remap([0, 1], [500, 1])
    loss = remap.add(mask).remap([1, 2, 500, 501], [0, 0, 0, 1])

    empty_sforest_loss = empty_sforest_loss.addBands(loss.rename(band_name))
    # Atualiza para a próxima iteração: se continua floresta, soma
    empty_temp = empty_temp.addBands(
        remap.multiply(mapbiomas_forest.select(band_name)).rename(band_name)
    )

sforest_loss = empty_sforest_loss.select(empty_sforest_loss.bandNames())

# ---------------------------------------------------------------------------- #
# 7. Idade da Floresta Secundária
# ---------------------------------------------------------------------------- #
# Similar ao que fez no script GEE
empty_age = ee.Image().byte()
age1986 = sforest_ext.select('classification_1986').rename('classification_1986')
empty_age = empty_age.addBands(age1986)
empty_age = empty_age.slice(1)  # descarta banda "0"

temp = empty_age
for i in range(1, totalYears - 1):
    y = firstYear + 1 + i
    band_name = 'classification_{}'.format(y)

    sforest = sforest_ext.select(band_name)
    ageforest = empty_age.add(sforest)
    fYear = mapbiomas_forest.select(band_name)
    # ageforest * fYear garante que só conta onde há floresta
    ageforest = ageforest.multiply(fYear)

    temp = temp.addBands(ageforest.rename(band_name))
    empty_age = ageforest

sforest_age = temp


# ---------------------------------------------------------------------------- #
# 8. Paletas e Parâmetros de Visualização por Produto
# ---------------------------------------------------------------------------- #
product_vis_params = {
    "Incremento (sforest_all)": {
        "min": 0,
        "max": 1,
        "palette": ['ffffff', 'ff0000']  # branco a vermelho
    },
    "Extensão (sforest_ext)": {
        "min": 0,
        "max": 1,
        "palette": ['ffffff', 'ff0000']
    },
    "Perda (sforest_loss)": {
        "min": 0,
        "max": 1,
        "palette": ['ffffff', 'ff0000']
    },
    "Idade (sforest_age)": {
        "min": 0,
        "max": 37,  # ou (lastYear - 1986)
        "palette": [
    'ffffcc','ffeda0','fed976','feb24c','fd8d3c','fc4e2a','e31a1c','bd0026','800026'
]
    }
}

# ---------------------------------------------------------------------------- #
# 9. Visualização Interativa no Streamlit
# ---------------------------------------------------------------------------- #
st.title("Benchmark maps of 33 years of secondary forest age for Brazil")

with st.expander("About This App", expanded=False):
    st.markdown("""
    **Background:**
    
    The restoration and reforestation of 12 million hectares of forests by 2030 are amongst
    the leading mitigation strategies for reducing carbon emissions within the Brazilian Nationally Determined 
    Contribution targets assumed under the Paris Agreement. Understanding the dynamics of forest cover, 
    which steeply decreased between 1985 and 2018 throughout Brazil, is essential for estimating the global 
    carbon balance and quantifying the provision of ecosystem services. Knowing the long-term increment, extent, 
    and age of secondary forests is crucial; however, these variables are poorly quantified. Here we developed a 30-m spatial resolution 
    dataset of the annual increment, extent, and age of secondary forests for Brazil over the 1986–2018 period. 
    Land-use and land-cover maps from MapBiomas Project were used as input data for our algorithm, implemented in the Google Earth Engine
    platform. This dataset provides critical spatially explicit information for supporting carbon emissions reduction, biodiversity,
    and restoration policies, enabling environmental science applications,
    territorial planning, and subsidizing environmental law enforcement.
    """)
    st.image('asset/image.jpg', caption="Exemplo de imagem", width=600)

# Seleção do produto e ano para visualização
products_dict = {
    "Incremento (sforest_all)": sforest_all,
    "Extensão (sforest_ext)": sforest_ext,
    "Perda (sforest_loss)": sforest_loss,
    "Idade (sforest_age)": sforest_age
}

st.sidebar.image('asset/ipam-brand-color.png',width=150)

st.sidebar.markdown(
    """
    <div style="font-size: 12px;">
    <strong>Associated Publication (method description):</strong><br><br>
    Silva-Junior, C.H.L., Heinrich, V.H.A., Freire, A.T.G., Broggio, I.S., Rosan, T.M., Doblas, J., Anderson, L.O., Rousseau, G.X., Shimabukuro, Y.E., Silva, C.A., House, J.I., Aragão, L.E.O.C. <em>Benchmark maps of 33 years of secondary forest age for Brazil</em>. <em>Scientific Data (2020)</em>.<br>
    <a href="https://doi.org/10.1038/s41597-020-00600-4" target="_blank">https://doi.org/10.1038/s41597-020-00600-4</a>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.divider()

selected_product = st.sidebar.selectbox(
    "Escolha o produto para visualizar:",
    list(products_dict.keys())
)

selected_year = st.sidebar.selectbox(
    "Escolha o ano de visualização:",
    list(range(1986, lastYear + 1)),
    index=2023 - 1986  # define o ano 2000 como opção padrão
)

band_name_selected = f"classification_{selected_year}"
image_selected = products_dict[selected_product]

if band_name_selected not in image_selected.bandNames().getInfo():
    st.warning("Ano/banda selecionado não está disponível para este produto.")
else:
    single_band = image_selected.select(band_name_selected)
    
    # Torna os pixels de valor 0 transparentes.
    single_band_masked = single_band.updateMask(single_band.neq(0))
    
    # Recupera a paleta e min/max específicos do produto
    vis_params = product_vis_params[selected_product]
    
    

    Map = geemap.Map(center=[-15, -55], zoom=4,basemap='CartoDB.DarkMatter')
    Map.add_basemap('SATELLITE')          # Google Satellite
    # Map.add_basemap('CartoDB.DarkMatter') # Mapa "preto"
    Map.addLayer(single_band_masked, vis_params, f"{selected_product} - {selected_year}")
    Map.addLayerControl()
        # # Renderiza o mapa no Streamlit
    # Map.to_streamlit(height=600)
    
   # Renderiza o mapa interativo e captura dados do clique
click_data = st_folium(Map, key="map_click", height=650, width=1200, use_container_width=True)

# Verifica se o usuário clicou no mapa
if click_data and click_data.get("last_clicked") is not None:
    lon, lat = click_data["last_clicked"]["lng"], click_data["last_clicked"]["lat"]

    # Criação de um quadrado de 256x256 pixels (30m/pixel)
    tile_size = 256 * 30  # 256 pixels * 30m de resolução
    region = ee.Geometry.Rectangle([
        [lon - tile_size / 2 / 111320, lat - tile_size / 2 / 111320],
        [lon + tile_size / 2 / 111320, lat + tile_size / 2 / 111320]
    ])

    # Adiciona um marcador para mostrar onde foi clicado
    folium.Marker(
        location=[lat, lon],
        popup=f"Selecionado: {lat:.5f}, {lon:.5f}",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(Map)

    # Atualiza o mapa no Streamlit
    # st_folium(Map, key="map_click_updated", height=650, width=1200)

    # Geração da URL de download
    try:
        download_url = image_selected.getDownloadURL({
            'scale': 30,
            'crs': 'EPSG:4326',
            'region': region.getInfo()['coordinates'],
            'format': 'GEO_TIFF'
        })

        st.sidebar.markdown(
        f"""
        <style>
            /* Ajuste do background e do texto da seção de Download */
            .download-section {{
                background-color: #f5f5f5 !important; /* Fundo acinzentado */
                color: #111111 !important; /* Preto levemente menos agressivo */
                font-weight: bold;
                padding: 15px;
                border-radius: 8px;
                margin-top: 15px;
                border: 1px solid #ccc; /* Adiciona uma borda sutil */
            }}

            /* Forçar o título a ser preto */
            .download-section h4 {{
                color: #000000 !important; /* Preto absoluto */
            }}

            /* Estilo do link de Download */
            .download-section a {{
                color: #00796b !important; /* Verde IPAM */
                font-weight: bold;
                text-decoration: none;
            }}

            /* Hover no link de Download */
            .download-section a:hover {{
                text-decoration: underline;
            }}
        </style>
        
        <div class="download-section">
            <h4>📥 Baixar Tile</h4>
            <p><strong>Produto:</strong> {selected_product} - {selected_year}</p>
            <p><strong>Localização:</strong> {lat:.5f}, {lon:.5f}</p>
            <p>🔗 <a href="{download_url}" target="_blank">Download</a></p>
        </div>
        """,
        unsafe_allow_html=True
    )


        st.sidebar.success("📌 Clique no link acima para baixar o tile selecionado.")
    
    except Exception as e:
        st.sidebar.error(f"Erro ao gerar URL de download: {e}")
else:
    st.sidebar.info("🖱️ Clique no mapa para selecionar um ponto e baixar um tile.")
    
  # ----------------------------------------------------------------------
    # Sidebar: Explicação sobre o download dos dados via Zenodo
    # ----------------------------------------------------------------------
st.sidebar.markdown(
    """
    <style>
        /* Ajuste do background e do texto da seção de Download */
        .download-section {
            background-color: #f5f5f5 !important; /* Fundo acinzentado */
            color: #000000 !important;  /* Texto preto */
            font-weight: bold;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
        }
    </style>
    <div class="download-section">
        📥 <strong>Download dos Dados Oficiais</strong> <br>
        Os dados finais da versão <strong>v2</strong> podem ser acessados diretamente no repositório Zenodo: <br><br>
        🔗 <a href="https://doi.org/10.5281/zenodo.3928660" target="_blank">
        <strong>Zenodo Repository - DOI: 10.5281/zenodo.3928660</strong></a>
    </div>
    """,
    unsafe_allow_html=True
)
     
