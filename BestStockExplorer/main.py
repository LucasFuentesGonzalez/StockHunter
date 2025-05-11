# main.py
import re, sys, os, time, io
from dotenv import load_dotenv

from Lib.ObtenerTickers import *
from Lib.GenerarMetricas import *
#from Lib.VisualizadorDeAcciones import *


if __name__ == "__main__":

   print(f'\n\n######################################################################\n')
   print(f'INFO    - INICIO MAIN \n')

   ################### CONFIGURACION ####################
   bEjecutarfObtenerTickers = False
   bEjecutarfGenerarMetricas = True
   bEjecutarVisualizadorDeAcciones = False
   ######################################################


   ############### SCRAPEADOR DE TICKERS ################
   if bEjecutarfObtenerTickers:
      fObtenerTickers()

   ######################################################


   ########## GENERAR METRICAS DE LAS EMPRESAS ##########
   if bEjecutarfGenerarMetricas:
      fGenerarMetricas()

   ######################################################


   ##########  VISUALIZAR PANEL DE ACCIONES  ############
   if bEjecutarVisualizadorDeAcciones:
      # Cargar el archivo .env
      load_dotenv()
      # Obtener la ruta desde el archivo .env
      sRUTA_DE_VISUALIZADOR = os.getenv('RUTA_DE_VISUALIZADOR')

      sRutaScript = sRUTA_DE_VISUALIZADOR
      os.system(f"streamlit run \"{sRutaScript}\"")


   ######################################################


   print(f'INFO    - FIN MAIN ')

   sys.exit(0) # Termina sin errores
