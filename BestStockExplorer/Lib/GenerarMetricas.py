# Lib\GenerarMetricas.py
import re, sys, os, time
import csv
import random
import requests
import numpy as np
import pandas as pd
from tqdm import tqdm
import yfinance as yf
from datetime import datetime
from dotenv import load_dotenv
from pycountry_convert import country_name_to_country_alpha2, country_alpha2_to_continent_code


# Detectar si el script está empaquetado con PyInstaller
if getattr(sys, 'frozen', False):
   BASE_DIR = sys._MEIPASS  # Ruta temporal generada por PyInstaller
else:
   # Ruta base = carpeta del proyecto
   BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Ruta para almacenar las empresas, sus nombres y Ticker
sTICKER_LIST_PATH = os.path.join(BASE_DIR, "Data", "TickersDeEmpresas.csv")
# Ruta para almacenar el listado con todos los datos de las empresas obtenidos de yfinance
sDATA_STOCKS_PATH = os.path.join(BASE_DIR, "Data", "ListadoDeMejoresAcciones.xlsx")
# Ruta para almacenar los tipos de cambio obtenido de FIXER API
sTIPOS_CAMBIO_PATH = os.path.join(BASE_DIR, "Data", "TiposDeCambio.csv")

# Cargar el archivo .env
load_dotenv()

# Diccionario global para almacenar tipos de cambio ya consultados
dTiposDeCambio = {}
# Diccionario para registrar fecha por combinación
dFechasTipoCambio = {}


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



def fObtenerTipoCambio():
   """
   Carga los tipos de cambio previamente guardados en el archivo CSV
   y los almacena en el diccionario global `dTiposDeCambio`.
   Si el archivo no existe, lo crea con los encabezados necesarios.
   """
   if not sTIPOS_CAMBIO_PATH:
      print("ERROR - Ruta al archivo CSV no definida.")
      return

   # Si no existe el archivo, crearlo con encabezados
   if not os.path.exists(sTIPOS_CAMBIO_PATH):
      with open(sTIPOS_CAMBIO_PATH, mode="w", newline='', encoding="utf-8") as f:
         writer = csv.DictWriter(f, fieldnames=["sMonedaOrigen", "sMonedaDestino", "sTipoCambio", "sFecha"])
         writer.writeheader()
      return  # Ya está creado, pero aún no hay datos que cargar

   # Leer archivo existente
   with open(sTIPOS_CAMBIO_PATH, mode="r", newline='', encoding="utf-8") as f:
      reader = csv.DictReader(f)
      for row in reader:
         sMonedaOrigen = row["sMonedaOrigen"]
         sMonedaDestino = row["sMonedaDestino"]
         sTipoCambio = float(row["sTipoCambio"])
         sFecha = row.get("sFecha", "")
         clave = f"{sMonedaOrigen}_{sMonedaDestino}"
         dTiposDeCambio[clave] = sTipoCambio
         dFechasTipoCambio[clave] = sFecha



def fGuardarTipoCambio(sMonedaOrigen, sMonedaDestino, sTipoCambio):
   """
   Guarda o actualiza un tipo de cambio en el archivo CSV, incluyendo la fecha de actualización.

   Si la combinación de monedas ya existe en el archivo, se actualiza tanto el valor del tipo de cambio
   como la fecha correspondiente. Si no existe, se añade una nueva fila con la información.

   Parámetros:
      sMonedaOrigen (str): Código de la moneda origen (ej. "MXN").
      sMonedaDestino (str): Código de la moneda destino (ej. "USD").
      sTipoCambio (float): Tipo de cambio de sMonedaOrigen a sMonedaDestino.
   """
   if not sTIPOS_CAMBIO_PATH:
      print("ERROR - Ruta al archivo CSV no definida.")
      return

   oHoy = datetime.today().strftime("%Y-%m-%d")
   datos_actualizados = []
   clave_objetivo = f"{sMonedaOrigen}_{sMonedaDestino}"
   ya_existia = False

   # Leer datos existentes (si el archivo existe)
   if os.path.exists(sTIPOS_CAMBIO_PATH):
      with open(sTIPOS_CAMBIO_PATH, mode="r", newline='', encoding="utf-8") as f:
         reader = csv.DictReader(f)
         for row in reader:
               clave = row["sMonedaOrigen"] + "_" + row["sMonedaDestino"]
               if clave == clave_objetivo:
                  row["sTipoCambio"] = str(sTipoCambio)  # Actualizar el valor
                  row["sFecha"] = oHoy
                  ya_existia = True
               datos_actualizados.append(row)

   # Si no existía la clave, añadirla
   if not ya_existia:
      datos_actualizados.append({
         "sMonedaOrigen": sMonedaOrigen,
         "sMonedaDestino": sMonedaDestino,
         "sTipoCambio": sTipoCambio,
         "sFecha": oHoy
      })

   # Escribir todo al archivo (sobrescribir)
   with open(sTIPOS_CAMBIO_PATH, mode="w", newline='', encoding="utf-8") as f:
      writer = csv.DictWriter(f, fieldnames=["sMonedaOrigen", "sMonedaDestino", "sTipoCambio", "sFecha"])
      writer.writeheader()
      writer.writerows(datos_actualizados)



