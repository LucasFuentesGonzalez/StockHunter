import re, sys, os, time
import csv
import requests
import numpy as np
import pandas as pd
from tqdm import tqdm
import yfinance as yf
from dotenv import load_dotenv
from pycountry_convert import country_name_to_country_alpha2, country_alpha2_to_continent_code

# Diccionario global para almacenar tipos de cambio ya consultados
dTiposDeCambio = {}

# Cargar el archivo .env
load_dotenv()


def fObtenerContinente(sPais):
   try:
      sCodigoPais = country_name_to_country_alpha2(sPais)
      sCodigoContinente = country_alpha2_to_continent_code(sCodigoPais)
      lContinentes = {
         "NA": "North America",
         "SA": "South America",
         "EU": "Europe",
         "AF": "Africa",
         "AS": "Asia",
         "OC": "Oceania"
      }

      return lContinentes.get(sCodigoContinente, "Desconocido")
   except:
      return "Desconocido"



def fObtenerCambioFixer(sMonedaOrigen, sMonedaDestino="USD"):
   global dTiposDeCambio
   sClaveCache = f"{sMonedaOrigen}_{sMonedaDestino}"

   # Revisar si ya está guardado
   if sClaveCache in dTiposDeCambio:
      return dTiposDeCambio[sClaveCache]

   try:
      # Obtener la Key desde el .env
      sFIXER_API_KEY = os.getenv("FIXER_API_KEY")
      sUrl = f"http://data.fixer.io/api/latest?access_key={sFIXER_API_KEY}&base=EUR&symbols={sMonedaOrigen},{sMonedaDestino}"
      sResponse = requests.get(sUrl)
      sDatos = sResponse.json()

      if not sDatos["success"]:
         raise Exception(sDatos.get("error", {}).get("info", "Error desconocido"))

      sTasaOrigen = sDatos["rates"][sMonedaOrigen]
      sTasaDestino = sDatos["rates"][sMonedaDestino]
      sTipoCambio = sTasaDestino / sTasaOrigen

      # Guardar en caché
      dTiposDeCambio[sClaveCache] = sTipoCambio
      return sTipoCambio

   except Exception as e:
      print(f"ERROR   - Error al obtener tipo de cambio real ({sMonedaOrigen} a {sMonedaDestino}): {e}")
      raise



