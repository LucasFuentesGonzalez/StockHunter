# BotAlertaBursatilEmail.py
import sys, os
import time
import json
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
# =========================
# UMBRALES DE ALERTA
# =========================
# Cambio % mínimo para activar alerta
dUmbrales = {
   "default": 0.5,
   "Oro": 0.4,
   "Bonos": 0.3,
   "Dólar": 0.4,
   "VIX": 1.0,
   "S&P500": 0.6,
   "Bitcoin": 2.0
}


# =========================
# FUNCIONES
# =========================
def fObtenerUmbral(sAsset: str) -> float:
   return dUmbrales.get(sAsset, dUmbrales["default"])


def fValidarTickers(dAssets: dict) -> dict:
   """Valida los símbolos de los activos."""
   dValid = {}
   fAñadirALog("INFO", "Validando tickers...")
   for sName, sTicker in dAssets.items():
      try:
         # Intentar descargar datos del último día.
         df = yf.download(sTicker, period="1d", interval="1d", progress=False, auto_adjust=True)
            
         # Si se encuentran datos y el DataFrame no está vacío
         if not df.empty and len(df) > 0:
            #fAñadirALog("INFO", f"Ticker válido: {sName} ({sTicker})")
            dValid[sName] = sTicker
         else:
            fAñadirALog("WARNING", f"Ticker válido pero sin datos recientes: {sName} ({sTicker})")

      except Exception as e:
         fAñadirALog("ERROR", f"Ticker inválido: {sName} ({sTicker}). Error: {e}")
         
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
      msg.attach(MIMEText(sMessage, "html"))

      with smtplib.SMTP(sSmtpServer, iSmtpPort) as server:
         server.starttls()
         server.login(sEmailUser, sEmailPass)
         server.send_message(msg)
      fAñadirALog("INFO", "Alerta enviada por correo.")
   except Exception as e:
      fAñadirALog("ERROR", f"Error al enviar correo: {e}")

# =========================
# GESTIÓN DE ALERTAS ENVIADAS
# =========================
ALERT_FILE = "alertas_enviadas.json"

def fCargarAlertas():
   if os.path.exists(ALERT_FILE):
      with open(ALERT_FILE, "r") as f:
         return json.load(f)
   return {}


def fGuardarAlertas(dAlerts):
   with open(ALERT_FILE, "w") as f:
      json.dump(dAlerts, f)


def RevisionParaMandarAlerta(alert_id: str) -> bool:
   """
   Devuelve True si la alerta no se envió hoy.
   Registra su envío si procede.
   """
   today = dt.date.today().isoformat()
   dAlerts = fCargarAlertas()

   # Inicializar día si no existe
   if today not in dAlerts:
      dAlerts[today] = {}

   # Si ya se envió, no repetir
   if dAlerts[today].get(alert_id, False):
      return False

   # Marcar como enviada
   dAlerts[today][alert_id] = True
   fGuardarAlertas(dAlerts)

   return True
# =========================

def fAñadirALog(sLevel: str, sMessage: str):
   """Guarda la alerta en un CSV y registra evento en Logs/Log.log."""
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
      f.write(f"[{sNow}] {sLevel:<8} - {sMessage}\n")


def fCheckearDeathCross(sTicker: str, iShort=50, iLong=200) -> bool:
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
      fAñadirALog("ERROR", f"Error al verificar Death Cross en {sTicker}: {e}")
      return False


def fObtenerCambioEnTiempoReal(sTicker: str) -> float | None:
   """Calcula el cambio porcentual intradía (precio actual vs apertura)."""

   """# === BLOQUE DE SIMULACIÓN PARA PRUEBA (Descomentar para forzar envio de email) ===
   dFakeValues = {
      "GLD": 1.33,         # Oro sube
      "TLT": 0.89,         # Bonos suben
      "UUP": 0.6,         # Dólar 
      "BTC-USD": -2.32,     # Bitcoin neutro
      "^VIX": 5.87,      # Volatilidad sube
      "^GSPC":  -0.9        # S&P500 cae
   }

   # Si el ticker está en la lista de prueba, devuelve ese valor directamente
   if sTicker in dFakeValues:
      fAñadirALog("INFO", f"(TEST) Valor simulado para {sTicker}: {dFakeValues[sTicker]}%")
      return dFakeValues[sTicker]
   # === FIN DE BLOQUE DE SIMULACIÓN ==="""
   
   try:
      df = yf.download(sTicker, period="1d", interval="1m", progress=False, auto_adjust=True)
      if df.empty:
         fAñadirALog("WARNING", f"No se pudieron obtener datos intradía para {sTicker}")
         return None

      # Usa el primer valor de apertura y el último de cierre
      fOpen = df["Open"].iloc[0].item()
      fPrice = df["Close"].iloc[-1].item()
      fChange = ((fPrice - fOpen) / fOpen) * 100
      return round(fChange, 2)

   except Exception as e:
      fAñadirALog("ERROR", f"Fallo al obtener cambio intradía de {sTicker}: {e}")
      return None


