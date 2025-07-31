# Lib\VisualizadorDeAcciones.py
import re, sys, os, time
import io
import math
import numpy as np
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder
import plotly.express as px
from dotenv import load_dotenv


# Detectar si el script está empaquetado con PyInstaller
if getattr(sys, 'frozen', False):
   BASE_DIR = sys._MEIPASS  # Ruta temporal generada por PyInstaller
else:
   # Ruta base = carpeta del proyecto
   BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Ruta para almacenar el listado con todos los datos de las empresas obtenidos de yfinance
sDATA_STOCKS_PATH = os.path.join(BASE_DIR, "Data", "ListadoDeMejoresAcciones.xlsx")


# ================================
# CONFIGURACIÓN DE LA PÁGINA
# ================================
st.set_page_config(page_title="📊 Visualizador de Acciones", layout="wide")

# ================================
# CARGA DE DATOS
# ================================
if not os.path.exists(sDATA_STOCKS_PATH):
   st.error(f"⚠️ El archivo `{sDATA_STOCKS_PATH}` no se encuentra.")
   st.stop()

dfOriginal = pd.read_excel(sDATA_STOCKS_PATH)


# ================================
# FILTRADO DE OUTLIERS Y FILTRADO EXPLÍCITO
# ================================
dfFiltrado = dfOriginal.copy()

# Definir umbrales de protección
UMBRAL_PUNTUACION = 16
UMBRAL_CAPITALIZACION = 1_000_000_000_000

# Empresas protegidas (no se les aplican filtros de outliers)
dfProtegidas = dfOriginal[
   (dfOriginal["Puntuación"] > UMBRAL_PUNTUACION) |
   (dfOriginal["Capitalización ($)"] > UMBRAL_CAPITALIZACION)
]

# Empresas que sí serán filtradas
dfFiltrables = dfOriginal.drop(dfProtegidas.index)

# Reglas personalizadas
lReglasOutliers = {
   "P/E": {"min": True, "max": True},
   "Dividend Yield (%)": {"min": False, "max": True},
   "Deuda/Capital (%)": {"min": False, "max": True},
   "ROE (%)": {"min": True, "max": True},
   "Margen Neto (%)": {"min": True, "max": True},
   "Margen Operativo (%)": {"min": True, "max": True},
   "Crecimiento de Ingresos (%)": {"min": True, "max": True},
   "Beta": {"min": False, "max": True},
   "PEG": {"min": True, "max": True},
   "EV/EBITDA": {"min": False, "max": True},
}

# Aplicamos filtrado de outliers solo a las empresas no protegidas
for col, reglas in lReglasOutliers.items():
   if col in dfFiltrables.columns:
      q10 = dfFiltrables[col].quantile(0.10)
      q90 = dfFiltrables[col].quantile(0.90)
      iqr = q90 - q10
      factor = 1.5
      lower_bound = q10 - factor * iqr
      upper_bound = q90 + factor * iqr

      if reglas["min"] and reglas["max"]:
         dfFiltrables.loc[(dfFiltrables[col] < lower_bound) | (dfFiltrables[col] > upper_bound), col] = None
      elif reglas["min"]:
         dfFiltrables.loc[(dfFiltrables[col] < lower_bound), col] = None
      elif reglas["max"]:
         dfFiltrables.loc[(dfFiltrables[col] > upper_bound), col] = None

# Eliminar filas con NaN en los campos filtrados
dfFiltrables = dfFiltrables.dropna(subset=list(lReglasOutliers.keys()))

# Reconstruir el DataFrame con protegidas + filtradas limpias
dfSinOutliers = pd.concat([dfProtegidas, dfFiltrables], ignore_index=True)

# Aplicar filtros explícitos a TODOS los registros (sin excepciones)
dfFiltradoExplicito = dfSinOutliers[
   (dfSinOutliers["ROE (%)"] >= 0) &
   (dfSinOutliers["ROE (%)"] <= 150) &
   (dfSinOutliers["PEG"] >= -40) &
   (dfSinOutliers["P/E"] <= 100)
]


# ================================
# FILTROS (SIDEBAR)
# ================================
st.sidebar.header("🔍 Filtros")
# Lista de columnas categóricas que se filtrarán con selectbox
lColumnasTexto = ["Sector", "Continente", "País"]
lFiltrosTexto = {}
# Crea un selectbox en la barra lateral con la opción "Todos" + las opciones únicas ordenadas de esa columna
for col in lColumnasTexto:
   opciones = ["Todos"] + sorted(dfFiltradoExplicito[col].dropna().unique().tolist())
   lFiltrosTexto[col] = st.sidebar.selectbox(f"📌 Filtrar por {col}:", opciones)

