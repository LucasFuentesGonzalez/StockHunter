# Graficos\Heatmap.py
"""
Módulo: HeatmapGUI.py
Descripción:
   Interfaz gráfica con PyQt6 que permite seleccionar un filtro
   (por Continente, País o Sector) para visualizar una matriz de correlación
   entre variables financieras de un conjunto de empresas.
"""

import sys, os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Módulos de PyQt6
from PyQt6.QtWidgets import (
   QApplication, QWidget, QVBoxLayout, QLabel,
   QPushButton, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt


class HeatmapApp(QWidget):
   """
   Clase principal de la aplicación PyQt6.
   Crea una interfaz gráfica para filtrar y generar un heatmap.
   """

   def __init__(self):
      super().__init__()

      # --- Configuración inicial de la ventana ---
      self.setWindowTitle("Generar Heatmap de Correlaciones")
      self.setGeometry(300, 200, 400, 250)

      # --- Layout principal ---
      self.oLayoutPrincipal = QVBoxLayout()

      # --- Detección del directorio base ---
      if getattr(sys, 'frozen', False):
         sBaseDir = sys._MEIPASS  # Si el script está empaquetado (PyInstaller)
      else:
         sBaseDir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

      # --- Ruta del archivo Excel con los datos ---
      sRutaExcel = os.path.join(sBaseDir, "Data", "ListadoDeMejoresAcciones.xlsx")

      # --- Cargar el archivo Excel ---
      try:
         self.dfDatos = pd.read_excel(sRutaExcel, engine='openpyxl')
      except Exception as e:
         QMessageBox.critical(self, "Error", f"No se pudo cargar el archivo Excel:\n{e}")
         sys.exit(1)

      # --- Definir las columnas numéricas relevantes ---
      self.lstColumnasNumericas = [
         'Puntuación', 'Precio ($)', 'Valor en Libros ($)', 'P/E', 'EV/EBITDA',
         'Dividend Yield (%)', 'Deuda/Capital (%)', 'Crecimiento de Ingresos (%)',
         'FCF/Acción ($)', 'ROE (%)', 'Margen Neto (%)', 'Margen Operativo (%)',
         'Beta', 'Capitalización ($)', 'PEG'
      ]

      # Convertir las columnas a tipo numérico (forzando errores a NaN)
      self.dfDatos[self.lstColumnasNumericas] = self.dfDatos[self.lstColumnasNumericas].apply(
         pd.to_numeric, errors='coerce'
      )

      # --- Widgets de la interfaz ---
      self.lblFiltro = QLabel("Filtrar por:")
      self.cboFiltro = QComboBox()
      self.cboFiltro.addItems(["Sin filtro", "Continente", "País", "Sector"])
      self.cboFiltro.currentIndexChanged.connect(self.fActualizarValores)

      self.lblValor = QLabel("Valor del filtro:")
      self.cboValor = QComboBox()
      self.cboValor.addItem("(Seleccione un filtro primero)")

      self.btnGenerar = QPushButton("Generar Heatmap")
      self.btnGenerar.clicked.connect(self.fGenerarHeatmap)

      # --- Agregar widgets al layout ---
      self.oLayoutPrincipal.addWidget(self.lblFiltro)
      self.oLayoutPrincipal.addWidget(self.cboFiltro)
      self.oLayoutPrincipal.addWidget(self.lblValor)
      self.oLayoutPrincipal.addWidget(self.cboValor)
      self.oLayoutPrincipal.addStretch()
      self.oLayoutPrincipal.addWidget(self.btnGenerar)

      self.setLayout(self.oLayoutPrincipal)

      # Inicializar el combo de valores
      self.fActualizarValores()

   # ----------------------------------------------------------------------
   def fActualizarValores(self):
      """
      Actualiza la lista de valores disponibles según el filtro seleccionado.
      """
      self.cboValor.clear()
      sFiltroSeleccionado = self.cboFiltro.currentText()

      if sFiltroSeleccionado == "Sin filtro":
         self.cboValor.addItem("(No se aplica filtro)")
         return

      # Obtener valores únicos del campo seleccionado
      lstValores = sorted(self.dfDatos[sFiltroSeleccionado].dropna().unique())
      self.cboValor.addItems(lstValores)

   # ----------------------------------------------------------------------
   def fGenerarHeatmap(self):
      """
      Filtra el DataFrame según el filtro elegido y genera el heatmap de correlaciones.
      """
      sFiltro = self.cboFiltro.currentText()
      sValor = self.cboValor.currentText()

      # Copiar el DataFrame original
      dfFiltrado = self.dfDatos.copy()

      # Aplicar filtro si corresponde
      if sFiltro != "Sin filtro" and "(Seleccione" not in sValor:
         dfFiltrado = dfFiltrado[dfFiltrado[sFiltro] == sValor]

      # Eliminar filas con valores faltantes en las columnas numéricas
      dfFiltrado = dfFiltrado.dropna(subset=self.lstColumnasNumericas)

      # Validar que haya datos suficientes
      if dfFiltrado.empty:
         QMessageBox.warning(self, "Sin datos", "No hay registros válidos para este filtro.")
         return

      # Calcular la matriz de correlación
      dfCorrelacion = dfFiltrado[self.lstColumnasNumericas].corr()

      # --- Mostrar heatmap con Seaborn ---
      plt.figure(figsize=(14, 10))
      sns.heatmap(
         dfCorrelacion,
         annot=True, fmt=".2f",
         cmap="coolwarm", linewidths=0.5
      )
      plt.title(f"Matriz de Correlación ({sFiltro}: {sValor}) - {len(dfFiltrado)} empresas")
      plt.tight_layout()
      plt.show()


# ----------------------------------------------------------------------
if __name__ == "__main__":
   """
   Punto de entrada principal del programa.
   Inicia la aplicación PyQt6 y muestra la ventana principal.
   """
   oApp = QApplication(sys.argv)
   oVentana = HeatmapApp()
   oVentana.show()
   sys.exit(oApp.exec())
