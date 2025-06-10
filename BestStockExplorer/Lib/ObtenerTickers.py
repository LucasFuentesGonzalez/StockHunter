# Lib\ObtenerTickers.py
import re, sys, os, time
import json
import numpy as np
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
from unidecode import unidecode
from bs4 import BeautifulSoup
from seleniumbase import SB, BaseCase
from typing import List, Tuple, Optional, Dict

"""
================================================================================
Scraper de Tickers de Empresas en Índices Bursátiles Globales
--------------------------------------------------------------------------------

Este script extrae los tickers de empresas que conforman los principales índices
bursátiles del mundo, a partir de un archivo CSV basado en Investing.com:
https://www.investing.com/indices/major-indices

================================================================================
"""


# Detectar si el script está empaquetado con PyInstaller
if getattr(sys, 'frozen', False):
   BASE_DIR = sys._MEIPASS  # Ruta temporal generada por PyInstaller
else:
   # Ruta base = carpeta del proyecto
   BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Ruta para almacenar las empresas, sus nombres y Ticker
sTICKER_LIST_PATH = os.path.join(BASE_DIR, "Data", "TickersDeEmpresas.csv")
# Ruta para almacenar los indices de los mercados, se guarda su pais, indice y sufijo del indice para yfinance
sMAYOR_WORLD_INDICES_PATH = os.path.join(BASE_DIR, "Data", "IndicesGlobales.csv")
# Ruta para almacenar la configuracion del SCRAPEADOR_DE_TICKERS
sCONFIG_PATH = os.path.join(BASE_DIR, "Config", "Config.json")


# ================= FUNCIONES =================
def fAbrirURLYObtenerHtml(sbDriver: BaseCase, sUrl: str, sCookies: str, iTiempoSleep: int) -> Optional[BeautifulSoup]:
   """
   Función para inicializar un navegador, visitar una URL y aceptar cookies si es necesario.

   Args:
      - sbDriver (BaseCase): Objeto SeleniumBase para controlar el navegador.
      - sUrl (str): La URL del sitio web al que se desea acceder.
      - sCookies (str): Selector para el botón de aceptación de cookies.
      - iTiempoSleep (int): Tiempo de espera en segundos antes de continuar.

   Returns:
      - oSoup (obj): Objeto BeautifulSoup que contiene el HTML analizado de la página.
   """
   try:
      # Abrir el navegador y cargar la URL  
      sbDriver.open(sUrl)
      sbDriver.sleep(iTiempoSleep)

      # Aceptamos las cookies si estan visibles
      if sCookies and sbDriver.is_element_visible(sCookies):
         sbDriver.click(sCookies)
         sbDriver.sleep(iTiempoSleep)

      try:
         # Obtener el contenido HTML de la página
         sHtml = sbDriver.get_page_source()
         # Crear el objeto BeautifulSoup para analizar el HTML
         oSoup = BeautifulSoup(sHtml, 'lxml')
      except Exception as e:
         print(f'\nERROR   - fAbrirURLYObtenerHtml - Error al Obtener HTML en sUrl: {sUrl} \n {e} \n')

      return oSoup
   
   except Exception as e:
      print(f'\nERROR   - fAbrirURLYObtenerHtml - Error al abrir la sURL: {sUrl}: \n {e} \n')
      return None