# Lista de columnas numéricas que se filtrarán con sliders (rangos)
lColumnasNumericas = [
"Puntuación", "Precio ($)", "Valor en Libros ($)", "Valor Intrínseco ($)", "P/E", "PEG", "EV/EBITDA", "ROE (%)", 
"Margen Neto (%)", "Margen Operativo (%)", "FCF/Acción ($)", "Dividend Yield (%)", "Beta", 
"Deuda/Capital (%)", "Crecimiento de Ingresos (%)", "Capitalización ($)"
]
lFiltrosNumericos = {}

# Para cada columna numérica, crea un slider en la barra lateral
for col in lColumnasNumericas:
   if col in dfFiltradoExplicito.columns:
      # Primero reemplaza infinitos por NaN y luego elimina los NaN
      serie = dfFiltradoExplicito[col].replace([np.inf, -np.inf], np.nan).dropna()
      # Define valores mínimo y máximo de la serie
      min_val = int(serie.min()) if not serie.empty else 0
      max_val = int(serie.max()) if not serie.empty else 1
      # Crea un slider para seleccionar el rango deseado
      lFiltrosNumericos[col] = st.sidebar.slider(f"📊 Rango {col}:", min_value=min_val, max_value=max_val, value=(min_val, max_val), step=1)

dfFiltradoSideBar = dfFiltradoExplicito.copy()

# Aplica los filtros categóricos (texto)
for col, filtro in lFiltrosTexto.items():
   if filtro != "Todos":
      dfFiltradoSideBar = dfFiltradoSideBar[dfFiltradoSideBar[col] == filtro]

# Aplica los filtros numéricos (por rangos)
for col, (min_val, max_val) in lFiltrosNumericos.items():
   dfFiltradoSideBar = dfFiltradoSideBar[(dfFiltradoSideBar[col] >= min_val) & (dfFiltradoSideBar[col] <= max_val)]


# ================================
# EXPLICACIÓN DE CADA CAMPO
# ================================
st.title("📈 Análisis de Acciones")
st.markdown("""
### Explicación de los Campos

- **Precio ($)**: Precio actual de la acción de la empresa en euros.
- **Valor en Libros ($)**: Valor contable de la empresa, que representa lo que valdría la empresa si se vendieran todos sus activos.
- **Valor Intrínseco ($)**: Estimación del valor real de la acción basada en las ganancias actuales y un crecimiento esperado moderado. Si es mayor que el precio actual, la acción podría estar infravalorada; si es menor, podría estar sobrevalorada.
- **P/E (Price/Earnings)**: Relación entre el precio de la acción y las ganancias por acción, indica la valoración de la empresa.
- **PEG (Price/Earnings to Growth)**: Relación entre el precio de la acción, las ganancias por acción y el crecimiento esperado de las ganancias.
- **EV/EBITDA (Enterprise Value / EBITDA)**: Mide el valor total de la empresa en relación a sus ganancias antes de intereses, impuestos, depreciación y amortización.
- **ROE (Return on Equity) (%)**: Rentabilidad sobre el capital, muestra la eficiencia con la que la empresa genera ganancias a partir del capital invertido.
- **Margen Neto (%)**: Porcentaje de los ingresos de la empresa que queda como ganancia neta después de todos los gastos.
- **Margen Operativo (%)**: Mide la eficiencia operativa de la empresa, considerando los ingresos menos los gastos operativos.
- **FCF/Acción ($)**: Flujo de caja libre por acción, mide la cantidad de dinero que la empresa tiene disponible para distribuir a los accionistas.      
- **Dividend Yield (%)**: Rendimiento por dividendo de la acción, indica el porcentaje de retorno que paga la empresa en forma de dividendos.
- **Beta**: Medida de la volatilidad de la acción en comparación con el mercado en general.
- **Deuda/Capital (%)**: Porcentaje de deuda que tiene la empresa en relación a su capital total.
- **Crecimiento de Ingresos (%)**: Tasa de crecimiento anual de los ingresos de la empresa.
- **Capitalización ($)**: Valor total de mercado de la empresa, calculado como el precio de la acción por el número total de acciones.
""")
st.write("")
st.write("")
st.write("")


# ================================
# ESTADÍSTICAS DE FILTRADO
# ================================
st.subheader("📊 Estadísticas de Filtrado")
col1, col2, col3, col4 = st.columns(4)
with col1:
   st.metric("Total original", len(dfOriginal))
with col2:
   st.metric("Tras outliers", len(dfSinOutliers))
with col3:
   st.metric("Tras filtros explícitos", len(dfFiltradoExplicito))
with col4:
   st.metric("Tras filtros del sidebar", len(dfFiltradoSideBar))
st.write("")
st.write("")
st.write("")


# ================================
# TABLA FILTRADA
# ================================
st.subheader("📜 Datos Filtrados")
st.write("""
En esta sección, se muestran los datos que han sido filtrados según los criterios seleccionados, como el sector, 
el continente, los rangos de los indicadores financieros y la eliminación de outliers. Esta tabla incluye solo 
las acciones que cumplen con estos criterios.""")