def fEvaluarAccion(sTicker: str) -> tuple:
   """
   Evalúa una acción y le asigna una calificación basada en indicadores financieros avanzados.
   
   Parámetros:
      sTicker (str): Símbolo de la acción en el mercado bursátil.
   
   Retorna:
      tuple: (sTicker, sName, sSector, sCalificacion, sPuntuacion) para ordenar posteriormente.
   """
   try:
      # Obtener los datos de la acción desde Yahoo Finance
      lAccion = yf.Ticker(sTicker)
      time.sleep(1)  # Pausa para evitar bloqueos
      lDatos = lAccion.info

      # Validar que se haya obtenido información útil
      if not lDatos or lDatos.get("longName") is None:
         raise ValueError(f"No se pudo obtener información del ticker")
      
      # Obtener información de la empresa
      sName = lDatos.get("longName", "Nombre no disponible")
      sSector = lDatos.get("sector", "Sector no disponible")
      sMoneda = lDatos.get("financialCurrency", "USD")  # Moneda original
      sPais = lDatos.get("country", "Desconocido")
      sContinente = fObtenerContinente(sPais)

      # Obtener tipo de cambio
      dFactorCambio = 1
      if sMoneda != "USD":
         try:
            dFactorCambio = fObtenerCambioFixer(sMoneda, "USD")
         except:
            print(f"ERROR   - Error obteniendo tipo de cambio de '{sMoneda}' a USD, se usará 1")
            dFactorCambio = 1  # fallback si no hay tasa

      # Extraer e interpretar los indicadores
      def fConvertirMoneda(valor):
         return valor * dFactorCambio if isinstance(valor, (int, float)) else np.nan
         
      # Extraer indicadores financieros clave
      lIndicadores = {
         "Precio ($)": round(fConvertirMoneda(lDatos.get("currentPrice")), 2),
         "Valor en Libros ($)": round(fConvertirMoneda(lDatos.get("bookValue")), 2),
         "P/E": round(lDatos.get("trailingPE"), 2) if lDatos.get("trailingPE") is not None else np.nan,
         "PEG": np.nan,  # Se calcula después
         "EV/EBITDA": round(lDatos.get("enterpriseToEbitda"), 2) if lDatos.get("enterpriseToEbitda") is not None else np.nan,
         "ROE (%)": round(lDatos.get("returnOnEquity") * 100, 2) if lDatos.get("returnOnEquity") is not None else np.nan,
         "Margen Neto (%)": round(lDatos.get("profitMargins") * 100, 2) if lDatos.get("profitMargins") is not None else np.nan,
         "Margen Operativo (%)": round(lDatos.get("operatingMargins") * 100, 2) if lDatos.get("operatingMargins") is not None else np.nan,
         "FCF/Acción ($)": round(fConvertirMoneda(lDatos.get("freeCashflow")), 2),
         "Dividend Yield (%)": round(lDatos.get("dividendYield"), 2) if lDatos.get("dividendYield") is not None else np.nan,
         "Beta": round(lDatos.get("beta"), 2) if lDatos.get("beta") is not None else np.nan,
         "Deuda/Capital (%)": round(lDatos.get("debtToEquity"), 2) if lDatos.get("debtToEquity") is not None else np.nan,
         "Crecimiento de Ingresos (%)": round(lDatos.get("revenueGrowth") * 100, 2) if lDatos.get("revenueGrowth") is not None else np.nan,
         "Capitalización ($)": round(fConvertirMoneda(lDatos.get("marketCap", 0)) / 1e6, 2)
      }

      # Calcular valor intrínseco según fórmula de Benjamin Graham
      EPS = lDatos.get("trailingEps")
      G = lDatos.get("earningsGrowth")

      if EPS is not None and G is not None and isinstance(EPS, (int, float)) and isinstance(G, (int, float)):
         G_normalizado = max(min(G * 100, 20), 0)  # entre 0% y 20%
         valor_intrinseco = round(EPS * (8.5 + 2 * G_normalizado), 2)
      else:
         valor_intrinseco = np.nan

      # Agregar al diccionario de indicadores
      lIndicadores["Valor Intrínseco ($)"] = valor_intrinseco

      # Reemplazar valores None o no numéricos por np.nan directamente
      for key, value in lIndicadores.items():
         if value is None or not isinstance(value, (int, float)):
            lIndicadores[key] = np.nan

      # Calcular PEG si hay datos suficientes
      if not np.isnan(lIndicadores["P/E"]) and not np.isnan(lIndicadores["Crecimiento de Ingresos (%)"]) and lIndicadores["Crecimiento de Ingresos (%)"] != 0:
         try:
            lIndicadores["PEG"] = round(lIndicadores["P/E"] / lIndicadores["Crecimiento de Ingresos (%)"], 2)
         except ZeroDivisionError:
            lIndicadores["PEG"] = np.nan
      else:
         lIndicadores["PEG"] = np.nan

      # Inicializar puntuación
      iPuntuacion = 0

      # Evaluar lIndicadores y asignar puntuaciones
      if not np.isnan(lIndicadores["PEG"]):
         if lIndicadores["PEG"] < 0:
            iPuntuacion -= 1
         elif lIndicadores["PEG"] < 1:
            iPuntuacion += 3
         elif 1 <= lIndicadores["PEG"] <= 2:
            iPuntuacion += 2
         elif lIndicadores["PEG"] > 2:
            iPuntuacion += 0

      if not np.isnan(lIndicadores["EV/EBITDA"]): 
         if lIndicadores["EV/EBITDA"] < 8:
            iPuntuacion += 3
         elif 8 <= lIndicadores["EV/EBITDA"] <= 12:
            iPuntuacion += 2
         else:
            iPuntuacion += 0

      if not np.isnan(lIndicadores["P/E"]):
         if lIndicadores["P/E"] < 15:
            iPuntuacion += 3
         elif 15 <= lIndicadores["P/E"] <= 20:
            iPuntuacion += 2
         elif 20 < lIndicadores["P/E"] <= 50:
            iPuntuacion += 0
         else:  # P/E > 50
            iPuntuacion -= 1

      if not np.isnan(lIndicadores["Dividend Yield (%)"]):
         if lIndicadores["Dividend Yield (%)"] > 3:
            iPuntuacion += 2
         elif 1 <= lIndicadores["Dividend Yield (%)"] <= 3:
            iPuntuacion += 1
         else:
            iPuntuacion += 0

      if not np.isnan(lIndicadores["Deuda/Capital (%)"]):
         if lIndicadores["Deuda/Capital (%)"] < 50:
            iPuntuacion += 2
         elif 50 <= lIndicadores["Deuda/Capital (%)"] <= 100:
            iPuntuacion += 1
         else:  # Deuda/Capital > 100
            iPuntuacion -= 1

      if not np.isnan(lIndicadores["Crecimiento de Ingresos (%)"]):
         if lIndicadores["Crecimiento de Ingresos (%)"] > 10:
            iPuntuacion += 3
         elif 5 <= lIndicadores["Crecimiento de Ingresos (%)"] <= 10:
            iPuntuacion += 2
         elif 0 <= lIndicadores["Crecimiento de Ingresos (%)"] < 5:
            iPuntuacion += 1
         else:  # Crecimiento negativo
            iPuntuacion += 0

      if not np.isnan(lIndicadores["FCF/Acción ($)"]):
         if lIndicadores["FCF/Acción ($)"] > 0:
            iPuntuacion += 2

      if not np.isnan(lIndicadores["ROE (%)"]):
         if lIndicadores["ROE (%)"] > 15:
            iPuntuacion += 3
         elif 10 <= lIndicadores["ROE (%)"] <= 15:
            iPuntuacion += 2
         elif 5 <= lIndicadores["ROE (%)"] < 10:
            iPuntuacion += 1
         else:
            iPuntuacion += 0

      if not np.isnan(lIndicadores["Beta"]):
         if lIndicadores["Beta"] < 1:
            iPuntuacion += 2
         elif 1 <= lIndicadores["Beta"] <= 1.5:
            iPuntuacion += 1
         else:
            iPuntuacion += 0
      
      # Asignar calificación basada en la puntuación
      if iPuntuacion >= 18:
         sCalificacion = "Excelente"
      elif iPuntuacion >= 14:
         sCalificacion = "Muy Buena"
      elif iPuntuacion >= 10:
         sCalificacion = "Buena"
      elif iPuntuacion >= 6:
         sCalificacion = "Regular"
      else:
         sCalificacion = "Débil"
      
      # Orden consistente según columnas de Excel
      lColumnasOrdenadas = [
         "Precio ($)", "Valor en Libros ($)", "Valor Intrínseco ($)", "P/E", "PEG", "EV/EBITDA", "ROE (%)", 
         "Margen Neto (%)", "Margen Operativo (%)", "FCF/Acción ($)", "Dividend Yield (%)", "Beta", 
         "Deuda/Capital (%)", "Crecimiento de Ingresos (%)", "Capitalización ($)"
      ]

      lValoresOrdenados = [lIndicadores.get(clave, np.nan) for clave in lColumnasOrdenadas]

      return (sTicker, sName, sSector, sContinente, sPais, sCalificacion, iPuntuacion, *lValoresOrdenados)

   except Exception as e:
      print(f"ERROR   - Error al evaluar {sTicker}: {e}")
      return None