def fObtenerEmpresasDelIndice(oSoup, sbDriver: BaseCase, iTiempoSleep: int) -> List[str]:
   """
   Extrae el nombre y enlace de las empresas desde el indice.
   """
   lEmpresasDelIndice = []
   # Buscar todas las filas de la tabla de empresas
   oTablaEmpresas = oSoup.find('tbody', class_='datatable-v2_body__8TXQk')


   # Si no encuentra la tabla se debe a que la pagina nos redirije a otra url, para llegar a la correcta clicamos el boton de 'Components'
   if not oTablaEmpresas:
      # Esperamos a que el enlace de 'Components' esté visible, y luego hacemos clic
      sbDriver.wait_for_element('ul[data-test="sub-link-items"] a', timeout=10)
      sbDriver.click('ul[data-test="sub-link-items"] a')  # Hacemos clic en el primer enlace dentro de ese <ul>
      sbDriver.sleep(iTiempoSleep)  # Esperamos el tiempo indicado para que la página cargue
      # Esperar a que la tabla se cargue
      sbDriver.wait_for_element('tbody.datatable-v2_body__8TXQk', timeout=10)
      # Obtener el nuevo HTML después de la redirección
      sHtml = sbDriver.get_page_source()
      oSoup = BeautifulSoup(sHtml, 'lxml')
      oTablaEmpresas = oSoup.find('tbody', class_='datatable-v2_body__8TXQk')


   # Recorrer las filas de la tabla de empresas para guardar las URL
   for oFila in oTablaEmpresas.find_all('tr', class_='datatable-v2_row__hkEus'):
      oCeldaNombre = oFila.find('td', class_='dynamic-table-v2_col-name__Xhsxv')
      if oCeldaNombre:
         oEnlace = oCeldaNombre.find('a')
         if oEnlace and 'href' in oEnlace.attrs:
            sUrlEmpresa = oEnlace['href'].strip()
            lEmpresasDelIndice.append(f"{sUrlEmpresa}")
         else:
            print("\nERROR   - Enlace de empresa no encontrado o no contiene 'href'")
      else:
         print("\nERROR   - Celda de nombre de empresa no encontrada")

   return lEmpresasDelIndice


def fObtenerDatosEmpresas(oSoup, sEnlace, sSufijo):
   """
   Extrae el nombre y ticker de una empresa desde su página.
   """
   for oTitulo in oSoup.find_all('h1'):
      oMatch = re.match(r'^(.*?)\s+\(([^)]+)\)$', oTitulo.get_text(strip=True))
      if oMatch:
         sNombreEmpresa = oMatch.group(1).strip()
         sTickerEmpresa = oMatch.group(2).strip()

         # Añadir sufijo si existe
         sTickerConSufijo = sTickerEmpresa + sSufijo if sSufijo else sTickerEmpresa
         
         return {
               'Nombre': sNombreEmpresa,
               'Ticker': sTickerConSufijo,
         }

   print(f"ERROR   - No se encontró un <h1> con formato válido en: {sEnlace} \n")
   return None