def fCheckearAlertas(dAssetsChecked: dict):
   """Evalúa condiciones de alerta bursátil."""
   dChanges = {}
   for sName, sTicker in dAssetsChecked.items():
      fChange = fObtenerCambioEnTiempoReal(sTicker)
      fAñadirALog("INFO", f"{sName}: {fChange}%")
      if fChange is not None:
         dChanges[sName] = fChange

   lsSafeAssets = ["Oro", "Bonos", "Dólar", "VIX"]
   lsRiskAssets = ["S&P500", "Bitcoin"]

   lsMessages = []

   # ================================
   # 1. Todos los refugios suben
   # ================================
   if all(dChanges.get(s, 0) > fObtenerUmbral(s) for s in lsSafeAssets):
      if RevisionParaMandarAlerta("refugios_suben"):
         lsMessages.append("⚠️ Todos los activos refugio suben simultáneamente — posible huida del riesgo global.")
         lsMessages.append("💡 Recomendación: Considerar reducir exposición a renta variable y aumentar liquidez o refugio.<br>")

   # ==============================================
   # 2. S&P500 cae mientras refugios suben
   # ==============================================
   if (dChanges.get("S&P500", 0) < -fObtenerUmbral("S&P500") and all(dChanges.get(s, 0) > fObtenerUmbral(s) for s in lsSafeAssets)):
      if RevisionParaMandarAlerta("sp500_vs_refugios"):
         lsMessages.append("⚠️ El S&P500 cae mientras los refugios suben — los inversores buscan seguridad.")
         lsMessages.append("💡 Recomendación: Rebalancear cartera hacia activos defensivos y vigilar soportes clave del índice.<br>")

   # ==============================================
   # 3. Death Cross en S&P500
   # ==============================================
   if fCheckearDeathCross("^GSPC"):
      if RevisionParaMandarAlerta("death_cross"):
         lsMessages.append("⚠️ Death Cross detectado en S&P500 — posible cambio a tendencia bajista de medio plazo.")
         lsMessages.append("💡 Recomendación: Revisar posiciones de largo plazo y considerar coberturas (put options, ETFs inversos).<br>")

   # ==============================================
   # 4. Divergencia entre Bitcoin y S&P500
   # ==============================================
   if dChanges.get("Bitcoin") and dChanges.get("S&P500"):
      if (dChanges["Bitcoin"] > fObtenerUmbral("Bitcoin") and dChanges["S&P500"] < -fObtenerUmbral("S&P500")):
         if RevisionParaMandarAlerta("divergencia_btc_sp500_up"):
            lsMessages.append("⚠️ Divergencia: Bitcoin sube mientras el S&P500 cae — apetito especulativo pese al riesgo en bolsa.<br>")
            lsMessages.append("💡 Recomendación: Vigilar sostenibilidad del rally cripto y considerar toma de beneficios.")
      elif (dChanges["Bitcoin"] < -fObtenerUmbral("Bitcoin") and dChanges["S&P500"] > fObtenerUmbral("S&P500")):
         if RevisionParaMandarAlerta("divergencia_btc_sp500_down"):
            lsMessages.append("⚠️ Divergencia: Bitcoin cae mientras el S&P500 sube — menor apetito por riesgo.")
            lsMessages.append("💡 Recomendación: Prudencia con activos volátiles; el mercado podría rotar hacia activos defensivos.<br>")

   # ==============================================
   # 5. Caída generalizada del mercado
   # ==============================================
   iFalling = sum(1 for s, x in dChanges.items() if x < -fObtenerUmbral(s))
   if iFalling >= len(dChanges) * 0.7:  # 70% de activos cayendo
      if RevisionParaMandarAlerta("caida_general"):
         lsMessages.append("⚠️ Caída generalizada: más del 70% de los activos están en negativo — posible corrección amplia.")
         lsMessages.append("💡 Recomendación: Evitar compras impulsivas, esperar señales de estabilización o soporte técnico.<br>")

   # ==============================================
   # 6. Repunte de volatilidad fuerte (VIX)
   # ==============================================
   if dChanges.get("VIX", 0) > 10:  # +10% en el VIX es fuerte
      if RevisionParaMandarAlerta("vix_10"):
         lsMessages.append("⚠️ Repunte fuerte de la volatilidad (VIX > +10%) — aumento del miedo en el mercado.")
         lsMessages.append("💡 Recomendación: Revisar stop-loss y mantener posición conservadora hasta que el VIX se normalice.<br>")

   # ==============================================
   # 7. Oro y Bitcoin suben juntos
   # ==============================================
   if (dChanges.get("Oro", 0) > fObtenerUmbral("Oro") and dChanges.get("Bitcoin", 0) > fObtenerUmbral("Bitcoin")):
      if RevisionParaMandarAlerta("oro_btc"):
         lsMessages.append("⚠️ Oro y Bitcoin suben simultáneamente — búsqueda de refugios alternativos ante incertidumbre macro.")
         lsMessages.append("💡 Recomendación: Diversificar exposición a refugios; posible señal de pérdida de confianza en divisas fiat.<br>")

   # ==============================================
   # 8. Dólar y Bonos caen juntos
   # ==============================================
   if (dChanges.get("Dólar", 0) < -fObtenerUmbral("Dólar") and dChanges.get("Bonos", 0) < -fObtenerUmbral("Bonos")):
      if RevisionParaMandarAlerta("usd_bonos"):
         lsMessages.append("⚠️ Dólar y Bonos caen juntos — posible cambio en expectativas de tipos o inflación.")
         lsMessages.append("💡 Recomendación: Vigilar decisiones de bancos centrales y evolución de rendimientos soberanos.<br>")

   # ==============================================
   # 9. Rally coordinado en activos de riesgo
   # ==============================================
   if all(dChanges.get(s, 0) > fObtenerUmbral(s) for s in lsRiskAssets):
      if RevisionParaMandarAlerta("rally_riesgo"):
         lsMessages.append("⚠️ Rally en activos de riesgo (S&P500 y Bitcoin suben) — apetito por riesgo creciente.")
         lsMessages.append("💡 Recomendación: Mantener exposición táctica, pero preparar estrategia de salida ante sobrecompra.<br>")

   # ================================
   # Enviar email si hay alertas
   # ================================
   if lsMessages:
      sNow = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
      sFormattedMessages = "<br>".join(lsMessages)

      sBody = f"""
      <html>
      <body style="font-family:Arial, sans-serif; font-size:14px; color:#222;">
      <p>📊 <b>Alerta Bursátil - Revisión del {sNow}</b></p>

      <p>{sFormattedMessages}</p><br>

      <p style="margin-bottom:2px; margin-top:4px;">🛡️ <b>Activos Refugio:</b></p>
      <table style="border-collapse:collapse; margin-left:10px; margin-top:2px;">
      """
      for s in ["Oro", "Bonos", "Dólar", "VIX"]:
         if s in dChanges:
            sBody += f"<tr><td style='padding-right:15px;'>{s}</td><td align='right'>{dChanges[s]:+.2f}%</td></tr>"
      sBody += """
      </table>

      <p style="margin-bottom:2px; margin-top:8px;">🚀 <b>Activos de Riesgo:</b></p>
      <table style="border-collapse:collapse; margin-left:10px; margin-top:2px;">
      """
      for s in ["S&P500", "Bitcoin"]:
         if s in dChanges:
            sBody += f"<tr><td style='padding-right:15px;'>{s}</td><td align='right'>{dChanges[s]:+.2f}%</td></tr>"
      sBody += """
      </table><br>

      <p style="font-size:12px; color:#666; margin-top:12px;">
         <i>Mensaje generado automáticamente por el Bot de Alerta Bursátil.</i>
      </p>
      </body>
      </html>
      """

      fSendEmailAlert("📉 Alerta Bursátil - BotAlertaBursatilEmail.py", sBody)
      fAñadirALog(sBody)

   else:
      fAñadirALog("INFO", "No se detectaron alertas en esta revisión.")

# =========================
# LOOP PRINCIPAL
# =========================
if __name__ == "__main__":
   fAñadirALog("INFO", f"Inicio BotAlertaBursatilEmail")

   try:
      dValidAssets = fValidarTickers(dAssets)
      fAñadirALog("INFO", f"{len(dValidAssets)} tickers válidos confirmados.")
   except Exception as e:
      fAñadirALog("ERROR", f"Falló la validación de tickers: {e}")
      sys.exit(1)  

   try:
      fCheckearAlertas(dValidAssets)
   except Exception as e:
      fAñadirALog("ERROR", f"Fallo en el ciclo principal: {e}")
   finally:
      fAñadirALog("INFO", f"Fin BotAlertaBursatilEmail \n\n")