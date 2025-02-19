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
firstYear = 1985
lastYear = 2023
totalYears = lastYear - firstYear + 1

mapbiomasCollection = 'collection9'  # Versão da collection do MapBiomas
mappingVersion = 'v7'                # Versão do mapeamento (sua escolha)
assetFolder = 'users/ybyrabr/public' # Pasta de destino dos assets no GEE

# Delimitação do Brasil (Asset que você tem no GEE)
brazil = ee.FeatureCollection("projects/ee-ipamchristhian/assets/BR_UF_2023").filter(ee.Filter.eq('SIGLA_UF','PA'))

# Definição das assets do GEE
assets = {
    "Idade (sforest_age)": "users/ybyrabr/public/secondary_vegetation_age_collection9_v7",
    "Extensão (sforest_ext)": "users/ybyrabr/public/secondary_vegetation_extent_collection9_v7",
    "Incremento (sforest_all)": "users/ybyrabr/public/secondary_vegetation_increment_collection9_v7",
    "Perda (sforest_loss)": "users/ybyrabr/public/secondary_vegetation_loss_collection9_v7"
}

# Parâmetros de visualização
product_vis_params = {
    "Incremento (sforest_all)": {"min": 0, "max": 1, "palette": ['ffffff', 'ff0000']},
    "Extensão (sforest_ext)": {"min": 0, "max": 1, "palette": ['ffffff', 'ff0000']},
    "Perda (sforest_loss)": {"min": 0, "max": 1, "palette": ['ffffff', 'ff0000']},
    "Idade (sforest_age)": {"min": 0, "max": 37, "palette": ['ffffcc','ffeda0','fed976','feb24c','fd8d3c','fc4e2a','e31a1c','bd0026','800026']}
}

# Sidebar para seleção do produto e ano
st.sidebar.image('asset/ipam-brand-color.png', width=150)

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

selected_product = st.sidebar.selectbox("Escolha o produto para visualizar:", list(assets.keys()), key='product_select')
selected_year = st.sidebar.selectbox("Escolha o ano de visualização:", list(range(1986, lastYear + 1)), index=2023 - 1986, key='year_select')

band_name_selected = f"classification_{selected_year}"
image_selected = ee.Image(assets[selected_product]).clip(brazil)

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




# Renderiza o mapa interativo
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
     
