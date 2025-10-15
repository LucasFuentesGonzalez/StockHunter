# BotAlertaBursatilEmail.py
import os
import time
import pandas as pd
import yfinance as yf
import datetime as dt
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================
# CONFIGURACIÓN DE EMAIL
# =========================
# Cargar el archivo .env
load_dotenv()
# Obtener la Configuración de la API de GMAIL para envio de correos
sEmailUser = os.getenv('EMAIL_REMITENTE')
sEmailTo = os.getenv('EMAIL_DESTINATARIO')
sEmailPass = os.getenv('EMAIL_CLAVE_DE_APLICACION')

sSmtpServer = "smtp.gmail.com"
iSmtpPort = 587

# Intervalo de ejecución (segundos)
iCheckInterval = 3600  # 1 hora

# =========================
# CONFIGURACIÓN FINANCIERA
# =========================
dAssets = {
   "Oro": "GLD",           # ETF de oro
   "Bonos": "TLT",         # Bonos del tesoro
   "Dólar": "UUP",         # ETF del dólar
   "Bitcoin": "BTC-USD",   # Bitcoin en USD
   "VIX": "^VIX",          # Índice de volatilidad
   "S&P500": "^GSPC"       # Índice S&P 500
}

iMA_Short = 50
iMA_Long = 200
fThreshold = 0.5  # Cambio % mínimo para activar alerta

# =========================
# FUNCIONES
# =========================

def fValidateTickers(dAssets: dict) -> dict:
   """Valida los símbolos de los activos."""
   dValid = {}
   print("INFO    - Validando tickers...")
   for sName, sTicker in dAssets.items():
      try:
         # Intentar descargar datos del último día.
         df = yf.download(sTicker, period="1d", interval="1d", progress=False, auto_adjust=True)
            
         # Si se encuentran datos y el DataFrame no está vacío
         if not df.empty and len(df) > 0:
            print(f"INFO    - Ticker válido: {sName} ({sTicker})")
            dValid[sName] = sTicker
         else:
            print(f"WARNING - Ticker válido pero sin datos recientes: {sName} ({sTicker})")

      except Exception as e:
         print(f"ERROR   - Ticker inválido: {sName} ({sTicker}). Error: {e}")
   if not dValid:
      raise ValueError("No se encontró ningún ticker válido.")
   return dValid


def fSendEmailAlert(sSubject: str, sMessage: str):
   """Envía alerta por email."""
   try:
      msg = MIMEMultipart()
      msg["From"] = sEmailUser
      msg["To"] = sEmailTo
      msg["Subject"] = sSubject
      msg.attach(MIMEText(sMessage, "plain"))

      with smtplib.SMTP(sSmtpServer, iSmtpPort) as server:
         server.starttls()
         server.login(sEmailUser, sEmailPass)
         server.send_message(msg)
      print("INFO    - Alerta enviada por correo.")
   except Exception as e:
      print(f"ERROR   - Error al enviar correo: {e}")


def fLogAlert(sMessage: str):
   """Guarda la alerta en un CSV y registra evento en Logs/Log.log."""
   try:
      # Ruta base del script
      sBaseDir = os.path.dirname(os.path.abspath(__file__))
      sLogDir = os.path.join(sBaseDir, "Logs")
      os.makedirs(sLogDir, exist_ok=True)

      # Ruta completa del archivo Log.log
      sLogFile = os.path.join(sLogDir, "Log.log")

      # Fecha y formato
      sNow = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

      # Escribir en el log
      with open(sLogFile, "a", encoding="utf-8") as f:
         f.write(f"[{sNow}] {sMessage}\n")

      print(f"INFO    - Alerta registrada en {sLogFile}.")

   except Exception as e:
      print(f"ERROR   - No se pudo registrar alerta: {e}")


