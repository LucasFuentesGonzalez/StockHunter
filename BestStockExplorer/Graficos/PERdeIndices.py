# Graficos\PERdeIndices.py
import yfinance as yf
import datetime
import pandas as pd
import matplotlib.pyplot as plt

"""
================================================================================
Análisis de Rentabilidad de Índices Globales
--------------------------------------------------------------------------------
 
Descripción:
Este script permite calcular y visualizar la rentabilidad acumulada de los 
principales índices bursátiles del mundo desde una fecha inicial hasta hoy.

Uso previsto:
Este script es útil para hacer un seguimiento comparativo del rendimiento de 
distintas regiones o economías globales con fines de análisis financiero, 
educación, o toma de decisiones de inversión.

================================================================================
"""

# Diccionario con los principales índices/fondos del mundo y sus tickers de Yahoo Finance
funds = {
"^DJI": "Dow Jones", "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^RUT": "Small Cap 2000", "^VIX": "S&P 500 VIX", "^GSPTSE": "S&P/TSX",
"^BVSP": "Bovespa (Brasil)", "^MXX": "S&P/BMV IPC (México)", "URTH": "MSCI World", "^GDAXI": "DAX (Alemania)", "^FTSE": "FTSE 100 (Reino Unido)",
"^FCHI": "CAC 40 (Francia)", "^STOXX50E": "Euro Stoxx 50", "^AEX": "AEX (Países Bajos)", "^IBEX": "IBEX 35 (España)", "FTSEMIB.MI": "FTSE MIB (Italia)",
"^SSMI": "SMI (Suiza)", "^PSI20": "PSI (Portugal)", "^ATX": "ATX (Austria)", "^OMX": "OMXS30 (Suecia)", "^OMXC25": "OMXC25 (Dinamarca)","IMOEX.ME": "MOEX Russia Index", 
"^WIG20": "WIG20 (Polonia)", "XU100.IS": "BIST 100 (Turquía)", "TA35.TA": "TA 35 (Israel)", "^N225": "Nikkei 225 (Japón)","^AXJO": "S&P/ASX 200 (Australia)", 
"^NZ50": "DJ New Zealand", "000001.SS": "Shanghai Composite", "399001.SZ": "SZSE Component", "^HSI": "Hang Seng (Hong Kong)", "^TWII": "Taiwan Weighted", 
"^SET.BK": "SET (Tailandia)", "^KS11": "KOSPI (Corea del Sur)", "^JKSE": "IDX Composite (Indonesia)", "^NSEI": "Nifty 50 (India)", "^BSESN": "BSE Sensex (India)",
}

# Rango de fechas para calcular la rentabilidad
start_date = "2020-01-01"
end_date = datetime.datetime.today().strftime('%Y-%m-%d')

# Diccionario donde se almacenarán las rentabilidades calculadas
returns = {}

# Descargar precios históricos y calcular rentabilidad total de cada índice
for ticker, name in funds.items():
   try:
      # Descargar precios con ajuste automático (ajustado por splits y dividendos)
      data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)

      # Si no hay datos, lo ignoramos
      if data.empty:
         print(f"No se pudo descargar datos para {name} ({ticker})")
         continue

      # Extraer el primer y último valor del cierre ajustado
      initial = data["Close"].iloc[0].item()
      final = data["Close"].iloc[-1].item()

      # Calcular rentabilidad total porcentual
      total_return = (final - initial) / initial * 100

      # Guardar resultado en el diccionario
      returns[name] = total_return

      # Mostrar resultado por consola
      print(f"{name}: {total_return:.2f}%")

   except Exception as e:
      # Mostrar cualquier error que ocurra al procesar un índice
      print(f"Error con {name} ({ticker}): {e}")

# Crear un DataFrame con las rentabilidades
returns_df = pd.DataFrame.from_dict(returns, orient='index', columns=['Rentabilidad (%)'])

# Ordenar de mayor a menor rentabilidad
returns_df = returns_df.sort_values(by='Rentabilidad (%)', ascending=False)

# Mostrar resultados por consola
print("\nRentabilidad desde", start_date, "hasta", end_date)
print(returns_df)

# Generar gráfico si hay datos disponibles
if not returns_df.empty:
   returns_df.plot(kind='barh', legend=False, figsize=(10, 6), color='skyblue')
   plt.title(f"Rentabilidad desde {start_date} hasta {end_date}")
   plt.xlabel("Rentabilidad (%)")
   plt.tight_layout()
   plt.grid(axis='x', linestyle='--', alpha=0.7)
   plt.show()
else:
   print("No hay datos disponibles para graficar.")