def fGuardarResultadoEnExcel(dfResultado):
   """
   Guarda los resultados de la evaluación de la acción en un archivo Excel.
   """
   columnas_fijas = ["Ticker", "Nombre", "Sector", "Continente", "País", "Calificación", "Puntuación"]
   columnas_indicadores = [
   "Precio ($)", "Valor en Libros ($)", "Valor Intrínseco ($)", "P/E", "PEG", "EV/EBITDA", "ROE (%)", 
   "Margen Neto (%)", "Margen Operativo (%)", "FCF/Acción ($)", "Dividend Yield (%)", "Beta", 
   "Deuda/Capital (%)", "Crecimiento de Ingresos (%)", "Capitalización ($)"
   ]

   try:
      # Definir las columnas totales
      columnas_totales = columnas_fijas + columnas_indicadores

      # Obtener la Key desde el .env
      sDATA_OUTPUT_PATH = os.getenv("DATA_OUTPUT_PATH")
      
      if not sDATA_OUTPUT_PATH:
         raise ValueError("La variable de entorno 'DATA_OUTPUT_PATH' no está definida")

      # Verificar si el archivo ya existe
      file_exists = os.path.isfile(sDATA_OUTPUT_PATH)
      # Crear un DataFrame con los resultados
      df = pd.DataFrame([dfResultado], columns=columnas_totales)

      # Si el archivo no existe, crear el archivo Excel y escribir las cabeceras
      if not file_exists:
         df.to_excel(sDATA_OUTPUT_PATH, index=False, engine='openpyxl')
      else:
         # Si el archivo ya existe, agregar los resultados en una nueva hoja
         with pd.ExcelWriter(sDATA_OUTPUT_PATH, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
            df.to_excel(writer, index=False, header=False, startrow=writer.sheets['Sheet1'].max_row, sheet_name='Sheet1')

      print(f"INFO    - Resultado guardado en: {sDATA_OUTPUT_PATH}")

   except Exception as e:
      print(f"ERROR   - No se pudo crear el Excel: {e}")




################### BUSCAR EMPRESA ###################

# Evaluar la acción
dfResultado = fEvaluarAccion("REP.MC")

######################################################

# Si el resultado es válido, guardar en CSV
if dfResultado:
   fGuardarResultadoEnExcel(dfResultado)
else:
   print("ERROR   - No se pudo evaluar la acción.")