def fCheckDeathCross(sTicker: str, iShort=iMA_Short, iLong=iMA_Long) -> bool:
   """Detecta si hay un death cross en el activo."""
   try:
      df = yf.download(sTicker, period="1y", interval="1d", progress=False, auto_adjust=True)
      if df.empty or len(df) < iLong:
         return False
      df["MA_Short"] = df["Close"].rolling(iShort).mean()
      df["MA_Long"] = df["Close"].rolling(iLong).mean()
      return (
         df["MA_Short"].iloc[-2] > df["MA_Long"].iloc[-2]
         and df["MA_Short"].iloc[-1] < df["MA_Long"].iloc[-1]
      )
   except Exception as e:
      print(f"ERROR   - Error al verificar Death Cross en {sTicker}: {e}")
      return False


def fGetRealtimeChange(sTicker: str) -> float | None:
   """Calcula el cambio porcentual intradía (precio actual vs apertura)."""

   """# === BLOQUE DE SIMULACIÓN PARA PRUEBA (Descomentar para forzar envio de email) ===
   dFakeValues = {
      "GLD": 1,         # Oro sube
      "TLT": 1,         # Bonos suben
      "UUP": 1,         # Dólar 
      "BTC-USD": 1,     # Bitcoin neutro
      "^VIX": 2.1,      # Volatilidad sube
      "^GSPC": 0        # S&P500 cae
   }

   # Si el ticker está en la lista de prueba, devuelve ese valor directamente
   if sTicker in dFakeValues:
      print(f"INFO    - (TEST) Valor simulado para {sTicker}: {dFakeValues[sTicker]}%")
      return dFakeValues[sTicker]
   # === FIN DE BLOQUE DE SIMULACIÓN ==="""

   try:
      oTicker = yf.Ticker(sTicker)
      info = oTicker.info

      fOpen = info.get("regularMarketOpen")
      fPrice = info.get("regularMarketPrice")

      if not fOpen or not fPrice:
         print(f"WARNING - Datos incompletos para {sTicker}")
         return None

      fChange = ((fPrice - fOpen) / fOpen) * 100
      return round(fChange, 2)

   except Exception as e:
      print(f"ERROR   - Fallo al obtener cambio intradía de {sTicker}: {e}")
      return None