st.dataframe(dfFiltradoSideBar, height=500, use_container_width=True)
st.write("")
st.write("")
st.write("")


# ================================
# COMPARACIÓN DE ACCIONES
# ================================
st.subheader("🆚 Comparar Acciones")
st.write("""
   Aquí puedes seleccionar varias acciones para compararlas en función de su puntuación. Al seleccionar las acciones 
   que te interesen, podrás ver cómo se comparan entre sí en términos de puntuación y sector. Esto te permitirá 
   hacer una selección más informada entre las mejores opciones.""")
seleccion = st.multiselect("🆚 Comparar Acciones", dfFiltradoSideBar["Nombre"].unique())
if seleccion:
   df_Comparacion = dfFiltradoSideBar[dfFiltradoSideBar["Nombre"].isin(seleccion)]
   st.dataframe(df_Comparacion)
   fig_comp = px.bar( df_Comparacion, x="Nombre", y="Puntuación", color="Sector", title="Comparación de Puntuación")
   st.plotly_chart(fig_comp, use_container_width=True)
st.write("")
st.write("")
st.write("")


# ================================
# GRÁFICAS AVANZADAS
# ================================
st.subheader("📊 Análisis Visual de Rentabilidad y Valor")

fig1 = px.scatter(dfFiltradoSideBar, x="P/E", y="ROE (%)", size="Capitalización ($)", color="Sector",
               title="Relación P/E vs ROE", hover_data=["Nombre"])
st.plotly_chart(fig1, use_container_width=True)

fig2 = px.scatter(dfFiltradoSideBar, x="PEG", y="Crecimiento de Ingresos (%)", color="Sector", size="Capitalización ($)",
               title="PEG vs Crecimiento de Ingresos", hover_data=["Nombre"])
st.plotly_chart(fig2, use_container_width=True)

fig3 = px.box(dfFiltradoSideBar, x="Sector", y="P/E", color="Sector", title="Distribución de P/E por Sector")
st.plotly_chart(fig3, use_container_width=True)

fig4 = px.histogram(dfFiltradoSideBar, x="Dividend Yield (%)", nbins=30, title="Distribución de Dividend Yield")
st.plotly_chart(fig4, use_container_width=True)

fig5 = px.scatter(dfFiltradoSideBar, x="ROE (%)", y="Margen Operativo (%)", color="Sector", size="Capitalización ($)",
               title="ROE vs Margen Operativo", hover_data=["Nombre"])
st.plotly_chart(fig5, use_container_width=True)
st.write("")
st.write("")
st.write("")

# ================================
# NUEVO GRÁFICO: Países Sobrevalorados (P/E promedio)
# ================================
st.subheader("🌍 Análisis de Valoración por País")

df_PER_Paises = dfOriginal[dfOriginal["P/E"] <= 100]


# Agrupar por país y calcular estadísticas
df_Paises = df_PER_Paises.groupby("País").agg(
   pe_promedio=("P/E", "mean"),
   num_empresas=("Nombre", "count")
).reset_index()

# Filtrar países con al menos 3 empresas para evitar distorsiones
df_Paises = df_Paises[df_Paises["num_empresas"] >= 3]

# Redondear valores para mejor visualización
df_Paises["pe_promedio"] = df_Paises["pe_promedio"].round(2)

# Ordenar por P/E promedio
df_Paises = df_Paises.sort_values(by="pe_promedio", ascending=False)

# Crear gráfico de barras
fig_pe_paises = px.bar(
   df_Paises,
   x="País",
   y="pe_promedio",
   color="pe_promedio",
   text="pe_promedio",  # Mostrar el P/E promedio sobre la barra
   title="📈 Países con Mayor P/E Promedio (potencial sobrevaloración)",
   labels={"pe_promedio": "P/E Promedio", "num_empresas": "N° de Empresas"},
   color_continuous_scale="Reds",
   hover_data={"num_empresas": True, "pe_promedio": True}
)

fig_pe_paises.update_layout(
   xaxis_tickangle=-45,
   yaxis_title="P/E Promedio",
   xaxis_title="País",
   uniformtext_minsize=8,
   uniformtext_mode='hide'
)
st.plotly_chart(fig_pe_paises, use_container_width=True)


# ================================
# EXPORTAR RESULTADOS
# ================================
st.subheader("📥 Exportar Resultados")
st.write("""
   Si deseas guardar los resultados filtrados en un archivo de Excel, puedes descargar el archivo desde el siguiente 
   botón. Este archivo incluirá los datos que has filtrado y comparado, lo que te permitirá tener un registro de 
   tus selecciones y análisis para su posterior revisión o inversión.""")
output = io.BytesIO()
dfFiltradoSideBar.to_excel(output, index=False)
st.download_button("📥 Descargar Filtro", output.getvalue(), file_name="ResultadosFiltrados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
