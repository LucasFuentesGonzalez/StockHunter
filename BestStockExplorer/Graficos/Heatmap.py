import re, sys, os, time
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv
import matplotlib.pyplot as plt


# Cargar el archivo .env
load_dotenv()
# Obtener la ruta desde el archivo .env
sDATA_STOCKS_PATH = os.getenv('DATA_STOCKS_PATH')

# Cargar el archivo Excel
df = pd.read_excel(sDATA_STOCKS_PATH, engine='openpyxl')

# Lista de columnas a tener en cuenta
columnas_numericas = [
    'Puntuación', 'Precio ($)', 'Valor en Libros ($)', 'P/E', 'EV/EBITDA',
    'Dividend Yield (%)', 'Deuda/Capital (%)', 'Crecimiento de Ingresos (%)',
    'FCF/Acción ($)', 'ROE (%)', 'Margen Neto (%)', 'Margen Operativo (%)',
    'Beta', 'Capitalización ($)', 'PEG'
]

# Convertir a numérico (forzando errores a NaN)
df[columnas_numericas] = df[columnas_numericas].apply(pd.to_numeric, errors='coerce')

# Filtrar solo filas que tengan todos los valores presentes en estas columnas
df_filtrado = df.dropna(subset=columnas_numericas)

# Mostrar cuántos registros quedaron
print(f"Número de registros completos: {len(df_filtrado)}")

# Calcular matriz de correlación
correlacion = df_filtrado[columnas_numericas].corr()

# Generar el heatmap
plt.figure(figsize=(14, 10))
sns.heatmap(correlacion, annot=True, fmt=".2f", cmap="coolwarm", linewidths=0.5)
plt.title('Matriz de Correlación - Solo columnas seleccionadas y registros completos')
plt.tight_layout()
plt.show()