def fCheckAlerts(dAssetsChecked: dict):
   """Evalúa condiciones de alerta bursátil."""
   dChanges = {}
   for sName, sTicker in dAssetsChecked.items():
      fChange = fGetRealtimeChange(sTicker)
      print(f"INFO    - {sName}: {fChange}%")
      if fChange is not None:
         dChanges[sName] = fChange

   lsSafeAssets = ["Oro", "Bonos", "Dólar", "VIX"]
   lsRiskAssets = ["S&P500", "Bitcoin"]

   lsMessages = []

   # ================================
   # 1. Todos los refugios suben
   # ================================
   if all(dChanges.get(s, 0) > fThreshold for s in lsSafeAssets):
      lsMessages.append("⚠️ Todos los activos refugio suben simultáneamente — posible huida del riesgo global.")
      lsMessages.append("💡 Recomendación: Considerar reducir exposición a renta variable y aumentar liquidez o refugio.\n")

   # ==============================================
   # 2. S&P500 cae mientras refugios suben
   # ==============================================
   if dChanges.get("S&P500", 0) < -fThreshold and all(dChanges.get(s, 0) > fThreshold for s in lsSafeAssets):
      lsMessages.append("⚠️ El S&P500 cae mientras los refugios suben — los inversores buscan seguridad.")
      lsMessages.append("💡 Recomendación: Rebalancear cartera hacia activos defensivos y vigilar soportes clave del índice.\n")

   # ==============================================
   # 3. Death Cross en S&P500
   # ==============================================
   if fCheckDeathCross("^GSPC"):
      lsMessages.append("⚠️ Death Cross detectado en S&P500 — posible cambio a tendencia bajista de medio plazo.")
      lsMessages.append("💡 Recomendación: Revisar posiciones de largo plazo y considerar coberturas (put options, ETFs inversos).\n")

   # ==============================================
   # 4. Divergencia entre Bitcoin y S&P500
   # ==============================================
   if dChanges.get("Bitcoin") and dChanges.get("S&P500"):
      if dChanges["Bitcoin"] > fThreshold and dChanges["S&P500"] < -fThreshold:
         lsMessages.append("⚠️ Divergencia: Bitcoin sube mientras el S&P500 cae — apetito especulativo pese al riesgo en bolsa.\n")
         lsMessages.append("💡 Recomendación: Vigilar sostenibilidad del rally cripto y considerar toma de beneficios.")
      elif dChanges["Bitcoin"] < -fThreshold and dChanges["S&P500"] > fThreshold:
         lsMessages.append("⚠️ Divergencia: Bitcoin cae mientras el S&P500 sube — menor apetito por riesgo.")
         lsMessages.append("💡 Recomendación: Prudencia con activos volátiles; el mercado podría rotar hacia activos defensivos.\n")

   # ==============================================
   # 5. Caída generalizada del mercado
   # ==============================================
   iFalling = sum(1 for x in dChanges.values() if x < -fThreshold)
   if iFalling >= len(dChanges) * 0.7:  # 70% de activos cayendo
      lsMessages.append("⚠️ Caída generalizada: más del 70% de los activos están en negativo — posible corrección amplia.")
      lsMessages.append("💡 Recomendación: Evitar compras impulsivas, esperar señales de estabilización o soporte técnico.\n")

   # ==============================================
   # 6. Repunte de volatilidad fuerte (VIX)
   # ==============================================
   if dChanges.get("VIX", 0) > 10:  # +10% en el VIX es fuerte
      lsMessages.append("⚠️ Repunte fuerte de la volatilidad (VIX > +10%) — aumento del miedo en el mercado.")
      lsMessages.append("💡 Recomendación: Revisar stop-loss y mantener posición conservadora hasta que el VIX se normalice.\n")

   # ==============================================
   # 7. Oro y Bitcoin suben juntos
   # ==============================================
   if dChanges.get("Oro", 0) > fThreshold and dChanges.get("Bitcoin", 0) > fThreshold:
      lsMessages.append("⚠️ Oro y Bitcoin suben simultáneamente — búsqueda de refugios alternativos ante incertidumbre macro.")
      lsMessages.append("💡 Recomendación: Diversificar exposición a refugios; posible señal de pérdida de confianza en divisas fiat.\n")

   # ==============================================
   # 8. Dólar y Bonos caen juntos
   # ==============================================
   if dChanges.get("Dólar", 0) < -fThreshold and dChanges.get("Bonos", 0) < -fThreshold:
      lsMessages.append("⚠️ Dólar y Bonos caen juntos — posible cambio en expectativas de tipos o inflación.")
      lsMessages.append("💡 Recomendación: Vigilar decisiones de bancos centrales y evolución de rendimientos soberanos.\n")

   # ==============================================
   # 9. Rally coordinado en activos de riesgo
   # ==============================================
   if all(dChanges.get(s, 0) > fThreshold for s in lsRiskAssets):
      lsMessages.append("⚠️ Rally en activos de riesgo (S&P500 y Bitcoin suben) — apetito por riesgo creciente.")
      lsMessages.append("💡 Recomendación: Mantener exposición táctica, pero preparar estrategia de salida ante sobrecompra.\n")

   # ================================
   # Enviar email si hay alertas
   # ================================
   if lsMessages:
      sBody = "\n".join(lsMessages)
      sBody += "\nCambios actuales (%):\n"
      for sAsset, fChange in dChanges.items():
         sBody += f"{sAsset}: {fChange}%\n"

      fSendEmailAlert("📉 Alerta Bursátil - BotAlertaBursatilEmail.py", sBody)
      fLogAlert(sBody)
   else:
      print("INFO    - No se detectaron alertas en esta revisión.")

# =========================
# LOOP PRINCIPAL
# =========================
if __name__ == "__main__":
   print("INFO    - Sistema de alerta bursátil en tiempo casi real iniciado.")

   try:
      dValidAssets = fValidateTickers(dAssets)
      print(f"INFO    - {len(dValidAssets)} tickers válidos confirmados.\n")
   except Exception as e:
      print(f"ERROR   - Falló la validación de tickers: {e}")
      exit(1)

   while True:
      try:
         fCheckAlerts(dValidAssets)
      except Exception as e:
         print(f"ERROR   - Fallo en el ciclo principal: {e}")
      time.sleep(iCheckInterval)