def fObtenerCambioFixer(sMonedaOrigen, sMonedaDestino="USD"):
   """
   Obtiene el tipo de cambio entre dos monedas usando la API de Fixer, con control diario.

   Si el tipo de cambio ya ha sido obtenido en la fecha actual, se reutiliza desde la caché en memoria.
   Si no, se consulta la API de Fixer, se actualiza la caché y se guarda en el archivo CSV con la fecha.
   En caso de error en la consulta, intenta cargar el valor previamente almacenado en el archivo CSV.

   Parámetros:
      sMonedaOrigen (str): Código de la moneda origen (ej. "MXN").
      sMonedaDestino (str): Código de la moneda destino (por defecto "USD").

   Retorna:
      float: El tipo de cambio de sMonedaOrigen a sMonedaDestino.
   """
   global dTiposDeCambio, dFechasTipoCambio

   # Cargar tipos de cambio desde el CSV solo una vez
   if not dTiposDeCambio:
      fObtenerTipoCambio()

   sClaveCache = f"{sMonedaOrigen}_{sMonedaDestino}"
   oHoy = datetime.today().strftime("%Y-%m-%d")

   # Si ya está en caché y es de Hoy, usarlo
   if sClaveCache in dTiposDeCambio and dFechasTipoCambio.get(sClaveCache) == oHoy:
      return dTiposDeCambio[sClaveCache]

   # Obtener clave API desde variables de entorno
   sFIXER_API_KEY = os.getenv("FIXER_API_KEY")
   if not sFIXER_API_KEY:
      raise Exception("No se encontró FIXER_API_KEY en las variables de entorno")

   # Construir URL para consultar tipo de cambio con base en EUR
   sUrl = f"http://data.fixer.io/api/latest?access_key={sFIXER_API_KEY}&base=EUR&symbols={sMonedaOrigen},{sMonedaDestino}"
   sResponse = requests.get(sUrl)
   sDatos = sResponse.json()

   # Verificar si la respuesta fue exitosa
   if not sDatos.get("success", False):
      raise Exception(sDatos.get("error", {}).get("info", "Error desconocido en respuesta de Fixer"))

   # Calcular el tipo de cambio
   try:
      sTasaOrigen = sDatos["rates"][sMonedaOrigen]
      sTasaDestino = sDatos["rates"][sMonedaDestino]
   except KeyError as e:
      raise Exception(f"Moneda no encontrada en respuesta de Fixer: {str(e)}")
   
   sTipoCambio = round(sTasaDestino / sTasaOrigen, 3)

   # Guardar en caché y CSV
   dTiposDeCambio[sClaveCache] = sTipoCambio
   dFechasTipoCambio[sClaveCache] = oHoy
   fGuardarTipoCambio(sMonedaOrigen, sMonedaDestino, sTipoCambio)

   return sTipoCambio



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
      time.sleep(2)  # Pausa para evitar bloqueos
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

      # Inicializar el tipo de cambio con 1 por defecto (en caso de USD o error)
      dFactorCambio = 1

      # Solo convertir si la moneda no es USD
      if sMoneda != "USD":
         try:
            # Intentar obtener el tipo de cambio actual desde Fixer
            dFactorCambio = fObtenerCambioFixer(sMoneda, "USD")
         except Exception as e:
            # Mostrar mensaje de error si la API falla
            print(f"ERROR   - Error obteniendo tipo de cambio de '{sMoneda}' a USD: {e}")

            # Si hay un valor anterior almacenado en caché/CSV, usarlo
            if f"{sMoneda}_USD" in dTiposDeCambio:
               print(f"INFO    - Usando tipo de cambio antiguo guardado en CSV para {sMoneda}_USD")
               dFactorCambio = dTiposDeCambio[f"{sMoneda}_USD"]
            else:
               # Como último recurso, usar 1 como tipo de cambio de fallback
               dFactorCambio = 1


      # Función para convertir valores usando el tipo de cambio calculado
      def fConvertirMoneda(valor):
         # Solo convierte si es número (int o float), si no, devuelve NaN
         return valor * dFactorCambio if isinstance(valor, (int, float)) else np.nan
         
      # Extraer indicadores financieros clave
      lIndicadores = {
         "Precio ($)": round(fConvertirMoneda(lDatos.get("currentPrice")), 2),
         "Valor en Libros ($)": round(fConvertirMoneda(lDatos.get("bookValue")), 2),
         "P/E": round(lDatos.get("trailingPE"), 2) if isinstance(lDatos.get("trailingPE"), (int, float)) else np.nan,
         "PEG": np.nan,  # Se calcula más adelante si hay datos suficientes
         "EV/EBITDA": round(lDatos.get("enterpriseToEbitda"), 2) if isinstance(lDatos.get("enterpriseToEbitda"), (int, float)) else np.nan,
         "ROE (%)": round(lDatos.get("returnOnEquity") * 100, 2) if isinstance(lDatos.get("returnOnEquity"), (int, float)) else 0.0,
         "Margen Neto (%)": round(lDatos.get("profitMargins") * 100, 2) if isinstance(lDatos.get("profitMargins"), (int, float)) else 0.0,
         "Margen Operativo (%)": round(lDatos.get("operatingMargins") * 100, 2) if isinstance(lDatos.get("operatingMargins"), (int, float)) else 0.0,
         "FCF/Acción ($)": round(fConvertirMoneda(lDatos.get("freeCashflow")), 2) if isinstance(lDatos.get("freeCashflow"), (int, float)) else 0.0,
         "Dividend Yield (%)": round(lDatos.get("dividendYield") * 100, 2) if isinstance(lDatos.get("dividendYield"), (int, float)) else 0.0,
         "Beta": round(lDatos.get("beta"), 2) if isinstance(lDatos.get("beta"), (int, float)) else 1.0,
         "Deuda/Capital (%)": round(lDatos.get("debtToEquity"), 2) if isinstance(lDatos.get("debtToEquity"), (int, float)) else 0.0,
         "Crecimiento de Ingresos (%)": round(lDatos.get("revenueGrowth") * 100, 2) if isinstance(lDatos.get("revenueGrowth"), (int, float)) else 0.0,
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
      if not np.isnan(lIndicadores["P/E"]) and lIndicadores["Crecimiento de Ingresos (%)"] != 0:
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

      if lIndicadores["Dividend Yield (%)"] > 3:
         iPuntuacion += 2
      elif 1 <= lIndicadores["Dividend Yield (%)"] <= 3:
         iPuntuacion += 1
      else:
         iPuntuacion += 0

      if lIndicadores["Deuda/Capital (%)"] < 50:
         iPuntuacion += 2
      elif 50 <= lIndicadores["Deuda/Capital (%)"] <= 100:
         iPuntuacion += 1
      else:  # Deuda/Capital > 100
         iPuntuacion -= 1

      if lIndicadores["Crecimiento de Ingresos (%)"] > 10:
         iPuntuacion += 3
      elif 5 <= lIndicadores["Crecimiento de Ingresos (%)"] <= 10:
         iPuntuacion += 2
      elif 0 <= lIndicadores["Crecimiento de Ingresos (%)"] < 5:
         iPuntuacion += 1
      else:  # Crecimiento negativo
         iPuntuacion += 0

      if lIndicadores["FCF/Acción ($)"] > 0:
         iPuntuacion += 2

      if lIndicadores["ROE (%)"] > 15:
         iPuntuacion += 3
      elif 10 <= lIndicadores["ROE (%)"] <= 15:
         iPuntuacion += 2
      elif 5 <= lIndicadores["ROE (%)"] < 10:
         iPuntuacion += 1
      else:
         iPuntuacion += 0

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
      raise e


def fGenerarMetricas():
   """
   Función principal para obtener y evaluar las metricas de los tickers.
   """

   # Obtener tickers, omitiendo la primera fila (cabecera)
   df = pd.read_csv(sTICKER_LIST_PATH, encoding='utf-8')

   # Convertir todos los valores de la columna 'Ticker' a mayúsculas
   df['Ticker'] = df['Ticker'].str.upper()

   # Crear la lista de tickers
   lListaDeTickers = df['Ticker'].tolist()

   lResultados = []
   iContadorExitos = 0
   iContadorErrores = 0

   for sTicker in tqdm(lListaDeTickers, desc="Procesando acciones", unit="acción"):
   #for sTicker in tqdm(random.sample(lListaDeTickers, 10), desc="Procesando acciones", unit="acción"):

      try:
         lResultado = fEvaluarAccion(sTicker)

         if lResultado is not None:
            lResultados.append(lResultado)
            iContadorExitos += 1
            print(f"INFO    - Procesado correctamente: {sTicker}")
      except Exception as e:
         iContadorErrores += 1
         print(f"ERROR   - No se pudo procesar: {sTicker} | Detalle: {e}")

   # Ordenar por Puntuación, luego por ROE y luego por Crecimiento de Ingresos
   dfResultadosOrdenados = sorted(lResultados, key=lambda x: (x[6], x[16] if x[16] is not None else -1, x[14] if x[14] is not None else -1), reverse=True)


   lColumnas = [
   "Ticker", "Nombre", "Sector", "Continente", "País", "Calificación", "Puntuación", 
   "Precio ($)", "Valor en Libros ($)", "Valor Intrínseco ($)", "P/E", "PEG", "EV/EBITDA", "ROE (%)", 
   "Margen Neto (%)", "Margen Operativo (%)", "FCF/Acción ($)", "Dividend Yield (%)", "Beta", 
   "Deuda/Capital (%)", "Crecimiento de Ingresos (%)", "Capitalización ($)"
   ]

   # Crear DataFrame
   dfFinal = pd.DataFrame(dfResultadosOrdenados, columns=lColumnas)


   ################### LIMPIO COLUMNAS ##################
   # Reemplazar NaN en "Puntuación" con un valor negativo para evitar errores en ordenamiento
   dfFinal["Puntuación"] = dfFinal["Puntuación"].fillna(-1)

   # Aplicar redondeo a las columnas relevantes
   for col in ["Precio ($)", "Valor en Libros ($)", "Valor Intrínseco ($)", "P/E", "EV/EBITDA", "Dividend Yield (%)",
            "Deuda/Capital (%)", "Crecimiento de Ingresos (%)", "ROE (%)", "Margen Neto (%)",
            "Margen Operativo (%)", "Beta", "PEG"]:
      dfFinal[col] = dfFinal[col].round(2)

   dfFinal["FCF/Acción ($)"] = dfFinal["FCF/Acción ($)"].round(0)
   dfFinal["Capitalización ($)"] = dfFinal["Capitalización ($)"].round(0)
   ######################################################

   # Ordenar por Puntuación y, en caso de empate, por ROE (%) y P/E
   dfFinal = dfFinal.sort_values(by=["Puntuación", "ROE (%)", "P/E"], ascending=[False, False, True])

   # Guardar en Excel
   dfFinal.to_excel(sDATA_STOCKS_PATH, index=False)

   print(f"INFO    - TOTAL Tickers Correctos: {iContadorExitos}")
   print(f"INFO    - TOTAL Tickers Con Error: {iContadorErrores}")
   print(f"INFO    - Resultados guardados en: {sDATA_STOCKS_PATH}")
