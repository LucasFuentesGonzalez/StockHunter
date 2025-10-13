# main.py
import re, sys, os, time, io
from dotenv import load_dotenv

from Lib.ObtenerTickers import *
from Lib.GenerarMetricas import *
#from Lib.VisualizadorDeAcciones import *


if __name__ == "__main__":

   print(f'\n\n######################################################################\n')
   print(f'INFO    - INICIO MAIN \n')


   # Detectar si el script está empaquetado con PyInstaller
   if getattr(sys, 'frozen', False):
      BASE_DIR = sys._MEIPASS  # Ruta temporal generada por PyInstaller
   else:
      # Ruta base = carpeta del proyecto
      BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))

   # Ruta del ejecutable del visualizador de acciones
   sRUTA_DE_VISUALIZADOR = os.path.join(BASE_DIR, "Lib", "VisualizadorDeAcciones.py")


   ################### CONFIGURACION ####################
   bEjecutarfObtenerTickers = False
   bEjecutarfGenerarMetricas = False
   bEjecutarVisualizadorDeAcciones = True
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

      sRutaScript = sRUTA_DE_VISUALIZADOR
      os.system(f"streamlit run \"{sRutaScript}\"")
   ######################################################


   print(f'INFO    - FIN MAIN ')

   sys.exit(0) # Termina sin errores