def fObtenerTickers() -> None:
   """
   Función principal para el scraping de tickers de los mercados en la pagina de https://www.investing.com/indices/major-indices
   """
   ########################### CONFIGURACION ###########################
   try:
      with open(sCONFIG_PATH, 'r') as sFicheroConfig:
         dConfiguracion = json.load(sFicheroConfig)
      # Obtener los valores de SCRAPEADOR_DE_TICKERS
      dConfigGeneral = dConfiguracion['SCRAPEADOR_DE_TICKERS']
      iSaltarIndice = int(dConfigGeneral['iSaltarIndice'])
      iSaltarEmpresa = int(dConfigGeneral['iSaltarEmpresa'])
      iTiempoSleep = int(dConfigGeneral['iTiempoSleep'])
   except FileNotFoundError:
      print(f"ERROR   - fScrapeadorIdealista: El archivo {sCONFIG_PATH} no se encuentra. \n")
   except KeyError as e:
      print(f"ERROR   - fScrapeadorIdealista: Clave no encontrada en el archivo JSON: {e} \n")

   
   # Lista para almacenar las empresas de los indices
   lEmpresasDelIndice = []
   # Lista para almacenar los datos extraídos de las empresas
   lDatosEmpresas = []
   #####################################################################

   # Cargar CSV de empresas ya existentes (si existe)
   if os.path.exists(sTICKER_LIST_PATH) and os.path.getsize(sTICKER_LIST_PATH) > 0:
      dfEmpresasExistentes = pd.read_csv(sTICKER_LIST_PATH)
      setTickersExistentes = set(dfEmpresasExistentes['Ticker'].astype(str))
   else:
      dfEmpresasExistentes = pd.DataFrame(columns=['Indice', 'Nombre', 'Ticker'])
      setTickersExistentes = set()

   # Crear una instancia de SB con undetected-chromedriver
   with SB(uc=True) as sbDriver:


   ######################## Scrapear Indices ###########################
      # Obtener Indices, omitiendo la primera fila (cabecera)
      dfIndicesDeMercado = pd.read_csv(sMAYOR_WORLD_INDICES_PATH, encoding='utf-8')
      # Contamos el numero total de indices
      iTotalIndices = max(0, len(dfIndicesDeMercado) - iSaltarIndice)
      print(f"==> iTotalIndices: {iTotalIndices}")


   ####################### Scrapear Empresas ###########################
      # Ahora recorrer cada URL de los indices filtrados
      for iIndice, fila in enumerate(tqdm(dfIndicesDeMercado.iloc[iSaltarIndice:].itertuples(index=False), desc="Procesando índices", unit="Índice"), start=iSaltarIndice):
         sIndice = fila.Indice
         sSufijo = fila.Sufijo if isinstance(fila.Sufijo, str) else ""
 
         # Construir la URL completa
         sUrl = f"https://www.investing.com/indices/{sIndice}-components"
         print(f"\nÍndice: {sIndice} - {sUrl}")
         
         # Resetear el salto de Empresa al pasar a un nuevo indice
         if iIndice > iSaltarIndice:
            iSaltarEmpresa = 0 
         
         # Obtener el HTML de la página del indice
         oSoup = fAbrirURLYObtenerHtml(sbDriver, sUrl, '#onetrust-accept-btn-handler', iTiempoSleep)
         lEmpresasDelIndice = fObtenerEmpresasDelIndice(oSoup, sbDriver, iTiempoSleep)
         # Contamos el numero total de empresas en el indice
         iTotalEmpresas = max(0, len(lEmpresasDelIndice) - iSaltarEmpresa)
         print(f"==> iTotalEmpresas: {iTotalEmpresas}")


   #################### Scrapear Datos de Empresas #####################
         # Recorrer las filas de la tabla de componentes
         for iEmpresa, sEnlace in enumerate(lEmpresasDelIndice[iSaltarEmpresa:], start=iSaltarEmpresa):
            print(f"==> [{iEmpresa}/{iTotalEmpresas}] Procesando empresa: {sEnlace}")

            # Obtener el HTML de la página de la empresa
            oSoup = fAbrirURLYObtenerHtml(sbDriver, sEnlace, '#onetrust-accept-btn-handler', iTiempoSleep)
            dDatosEmpresa = fObtenerDatosEmpresas(oSoup, sEnlace, sSufijo)

            if dDatosEmpresa:
               sTickerNuevo = dDatosEmpresa['Ticker']
               if sTickerNuevo not in setTickersExistentes:
                  print(f"[NUEVO] Agregando empresa: {dDatosEmpresa['Nombre'].encode('ascii', errors='replace').decode()} ({sTickerNuevo})")


                  # Añadir 'Indice' a los datos de empresa antes de guardarlo
                  dDatosEmpresa['Indice'] = sIndice
                  
                  # Añadir al DataFrame en memoria
                  dfEmpresasExistentes = pd.concat([dfEmpresasExistentes, pd.DataFrame([dDatosEmpresa])], ignore_index=True)
                  setTickersExistentes.add(sTickerNuevo)

                  # Guardar el resultado en un archivo CSV
                  dfEmpresasExistentes.to_csv(sTICKER_LIST_PATH, index=False, encoding='utf-8')
               else:
                  print(f"[EXISTENTE] Ya registrado: {dDatosEmpresa['Nombre'].encode('ascii', errors='replace').decode()} ({sTickerNuevo})")

