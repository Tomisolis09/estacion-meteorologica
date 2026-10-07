import sys
import requests
import webbrowser
import json
import os
import unicodedata
import subprocess
import tempfile
import time
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QStringListModel
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QMessageBox,
    QComboBox,
    QCompleter,
    QDialog
)


# ==============================================================
# CONFIGURACIÓN
# ==============================================================

ARCHIVO_CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "configuracion.json"
)

ARCHIVO_ICONO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "icono.png"
)


# ==============================================================
# ACTUALIZACIONES
# ==============================================================

# IMPORTANTE:
# Dejamos 1.0.0 para probar que detecte la versión 1.1.0
VERSION = "1.0.0"

URL_VERSION = (
    "https://raw.githubusercontent.com/"
    "Tomisolis09/estacion-meteorologica/main/version.json"
)

DIAS_SEMANA = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo"
]


PROVINCIAS = [
    "Buenos Aires",
    "Catamarca",
    "Chaco",
    "Chubut",
    "Ciudad Autónoma de Buenos Aires",
    "Córdoba",
    "Corrientes",
    "Entre Ríos",
    "Formosa",
    "Jujuy",
    "La Pampa",
    "La Rioja",
    "Mendoza",
    "Misiones",
    "Neuquén",
    "Río Negro",
    "Salta",
    "San Juan",
    "San Luis",
    "Santa Cruz",
    "Santa Fe",
    "Santiago del Estero",
    "Tierra del Fuego",
    "Tucumán"
]


# ==============================================================
# TARJETA
# ==============================================================

class Tarjeta(QFrame):

    def __init__(self):

        super().__init__()

        self.setObjectName("tarjeta")

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum
        )


# ==============================================================
# VENTANA DETALLE DEL DÍA
# ==============================================================

class VentanaDetalleDia(QDialog):

    def __init__(
        self,
        padre,
        fecha,
        indice,
        diario,
        horario
    ):

        super().__init__(padre)

        self.setWindowTitle("Detalle del pronóstico")

        self.setWindowIcon(
            QIcon(ARCHIVO_ICONO)
        )

        self.resize(950, 700)

        # ======================================================
        # FUNCIÓN PARA OBTENER DATOS
        # ======================================================

        def obtener_dato(
            datos,
            clave,
            indice_dato,
            predeterminado=0
        ):

            valores = datos.get(
                clave,
                []
            )

            if (
                indice_dato < len(valores)
                and valores[indice_dato] is not None
            ):

                return valores[indice_dato]

            return predeterminado

        # ======================================================
        # DATOS DEL DÍA
        # ======================================================

        dia = padre.nombre_dia(
            fecha,
            indice
        )

        codigo = obtener_dato(
            diario,
            "weather_code",
            indice,
            0
        )

        maxima = obtener_dato(
            diario,
            "temperature_2m_max",
            indice,
            0
        )

        minima = obtener_dato(
            diario,
            "temperature_2m_min",
            indice,
            0
        )

        lluvia_probabilidad = obtener_dato(
            diario,
            "precipitation_probability_max",
            indice,
            0
        )

        lluvia = obtener_dato(
            diario,
            "precipitation_sum",
            indice,
            0
        )

        viento = obtener_dato(
            diario,
            "wind_speed_10m_max",
            indice,
            0
        )

        uv = obtener_dato(
            diario,
            "uv_index_max",
            indice,
            0
        )

        # ======================================================
        # CONTENEDOR PRINCIPAL
        # ======================================================

        layout_principal = QVBoxLayout(self)

        layout_principal.setContentsMargins(
            20,
            20,
            20,
            20
        )

        layout_principal.setSpacing(15)

        # ======================================================
        # ENCABEZADO
        # ======================================================

        titulo = QLabel(
            f"{padre.obtener_icono(codigo)} {dia}"
        )

        titulo.setObjectName(
            "tituloDetalle"
        )

        titulo.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout_principal.addWidget(titulo)

        fecha_label = QLabel(fecha)

        fecha_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        fecha_label.setObjectName(
            "fechaDetalle"
        )

        layout_principal.addWidget(fecha_label)

        # ======================================================
        # INFORMACIÓN GENERAL
        # ======================================================

        tarjeta_general = QFrame()

        tarjeta_general.setObjectName(
            "tarjetaDetalle"
        )

        grid = QGridLayout(
            tarjeta_general
        )

        datos = [
            (
                "🌡️ Máxima",
                f"{maxima:.0f} °C"
            ),
            (
                "❄️ Mínima",
                f"{minima:.0f} °C"
            ),
            (
                "🌧️ Prob. lluvia",
                f"{lluvia_probabilidad:.0f}%"
            ),
            (
                "💧 Precipitación",
                f"{lluvia:.1f} mm"
            ),
            (
                "💨 Viento máximo",
                f"{viento:.0f} km/h"
            ),
            (
                "☀️ Índice UV",
                f"{uv:.1f} — "
                f"{padre.nivel_uv(uv)}"
            )
        ]

        for posicion, (nombre, valor) in enumerate(datos):

            fila = posicion // 3

            columna = posicion % 3

            bloque = QWidget()

            layout_bloque = QVBoxLayout(
                bloque
            )

            label_nombre = QLabel(nombre)

            label_nombre.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label_valor = QLabel(valor)

            label_valor.setObjectName(
                "valorDetalle"
            )

            label_valor.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            layout_bloque.addWidget(
                label_nombre
            )

            layout_bloque.addWidget(
                label_valor
            )

            grid.addWidget(
                bloque,
                fila,
                columna
            )

        layout_principal.addWidget(
            tarjeta_general
        )

        # ======================================================
        # PRONÓSTICO POR HORA
        # ======================================================

        titulo_horas = QLabel(
            "🕐 Pronóstico por hora"
        )

        titulo_horas.setObjectName(
            "subtituloDetalle"
        )

        layout_principal.addWidget(
            titulo_horas
        )

        scroll_horas = QScrollArea()

        scroll_horas.setWidgetResizable(True)

        scroll_horas.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        contenido_horas = QWidget()

        grid_horas = QGridLayout(
            contenido_horas
        )

        grid_horas.setSpacing(10)

        # ======================================================
        # BUSCAR HORAS DEL DÍA
        # ======================================================

        indices_horas = []

        tiempos = horario.get(
            "time",
            []
        )

        for i, hora in enumerate(tiempos):

            if hora.startswith(fecha):

                indices_horas.append(i)

        # ======================================================
        # CREAR TARJETAS POR HORA
        # ======================================================

        for posicion, i in enumerate(indices_horas):

            hora = horario["time"][i]

            try:

                fecha_hora = datetime.fromisoformat(
                    hora
                )

                hora_texto = fecha_hora.strftime(
                    "%H:%M"
                )

            except Exception:

                hora_texto = hora

            temperatura = obtener_dato(
                horario,
                "temperature_2m",
                i,
                0
            )

            prob_lluvia = obtener_dato(
                horario,
                "precipitation_probability",
                i,
                0
            )

            precipitacion = obtener_dato(
                horario,
                "precipitation",
                i,
                0
            )

            viento_hora = obtener_dato(
                horario,
                "wind_speed_10m",
                i,
                0
            )

            uv_hora = obtener_dato(
                horario,
                "uv_index",
                i,
                0
            )

            tarjeta_hora = QFrame()

            tarjeta_hora.setObjectName(
                "tarjetaHoraDetalle"
            )

            layout_hora = QVBoxLayout(
                tarjeta_hora
            )

            label_hora = QLabel(
                f"🕐 {hora_texto}"
            )

            label_hora.setObjectName(
                "horaDetalle"
            )

            label_hora.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label_temp = QLabel(
                f"{temperatura:.0f} °C"
            )

            label_temp.setObjectName(
                "temperaturaHoraDetalle"
            )

            label_temp.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label_lluvia = QLabel(
                f"🌧️ {prob_lluvia:.0f}%"
            )

            label_lluvia.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label_precipitacion = QLabel(
                f"💧 {precipitacion:.1f} mm"
            )

            label_precipitacion.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label_viento = QLabel(
                f"💨 {viento_hora:.0f} km/h"
            )

            label_viento.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label_uv = QLabel(
                f"☀️ UV {uv_hora:.1f}"
            )

            label_uv.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            layout_hora.addWidget(
                label_hora
            )

            layout_hora.addWidget(
                label_temp
            )

            layout_hora.addWidget(
                label_lluvia
            )

            layout_hora.addWidget(
                label_precipitacion
            )

            layout_hora.addWidget(
                label_viento
            )

            layout_hora.addWidget(
                label_uv
            )

            grid_horas.addWidget(
                tarjeta_hora,
                posicion // 4,
                posicion % 4
            )

        scroll_horas.setWidget(
            contenido_horas
        )

        layout_principal.addWidget(
            scroll_horas,
            1
        )

        # ======================================================
        # BOTÓN CERRAR
        # ======================================================

        boton_cerrar = QPushButton(
            "Cerrar"
        )

        boton_cerrar.setMinimumHeight(
            40
        )

        boton_cerrar.clicked.connect(
            self.close
        )

        layout_principal.addWidget(
            boton_cerrar
        )

        # ======================================================
        # ESTILOS
        # ======================================================

        self.setStyleSheet("""
            QDialog {
                background-color: #f4f6f8;
            }

            #tituloDetalle {
                font-size: 28px;
                font-weight: bold;
                color: #202124;
            }

            #fechaDetalle {
                color: #6c757d;
                font-size: 16px;
            }

            #tarjetaDetalle {
                background-color: white;
                border: 1px solid #e1e5e9;
                border-radius: 12px;
                padding: 10px;
            }

            #valorDetalle {
                font-size: 22px;
                font-weight: bold;
            }

            #subtituloDetalle {
                font-size: 20px;
                font-weight: bold;
                color: #202124;
            }

            #tarjetaHoraDetalle {
                background-color: white;
                border: 1px solid #e1e5e9;
                border-radius: 10px;
                padding: 8px;
            }

            #horaDetalle {
                font-weight: bold;
                font-size: 15px;
            }

            #temperaturaHoraDetalle {
                font-size: 22px;
                font-weight: bold;
            }

            QPushButton {
                background-color: #ffffff;
                color: #202124;
                border: 1px solid #d9d9d9;
                border-radius: 8px;
                padding: 10px;
            }

            QPushButton:hover {
                background-color: #e9eef5;
            }
        """)


# ==============================================================
# VENTANA PRINCIPAL
# ==============================================================

class EstacionMeteorologica(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Estación Meteorológica"
        )

        # ======================================================
        # ICONO
        # ======================================================

        self.setWindowIcon(
            QIcon(ARCHIVO_ICONO)
        )

        self.nombre_ubicacion = ""

        self.provincia_actual = ""

        self.localidad_actual = ""

        self.latitud = None

        self.longitud = None

        self.resultados_ubicacion = []

        self.datos_clima = None

        self.ventana_detalle = None

        # ======================================================
        # TIMER DE BÚSQUEDA
        # ======================================================

        self.timer_busqueda = QTimer(self)

        self.timer_busqueda.setSingleShot(
            True
        )

        self.timer_busqueda.timeout.connect(
            self.buscar_localidades_automaticamente
        )

        # ======================================================
        # TIMER DEL RELOJ
        # ======================================================

        self.timer_reloj = QTimer(self)

        self.timer_reloj.timeout.connect(
            self.actualizar_pronostico_por_hora
        )

        self.timer_reloj.start(
            30000
        )

        self.ultima_hora = datetime.now().hour

        self.crear_interfaz()

        self.cargar_configuracion()

        if (
            self.latitud is not None
            and self.longitud is not None
        ):

            self.cargar_clima()

        else:

            self.mostrar_mensaje_inicial()

    # ==========================================================
    # BUSCAR ACTUALIZACIONES
    # ==========================================================

    def comprobar_actualizacion(self):

        try:

            respuesta = requests.get(
                URL_VERSION,
                timeout=10
            )

            respuesta.raise_for_status()

            datos = respuesta.json()

            nueva_version = datos.get(
                "version",
                ""
            )

            url_descarga = datos.get(
                "url",
                ""
            )

            notas = datos.get(
                "notas",
                "No hay información sobre los cambios."
            )

            if not nueva_version:

                QMessageBox.warning(
                    self,
                    "Actualización",
                    "No se pudo obtener la versión disponible."
                )

                return

            if nueva_version == VERSION:

                QMessageBox.information(
                    self,
                    "Actualización",
                    f"Ya tenés la última versión instalada.\n\n"
                    f"Versión actual: {VERSION}"
                )

                return

            respuesta_usuario = QMessageBox.question(
                self,
                "Nueva actualización",
                f"Hay una nueva versión disponible.\n\n"
                f"Versión actual: {VERSION}\n"
                f"Nueva versión: {nueva_version}\n\n"
                f"Cambios:\n{notas}\n\n"
                "¿Querés descargarla e instalarla?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if (
                respuesta_usuario
                != QMessageBox.StandardButton.Yes
            ):

                return

            if not url_descarga:

                QMessageBox.warning(
                    self,
                    "Actualización",
                    "La actualización no tiene "
                    "un enlace de descarga."
                )

                return

            self.descargar_actualizacion(
                url_descarga,
                nueva_version
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Error de actualización",
                f"No se pudo comprobar "
                f"la actualización.\n\n{e}"
            )

    # ==========================================================
    # DESCARGAR ACTUALIZACIÓN
    # ==========================================================

    def descargar_actualizacion(
        self,
        url_descarga,
        nueva_version
    ):

        try:

            carpeta_temp = tempfile.gettempdir()

            archivo_nuevo = os.path.join(
                carpeta_temp,
                "Estacion.Meteorologica_nueva.exe"
            )

            # --------------------------------------------------
            # DESCARGAR
            # --------------------------------------------------

            respuesta = requests.get(
                url_descarga,
                stream=True,
                timeout=60
            )

            respuesta.raise_for_status()

            with open(
                archivo_nuevo,
                "wb"
            ) as archivo:

                for bloque in respuesta.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if bloque:

                        archivo.write(
                            bloque
                        )

            # --------------------------------------------------
            # COMPROBAR ARCHIVO
            # --------------------------------------------------

            if not os.path.exists(
                archivo_nuevo
            ):

                raise Exception(
                    "No se pudo guardar "
                    "el archivo descargado."
                )

            tamaño = os.path.getsize(
                archivo_nuevo
            )

            if tamaño < 100000:

                raise Exception(
                    "El archivo descargado "
                    "parece estar incompleto."
                )

            # --------------------------------------------------
            # DETERMINAR EJECUTABLE ACTUAL
            # --------------------------------------------------

            if getattr(
                sys,
                "frozen",
                False
            ):

                archivo_actual = (
                    sys.executable
                )

            else:

                archivo_actual = os.path.abspath(
                    sys.argv[0]
                )

            # --------------------------------------------------
            # CREAR ARCHIVO BAT
            # --------------------------------------------------

            archivo_bat = os.path.join(
                carpeta_temp,
                "actualizar_estacion.bat"
            )

            contenido_bat = f'''@echo off
timeout /t 2 /nobreak >nul
copy /Y "{archivo_nuevo}" "{archivo_actual}" >nul
timeout /t 1 /nobreak >nul
start "" "{archivo_actual}"
del "%~f0"
'''

            with open(
                archivo_bat,
                "w",
                encoding="utf-8"
            ) as archivo:

                archivo.write(
                    contenido_bat
                )

            # --------------------------------------------------
            # AVISAR AL USUARIO
            # --------------------------------------------------

            QMessageBox.information(
                self,
                "Actualización",
                f"La versión {nueva_version} "
                f"se descargó correctamente.\n\n"
                "El programa se cerrará y "
                "se instalará la actualización."
            )

            # --------------------------------------------------
            # EJECUTAR ACTUALIZADOR
            # --------------------------------------------------

            subprocess.Popen(
                [
                    "cmd",
                    "/c",
                    archivo_bat
                ],
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                )
            )

            # --------------------------------------------------
            # CERRAR PROGRAMA
            # --------------------------------------------------

            QApplication.quit()

        except Exception as e:

            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo instalar "
                f"la actualización.\n\n{e}"
            )

    # ==========================================================
    # ACTUALIZAR PRONÓSTICO SEGÚN EL RELOJ
    # ==========================================================

    def actualizar_pronostico_por_hora(self):

        if (
            self.latitud is None
            or self.longitud is None
        ):

            return

        hora_actual = datetime.now().hour

        if hora_actual != self.ultima_hora:

            self.ultima_hora = hora_actual

            self.cargar_clima()

    # ==========================================================
    # INTERFAZ
    # ==========================================================

    def crear_interfaz(self):

        contenedor = QWidget()

        layout_principal = QHBoxLayout(
            contenedor
        )

        layout_principal.setContentsMargins(
            0,
            0,
            0,
            0
        )

        layout_principal.setSpacing(
            0
        )

        # ======================================================
        # BARRA LATERAL
        # ======================================================

        barra = QFrame()

        barra.setObjectName(
            "barraLateral"
        )

        barra.setFixedWidth(
            220
        )

        layout_barra = QVBoxLayout(
            barra
        )

        layout_barra.setContentsMargins(
            15,
            20,
            15,
            20
        )

        titulo = QLabel(
            "🌦️ CLIMA"
        )

        titulo.setObjectName(
            "tituloBarra"
        )

        titulo.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout_barra.addWidget(
            titulo
        )

        layout_barra.addSpacing(
            20
        )

        botones = [
            ("🏠 Hoy", "Hoy"),
            ("📅 Pronóstico", "Pronóstico"),
            ("🌧️ Lluvia", "Lluvia"),
            ("💨 Viento", "Viento"),
            ("☀️ UV", "UV"),
            ("🏍️ Movilidad", "Movilidad"),
            ("⚠️ Alertas", "Alertas"),
        ]

        for texto, nombre in botones:

            boton = QPushButton(
                texto
            )

            boton.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            boton.clicked.connect(
                lambda checked=False, n=nombre:
                self.ir_a_seccion(n)
            )

            layout_barra.addWidget(
                boton
            )

        # ======================================================
        # BOTÓN ACTUALIZACIONES
        # ======================================================

        boton_actualizacion = QPushButton(
            "🔄 Buscar actualización"
        )

        boton_actualizacion.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        # IMPORTANTE:
        # Ahora llama a la función correcta
        boton_actualizacion.clicked.connect(
            self.comprobar_actualizacion
        )

        layout_barra.addWidget(
            boton_actualizacion
        )

        layout_barra.addStretch()

        boton_radar = QPushButton(
            "📡 SMN Radar"
        )

        boton_radar.clicked.connect(
            lambda: webbrowser.open(
                "https://www.smn.gob.ar/radar"
            )
        )

        layout_barra.addWidget(
            boton_radar
        )

        boton_satelite = QPushButton(
            "🛰️ SMN Satélite"
        )

        boton_satelite.clicked.connect(
            lambda: webbrowser.open(
                "https://www.smn.gob.ar/satelite"
            )
        )

        layout_barra.addWidget(
            boton_satelite
        )

        # ======================================================
        # PARTE DERECHA
        # ======================================================

        zona_derecha = QWidget()

        layout_derecha = QVBoxLayout(
            zona_derecha
        )

        layout_derecha.setContentsMargins(
            15,
            15,
            15,
            15
        )

        layout_derecha.setSpacing(
            12
        )

        # ======================================================
        # BUSCADOR
        # ======================================================

        panel_busqueda = QFrame()

        panel_busqueda.setObjectName(
            "tarjeta"
        )

        layout_busqueda = QVBoxLayout(
            panel_busqueda
        )

        titulo_busqueda = QLabel(
            "📍 Buscar localidad"
        )

        titulo_busqueda.setObjectName(
            "tituloSeccion"
        )

        layout_busqueda.addWidget(
            titulo_busqueda
        )

        fila_busqueda = QHBoxLayout()

        fila_busqueda.setSpacing(
            8
        )

        # ======================================================
        # PROVINCIA
        # ======================================================

        self.lista_provincias = QComboBox()

        self.lista_provincias.setMinimumHeight(
            42
        )

        self.lista_provincias.setMinimumWidth(
            230
        )

        self.lista_provincias.addItem(
            "📍 Provincia"
        )

        self.lista_provincias.addItems(
            PROVINCIAS
        )

        self.lista_provincias.currentIndexChanged.connect(
            self.provincia_seleccionada
        )

        fila_busqueda.addWidget(
            self.lista_provincias
        )

        # ======================================================
        # LOCALIDAD
        # ======================================================

        self.entrada_ubicacion = QLineEdit()

        self.entrada_ubicacion.setPlaceholderText(
            "🏙️ Escribí una localidad..."
        )

        self.entrada_ubicacion.setMinimumHeight(
            42
        )

        self.entrada_ubicacion.setEnabled(
            False
        )

        self.entrada_ubicacion.textEdited.connect(
            self.programar_busqueda
        )

        self.entrada_ubicacion.returnPressed.connect(
            self.buscar_localidad
        )

        fila_busqueda.addWidget(
            self.entrada_ubicacion,
            1
        )

        # ======================================================
        # BOTÓN BUSCAR
        # ======================================================

        self.boton_buscar = QPushButton(
            "🔎 Buscar"
        )

        self.boton_buscar.setMinimumHeight(
            42
        )

        self.boton_buscar.setEnabled(
            False
        )

        self.boton_buscar.clicked.connect(
            self.buscar_localidad
        )

        fila_busqueda.addWidget(
            self.boton_buscar
        )

        # ======================================================
        # BOTÓN GUARDAR
        # ======================================================

        self.boton_guardar = QPushButton(
            "💾 Guardar"
        )

        self.boton_guardar.setMinimumHeight(
            42
        )

        self.boton_guardar.setEnabled(
            False
        )

        self.boton_guardar.clicked.connect(
            self.guardar_ubicacion
        )

        fila_busqueda.addWidget(
            self.boton_guardar
        )

        layout_busqueda.addLayout(
            fila_busqueda
        )

        # ======================================================
        # AUTOCOMPLETADO
        # ======================================================

        self.modelo_completador = (
            QStringListModel()
        )

        self.completador = QCompleter(
            self.modelo_completador,
            self.entrada_ubicacion
        )

        self.completador.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )

        self.completador.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )

        self.completador.setMaxVisibleItems(
            8
        )

        self.completador.popup().setMinimumWidth(
            350
        )

        self.entrada_ubicacion.setCompleter(
            self.completador
        )

        self.completador.activated.connect(
            self.seleccionar_sugerencia
        )

        # ======================================================
        # ESTADO
        # ======================================================

        self.label_estado = QLabel(
            "Seleccioná una provincia."
        )

        self.label_estado.setObjectName(
            "estado"
        )

        layout_busqueda.addWidget(
            self.label_estado
        )

        # ======================================================
        # COORDENADAS
        # ======================================================

        self.label_coordenadas = QLabel(
            ""
        )

        self.label_coordenadas.setObjectName(
            "coordenadas"
        )

        layout_busqueda.addWidget(
            self.label_coordenadas
        )

        layout_derecha.addWidget(
            panel_busqueda
        )

        # ======================================================
        # ÁREA DE CONTENIDO
        # ======================================================

        self.scroll = QScrollArea()

        self.scroll.setWidgetResizable(
            True
        )

        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.contenido = QWidget()

        self.layout_contenido = QVBoxLayout(
            self.contenido
        )

        self.layout_contenido.setContentsMargins(
            5,
            5,
            5,
            20
        )

        self.layout_contenido.setSpacing(
            15
        )

        self.scroll.setWidget(
            self.contenido
        )

        layout_derecha.addWidget(
            self.scroll,
            1
        )

        layout_principal.addWidget(
            barra
        )

        layout_principal.addWidget(
            zona_derecha,
            1
        )

        self.setCentralWidget(
            contenedor
        )

        self.aplicar_estilos()

    # ==========================================================
    # PROVINCIA SELECCIONADA
    # ==========================================================

    def provincia_seleccionada(
        self,
        indice
    ):

        self.timer_busqueda.stop()

        self.modelo_completador.setStringList(
            []
        )

        self.completador.popup().hide()

        self.entrada_ubicacion.clear()

        self.resultados_ubicacion = []

        self.boton_guardar.setEnabled(
            False
        )

        if indice == 0:

            self.entrada_ubicacion.setEnabled(
                False
            )

            self.boton_buscar.setEnabled(
                False
            )

            self.label_estado.setText(
                "Seleccioná una provincia."
            )

            return

        self.provincia_actual = (
            self.lista_provincias.currentText()
        )

        self.entrada_ubicacion.setEnabled(
            True
        )

        self.boton_buscar.setEnabled(
            True
        )

        self.label_estado.setText(
            f"Escribí una localidad de "
            f"{self.provincia_actual}."
        )

        self.entrada_ubicacion.setFocus()

    # ==========================================================
    # PROGRAMAR BÚSQUEDA
    # ==========================================================

    def programar_busqueda(
        self,
        texto
    ):

        self.timer_busqueda.stop()

        texto = texto.strip()

        if len(texto) < 2:

            self.modelo_completador.setStringList(
                []
            )

            self.completador.popup().hide()

            self.label_estado.setText(
                "Escribí al menos 2 letras..."
            )

            return

        self.label_estado.setText(
            "🔎 Buscando localidades..."
        )

        self.timer_busqueda.start(
            500
        )

    # ==========================================================
    # BUSCAR LOCALIDADES AUTOMÁTICAMENTE
    # ==========================================================

    def buscar_localidades_automaticamente(
        self
    ):

        texto = (
            self.entrada_ubicacion
            .text()
            .strip()
        )

        provincia = (
            self.lista_provincias.currentText()
        )

        if (
            len(texto) < 2
            or self.lista_provincias.currentIndex() == 0
        ):

            return

        try:

            url = (
                "https://geocoding-api.open-meteo.com/v1/search"
            )

            query_busqueda = (
                f"{texto}, {provincia}"
            )

            parametros = {
                "name": query_busqueda,
                "count": 20,
                "language": "es",
                "format": "json"
            }

            respuesta = requests.get(
                url,
                params=parametros,
                timeout=10
            )

            respuesta.raise_for_status()

            datos = respuesta.json()

            resultados = datos.get(
                "results",
                []
            )

            if not resultados:

                parametros["name"] = texto

                respuesta = requests.get(
                    url,
                    params=parametros,
                    timeout=10
                )

                datos = respuesta.json()

                resultados = datos.get(
                    "results",
                    []
                )

            resultados_filtrados = []

            for resultado in resultados:

                if (
                    resultado.get(
                        "country",
                        ""
                    )
                    != "Argentina"
                ):

                    continue

                provincia_resultado = (
                    resultado.get(
                        "admin1",
                        ""
                    )
                )

                if self.provincia_coincide(
                    provincia_resultado,
                    provincia
                ):

                    resultados_filtrados.append(
                        resultado
                    )

            self.resultados_ubicacion = (
                resultados_filtrados
            )

            sugerencias = []

            for resultado in resultados_filtrados:

                nombre = resultado.get(
                    "name",
                    ""
                )

                if nombre:

                    sugerencias.append(
                        nombre
                    )

            sugerencias = list(
                dict.fromkeys(
                    sugerencias
                )
            )

            self.modelo_completador.setStringList(
                sugerencias
            )

            if sugerencias:

                self.label_estado.setText(
                    f"📍 {len(sugerencias)} "
                    f"localidades encontradas"
                )

                self.completador.setCompletionPrefix(
                    texto
                )

                self.completador.complete()

            else:

                self.label_estado.setText(
                    f"❌ No se encontró "
                    f"'{texto}' en "
                    f"{provincia}."
                )

                self.completador.popup().hide()

        except Exception as e:

            print(
                "Error de búsqueda:",
                e
            )

            self.label_estado.setText(
                "⚠️ No se pudo realizar "
                "la búsqueda."
            )

    # ==========================================================
    # COMPARAR PROVINCIA
    # ==========================================================

    def provincia_coincide(
        self,
        provincia_resultado,
        provincia_seleccionada
    ):

        if not provincia_resultado:

            return True

        def normalizar(
            texto
        ):

            texto = unicodedata.normalize(
                "NFD",
                texto
            )

            texto = "".join(
                c
                for c in texto
                if unicodedata.category(c)
                != "Mn"
            )

            return (
                texto
                .lower()
                .replace(
                    "province",
                    ""
                )
                .replace(
                    "provincia",
                    ""
                )
                .strip()
            )

        res = normalizar(
            provincia_resultado
        )

        sel = normalizar(
            provincia_seleccionada
        )

        if "buenos aires" in sel:

            return (
                "buenos aires"
                in res
            )

        return (
            sel in res
            or res in sel
        )

    # ==========================================================
    # SELECCIONAR SUGERENCIA
    # ==========================================================

    def seleccionar_sugerencia(
        self,
        nombre_localidad
    ):

        self.timer_busqueda.stop()

        for resultado in (
            self.resultados_ubicacion
        ):

            nombre = resultado.get(
                "name",
                ""
            )

            if nombre == nombre_localidad:

                self.seleccionar_resultado(
                    self.resultados_ubicacion.index(
                        resultado
                    )
                )

                return

    # ==========================================================
    # BUSCAR LOCALIDAD
    # ==========================================================

    def buscar_localidad(
        self
    ):

        if (
            self.lista_provincias.currentIndex()
            == 0
        ):

            QMessageBox.warning(
                self,
                "Provincia",
                "Primero seleccioná una provincia."
            )

            return

        texto = (
            self.entrada_ubicacion
            .text()
            .strip()
        )

        if not texto:

            QMessageBox.warning(
                self,
                "Buscar localidad",
                "Escribí una localidad."
            )

            return

        for resultado in (
            self.resultados_ubicacion
        ):

            if (
                resultado.get(
                    "name",
                    ""
                ).lower()
                == texto.lower()
            ):

                indice = (
                    self.resultados_ubicacion.index(
                        resultado
                    )
                )

                self.seleccionar_resultado(
                    indice
                )

                return

        self.label_estado.setText(
            "🔎 Buscando localidad..."
        )

        QApplication.processEvents()

        try:

            url = (
                "https://geocoding-api.open-meteo.com/v1/search"
            )

            provincia = (
                self.lista_provincias.currentText()
            )

            query_busqueda = (
                f"{texto}, {provincia}"
            )

            parametros = {
                "name": query_busqueda,
                "count": 20,
                "language": "es",
                "format": "json"
            }

            respuesta = requests.get(
                url,
                params=parametros,
                timeout=10
            )

            respuesta.raise_for_status()

            datos = respuesta.json()

            resultados = datos.get(
                "results",
                []
            )

            if not resultados:

                parametros["name"] = texto

                respuesta = requests.get(
                    url,
                    params=parametros,
                    timeout=10
                )

                datos = respuesta.json()

                resultados = datos.get(
                    "results",
                    []
                )

            resultados_filtrados = []

            for resultado in resultados:

                if (
                    resultado.get(
                        "country",
                        ""
                    )
                    != "Argentina"
                ):

                    continue

                provincia_resultado = (
                    resultado.get(
                        "admin1",
                        ""
                    )
                )

                if self.provincia_coincide(
                    provincia_resultado,
                    provincia
                ):

                    resultados_filtrados.append(
                        resultado
                    )

            if not resultados_filtrados:

                self.label_estado.setText(
                    f"❌ No se encontró "
                    f"'{texto}' en "
                    f"{provincia}."
                )

                return

            self.resultados_ubicacion = (
                resultados_filtrados
            )

            self.seleccionar_resultado(
                0
            )

        except Exception as e:

            self.label_estado.setText(
                "❌ Error al buscar localidad."
            )

            QMessageBox.warning(
                self,
                "Error",
                f"No se pudo buscar "
                f"la localidad.\n\n{e}"
            )

    # ==========================================================
    # CONSTRUIR NOMBRE
    # ==========================================================

    def construir_nombre(
        self,
        resultado
    ):

        partes = []

        nombre = resultado.get(
            "name"
        )

        admin1 = resultado.get(
            "admin1"
        )

        pais = resultado.get(
            "country"
        )

        if nombre:

            partes.append(
                nombre
            )

        if (
            admin1
            and admin1 != nombre
        ):

            partes.append(
                admin1
            )

        if pais:

            partes.append(
                pais
            )

        return ", ".join(
            partes
        )

    # ==========================================================
    # SELECCIONAR LOCALIDAD
    # ==========================================================

    def seleccionar_resultado(
        self,
        indice
    ):

        if not self.resultados_ubicacion:

            return

        if (
            indice < 0
            or indice >= len(
                self.resultados_ubicacion
            )
        ):

            return

        resultado = (
            self.resultados_ubicacion[
                indice
            ]
        )

        self.localidad_actual = (
            resultado.get(
                "name",
                ""
            )
        )

        self.provincia_actual = (
            resultado.get(
                "admin1",
                self.lista_provincias.currentText()
            )
        )

        self.nombre_ubicacion = (
            self.construir_nombre(
                resultado
            )
        )

        self.latitud = (
            resultado.get(
                "latitude"
            )
        )

        self.longitud = (
            resultado.get(
                "longitude"
            )
        )

        self.entrada_ubicacion.setText(
            self.localidad_actual
        )

        self.label_coordenadas.setText(
            f"📍 Coordenadas: "
            f"{self.latitud:.4f}, "
            f"{self.longitud:.4f}"
        )

        self.label_estado.setText(
            f"✅ Localidad seleccionada: "
            f"{self.nombre_ubicacion}"
        )

        self.boton_guardar.setEnabled(
            True
        )

        self.completador.popup().hide()

        self.cargar_clima()

    # ==========================================================
    # GUARDAR LOCALIDAD
    # ==========================================================

    def guardar_ubicacion(
        self
    ):

        if (
            self.latitud is None
            or self.longitud is None
        ):

            return

        configuracion = {

            "nombre":
                self.nombre_ubicacion,

            "provincia":
                self.provincia_actual,

            "localidad":
                self.localidad_actual,

            "latitud":
                self.latitud,

            "longitud":
                self.longitud
        }

        try:

            with open(
                ARCHIVO_CONFIG,
                "w",
                encoding="utf-8"
            ) as archivo:

                json.dump(
                    configuracion,
                    archivo,
                    ensure_ascii=False,
                    indent=4
                )

            self.label_estado.setText(
                "💾 Ubicación guardada correctamente."
            )

        except Exception as e:

            QMessageBox.warning(
                self,
                "Error",
                f"No se pudo guardar "
                f"la ubicación.\n\n{e}"
            )

    # ==========================================================
    # CARGAR CONFIGURACIÓN
    # ==========================================================

    def cargar_configuracion(
        self
    ):

        if not os.path.exists(
            ARCHIVO_CONFIG
        ):

            return

        try:

            with open(
                ARCHIVO_CONFIG,
                "r",
                encoding="utf-8"
            ) as archivo:

                configuracion = json.load(
                    archivo
                )

            self.nombre_ubicacion = (
                configuracion.get(
                    "nombre",
                    ""
                )
            )

            self.provincia_actual = (
                configuracion.get(
                    "provincia",
                    ""
                )
            )

            self.localidad_actual = (
                configuracion.get(
                    "localidad",
                    ""
                )
            )

            self.latitud = (
                configuracion.get(
                    "latitud"
                )
            )

            self.longitud = (
                configuracion.get(
                    "longitud"
                )
            )

            if self.provincia_actual:

                indice = (
                    self.lista_provincias.findText(
                        self.provincia_actual
                    )
                )

                if indice >= 0:

                    self.lista_provincias.blockSignals(
                        True
                    )

                    self.lista_provincias.setCurrentIndex(
                        indice
                    )

                    self.lista_provincias.blockSignals(
                        False
                    )

                self.entrada_ubicacion.setEnabled(
                    True
                )

                self.boton_buscar.setEnabled(
                    True
                )

            if self.localidad_actual:

                self.entrada_ubicacion.setText(
                    self.localidad_actual
                )

            if (
                self.latitud is not None
                and self.longitud is not None
            ):

                self.label_coordenadas.setText(
                    f"📍 Coordenadas: "
                    f"{self.latitud:.4f}, "
                    f"{self.longitud:.4f}"
                )

                self.label_estado.setText(
                    f"💾 Ubicación guardada: "
                    f"{self.nombre_ubicacion}"
                )

                self.boton_guardar.setEnabled(
                    True
                )

        except Exception as e:

            print(
                "Error cargando configuración:",
                e
            )

    # ==========================================================
    # CARGAR CLIMA
    # ==========================================================

    def cargar_clima(
        self
    ):

        if (
            self.latitud is None
            or self.longitud is None
        ):

            return

        try:

            url = (
                "https://api.open-meteo.com/v1/forecast"
            )

            parametros = {

                "latitude":
                    self.latitud,

                "longitude":
                    self.longitud,

                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "apparent_temperature,"
                    "precipitation,"
                    "weather_code,"
                    "wind_speed_10m,"
                    "wind_direction_10m"
                ),

                "hourly": (
                    "temperature_2m,"
                    "precipitation_probability,"
                    "precipitation,"
                    "wind_speed_10m,"
                    "uv_index"
                ),

                "daily": (
                    "weather_code,"
                    "temperature_2m_max,"
                    "temperature_2m_min,"
                    "precipitation_sum,"
                    "precipitation_probability_max,"
                    "wind_speed_10m_max,"
                    "uv_index_max"
                ),

                "timezone":
                    "auto",

                "forecast_days":
                    7
            }

            respuesta = requests.get(
                url,
                params=parametros,
                timeout=15
            )

            respuesta.raise_for_status()

            datos = respuesta.json()

            self.datos_clima = datos

            self.mostrar_clima(
                datos
            )

        except Exception as e:

            self.mostrar_error(
                str(e)
            )

    # ==========================================================
    # NOMBRE DEL DÍA
    # ==========================================================

    def nombre_dia(
        self,
        fecha_texto,
        indice=0
    ):

        try:

            fecha = datetime.strptime(
                fecha_texto,
                "%Y-%m-%d"
            )

            if indice == 0:

                return "Hoy"

            return DIAS_SEMANA[
                fecha.weekday()
            ]

        except Exception:

            return fecha_texto

    # ==========================================================
    # MOSTRAR CLIMA
    # ==========================================================

    def mostrar_clima(
        self,
        datos
    ):

        self.limpiar_contenido()

        actual = datos["current"]

        diario = datos["daily"]

        horario = datos["hourly"]

        # ======================================================
        # INFORMACIÓN
        # ======================================================

        tarjeta_info = Tarjeta()

        layout_info = QVBoxLayout(
            tarjeta_info
        )

        titulo = QLabel(
            "📍 Información"
        )

        titulo.setObjectName(
            "tituloSeccion"
        )

        layout_info.addWidget(
            titulo
        )

        nombre = QLabel(
            self.nombre_ubicacion
        )

        nombre.setObjectName(
            "ubicacion"
        )

        nombre.setWordWrap(
            True
        )

        layout_info.addWidget(
            nombre
        )

        coordenadas = QLabel(
            f"Latitud: "
            f"{self.latitud:.4f} | "
            f"Longitud: "
            f"{self.longitud:.4f}"
        )

        coordenadas.setObjectName(
            "coordenadas"
        )

        layout_info.addWidget(
            coordenadas
        )

        self.layout_contenido.addWidget(
            tarjeta_info
        )

        # ======================================================
        # HOY
        # ======================================================

        tarjeta_hoy = Tarjeta()

        layout_hoy = QVBoxLayout(
            tarjeta_hoy
        )

        titulo_hoy = QLabel(
            "🌤️ Tiempo de hoy"
        )

        titulo_hoy.setObjectName(
            "tituloSeccion"
        )

        layout_hoy.addWidget(
            titulo_hoy
        )

        icono = QLabel(
            self.obtener_icono(
                actual["weather_code"]
            )
        )

        icono.setObjectName(
            "iconoGrande"
        )

        icono.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout_hoy.addWidget(
            icono
        )

        temperatura = QLabel(
            f"{actual['temperature_2m']:.0f} °C"
        )

        temperatura.setObjectName(
            "temperatura"
        )

        temperatura.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout_hoy.addWidget(
            temperatura
        )

        minima_hoy = (
            diario["temperature_2m_min"][0]
        )

        maxima_hoy = (
            diario["temperature_2m_max"][0]
        )

        fila_temperaturas = QHBoxLayout()

        tarjeta_min = Tarjeta()

        layout_min = QVBoxLayout(
            tarjeta_min
        )

        texto_min = QLabel(
            "❄️ Mínima"
        )

        texto_min.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        valor_min = QLabel(
            f"{minima_hoy:.0f} °C"
        )

        valor_min.setObjectName(
            "valorDato"
        )

        valor_min.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout_min.addWidget(
            texto_min
        )

        layout_min.addWidget(
            valor_min
        )

        tarjeta_max = Tarjeta()

        layout_max = QVBoxLayout(
            tarjeta_max
        )

        texto_max = QLabel(
            "🔥 Máxima"
        )

        texto_max.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        valor_max = QLabel(
            f"{maxima_hoy:.0f} °C"
        )

        valor_max.setObjectName(
            "valorDato"
        )

        valor_max.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout_max.addWidget(
            texto_max
        )

        layout_max.addWidget(
            valor_max
        )

        fila_temperaturas.addWidget(
            tarjeta_min
        )

        fila_temperaturas.addWidget(
            tarjeta_max
        )

        layout_hoy.addLayout(
            fila_temperaturas
        )

        # ======================================================
        # DATOS ACTUALES
        # ======================================================

        datos_hoy = QGridLayout()

        datos_rapidos = [

            (
                "🌡️ Sensación",
                f"{actual['apparent_temperature']:.0f} °C"
            ),

            (
                "💧 Humedad",
                f"{actual['relative_humidity_2m']:.0f}%"
            ),

            (
                "💨 Viento",
                f"{actual['wind_speed_10m']:.0f} km/h"
            ),

            (
                "🌧️ Precipitación",
                f"{actual['precipitation']:.1f} mm"
            )
        ]

        for i, (
            nombre_dato,
            valor
        ) in enumerate(
            datos_rapidos
        ):

            tarjeta = Tarjeta()

            layout = QVBoxLayout(
                tarjeta
            )

            label_nombre = QLabel(
                nombre_dato
            )

            label_nombre.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label_valor = QLabel(
                valor
            )

            label_valor.setObjectName(
                "valorDato"
            )

            label_valor.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            layout.addWidget(
                label_nombre
            )

            layout.addWidget(
                label_valor
            )

            datos_hoy.addWidget(
                tarjeta,
                i // 4,
                i % 4
            )

        layout_hoy.addLayout(
            datos_hoy
        )

        self.layout_contenido.addWidget(
            tarjeta_hoy
        )

        # ======================================================
        # PRONÓSTICO 7 DÍAS
        # ======================================================

        tarjeta_pronostico = Tarjeta()

        layout_pronostico = QVBoxLayout(
            tarjeta_pronostico
        )

        titulo_pronostico = QLabel(
            "📅 Pronóstico de 7 días"
        )

        titulo_pronostico.setObjectName(
            "tituloSeccion"
        )

        layout_pronostico.addWidget(
            titulo_pronostico
        )

        aviso = QLabel(
            "👆 Hacé clic en un día para "
            "ver información detallada"
        )

        aviso.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        aviso.setStyleSheet(
            "color: #6c757d;"
        )

        layout_pronostico.addWidget(
            aviso
        )

        grid_pronostico = QGridLayout()

        cantidad_dias = min(
            7,
            len(
                diario.get(
                    "time",
                    []
                )
            )
        )

        for i in range(
            cantidad_dias
        ):

            tarjeta = Tarjeta()

            tarjeta.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            def hacer_click(
                evento,
                indice=i
            ):

                self.mostrar_detalle_dia(
                    indice,
                    diario,
                    horario
                )

            tarjeta.mousePressEvent = (
                hacer_click
            )

            layout = QVBoxLayout(
                tarjeta
            )

            dia = QLabel(
                self.nombre_dia(
                    diario["time"][i],
                    i
                )
            )

            dia.setObjectName(
                "diaPronostico"
            )

            dia.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            icono = QLabel(
                self.obtener_icono(
                    diario["weather_code"][i]
                )
            )

            icono.setObjectName(
                "iconoMediano"
            )

            icono.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            maxima = QLabel(
                f"🔥 Máx: "
                f"{diario['temperature_2m_max'][i]:.0f} °C"
            )

            maxima.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            minima = QLabel(
                f"❄️ Mín: "
                f"{diario['temperature_2m_min'][i]:.0f} °C"
            )

            minima.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            lluvia = QLabel(
                f"🌧️ "
                f"{diario['precipitation_probability_max'][i]:.0f}%"
            )

            lluvia.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            layout.addWidget(
                dia
            )

            layout.addWidget(
                icono
            )

            layout.addWidget(
                maxima
            )

            layout.addWidget(
                minima
            )

            layout.addWidget(
                lluvia
            )

            grid_pronostico.addWidget(
                tarjeta,
                i // 4,
                i % 4
            )

        layout_pronostico.addLayout(
            grid_pronostico
        )

        self.layout_contenido.addWidget(
            tarjeta_pronostico
        )

        # ======================================================
        # PRONÓSTICO POR HORA
        # ======================================================

        tarjeta_horas = Tarjeta()

        layout_horas = QVBoxLayout(
            tarjeta_horas
        )

        titulo_horas = QLabel(
            "🕐 Pronóstico por hora"
        )

        titulo_horas.setObjectName(
            "tituloSeccion"
        )

        layout_horas.addWidget(
            titulo_horas
        )

        grid_horas = QGridLayout()

        hora_actual = datetime.now()

        indice_inicio = 0

        for i, hora in enumerate(
            horario["time"]
        ):

            try:

                fecha_hora = datetime.fromisoformat(
                    hora
                )

                if (
                    fecha_hora.hour
                    >= hora_actual.hour
                ):

                    indice_inicio = i

                    break

            except Exception:

                pass

        indices_horas = range(
            indice_inicio,
            min(
                indice_inicio + 12,
                len(
                    horario["time"]
                )
            )
        )

        for posicion, i in enumerate(
            indices_horas
        ):

            hora = horario["time"][i]

            try:

                fecha_hora = datetime.fromisoformat(
                    hora
                )

                hora_formateada = (
                    fecha_hora.strftime(
                        "%H:%M"
                    )
                )

            except Exception:

                hora_formateada = hora

            tarjeta = Tarjeta()

            layout = QVBoxLayout(
                tarjeta
            )

            label_hora = QLabel(
                hora_formateada
            )

            label_hora.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            temp = QLabel(
                f"{horario['temperature_2m'][i]:.0f} °C"
            )

            temp.setObjectName(
                "valorDato"
            )

            temp.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            lluvia = QLabel(
                f"🌧️ "
                f"{horario['precipitation_probability'][i]:.0f}%"
            )

            lluvia.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            layout.addWidget(
                label_hora
            )

            layout.addWidget(
                temp
            )

            layout.addWidget(
                lluvia
            )

            grid_horas.addWidget(
                tarjeta,
                posicion // 6,
                posicion % 6
            )

        layout_horas.addLayout(
            grid_horas
        )

        self.layout_contenido.addWidget(
            tarjeta_horas
        )

        # ======================================================
        # LLUVIA
        # ======================================================

        tarjeta_lluvia = Tarjeta()

        layout_lluvia = QVBoxLayout(
            tarjeta_lluvia
        )

        titulo_lluvia = QLabel(
            "🌧️ Información de lluvia"
        )

        titulo_lluvia.setObjectName(
            "tituloSeccion"
        )

        layout_lluvia.addWidget(
            titulo_lluvia
        )

        for i in range(
            cantidad_dias
        ):

            dia = self.nombre_dia(
                diario["time"][i],
                i
            )

            texto = QLabel(
                f"🌧️ {dia} — "
                f"Probabilidad: "
                f"{diario['precipitation_probability_max'][i]:.0f}% | "
                f"Acumulado: "
                f"{diario['precipitation_sum'][i]:.1f} mm"
            )

            texto.setWordWrap(
                True
            )

            layout_lluvia.addWidget(
                texto
            )

        self.layout_contenido.addWidget(
            tarjeta_lluvia
        )

        # ======================================================
        # VIENTO
        # ======================================================

        tarjeta_viento = Tarjeta()

        layout_viento = QVBoxLayout(
            tarjeta_viento
        )

        titulo_viento = QLabel(
            "💨 Información de viento"
        )

        titulo_viento.setObjectName(
            "tituloSeccion"
        )

        layout_viento.addWidget(
            titulo_viento
        )

        for i in range(
            cantidad_dias
        ):

            dia = self.nombre_dia(
                diario["time"][i],
                i
            )

            texto = QLabel(
                f"💨 {dia} — "
                f"Viento máximo: "
                f"{diario['wind_speed_10m_max'][i]:.0f} km/h"
            )

            texto.setWordWrap(
                True
            )

            layout_viento.addWidget(
                texto
            )

        self.layout_contenido.addWidget(
            tarjeta_viento
        )

        # ======================================================
        # UV
        # ======================================================

        tarjeta_uv = Tarjeta()

        layout_uv = QVBoxLayout(
            tarjeta_uv
        )

        titulo_uv = QLabel(
            "☀️ Índice UV"
        )

        titulo_uv.setObjectName(
            "tituloSeccion"
        )

        layout_uv.addWidget(
            titulo_uv
        )

        for i in range(
            cantidad_dias
        ):

            dia = self.nombre_dia(
                diario["time"][i],
                i
            )

            uv = diario[
                "uv_index_max"
            ][i]

            texto = QLabel(
                f"☀️ {dia} — "
                f"UV máximo: {uv:.1f} — "
                f"{self.nivel_uv(uv)}"
            )

            texto.setWordWrap(
                True
            )

            layout_uv.addWidget(
                texto
            )

        self.layout_contenido.addWidget(
            tarjeta_uv
        )

        # ======================================================
        # MOVILIDAD
        # ======================================================

        tarjeta_movilidad = Tarjeta()

        layout_movilidad = QVBoxLayout(
            tarjeta_movilidad
        )

        titulo_movilidad = QLabel(
            "🚦 Condiciones de movilidad"
        )

        titulo_movilidad.setObjectName(
            "tituloSeccion"
        )

        layout_movilidad.addWidget(
            titulo_movilidad
        )

        grid_movilidad = QGridLayout()

        movilidad = [

            (
                "🏍️ Moto",
                self.condicion_moto(
                    actual,
                    diario
                )
            ),

            (
                "🚶 Caminar",
                self.condicion_caminando(
                    actual,
                    diario
                )
            ),

            (
                "🚗 Auto",
                self.condicion_auto(
                    actual,
                    diario
                )
            )
        ]

        for i, (
            nombre,
            texto
        ) in enumerate(
            movilidad
        ):

            tarjeta = (
                self.crear_tarjeta_movilidad(
                    nombre,
                    texto
                )
            )

            grid_movilidad.addWidget(
                tarjeta,
                0,
                i
            )

        layout_movilidad.addLayout(
            grid_movilidad
        )

        self.layout_contenido.addWidget(
            tarjeta_movilidad
        )

        # ======================================================
        # ALERTAS
        # ======================================================

        tarjeta_alertas = Tarjeta()

        layout_alertas = QVBoxLayout(
            tarjeta_alertas
        )

        titulo_alertas = QLabel(
            "⚠️ Alertas y recomendaciones"
        )

        titulo_alertas.setObjectName(
            "tituloSeccion"
        )

        layout_alertas.addWidget(
            titulo_alertas
        )

        alertas = self.generar_alertas(
            actual,
            diario
        )

        for alerta in alertas:

            label = QLabel(
                alerta
            )

            label.setWordWrap(
                True
            )

            layout_alertas.addWidget(
                label
            )

        self.layout_contenido.addWidget(
            tarjeta_alertas
        )

        # ======================================================
        # ACTUALIZACIÓN
        # ======================================================

        actualizacion = QLabel(
            f"Última actualización: "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

        actualizacion.setObjectName(
            "actualizacion"
        )

        actualizacion.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.layout_contenido.addWidget(
            actualizacion
        )

    # ==========================================================
    # MOSTRAR DETALLE DE UN DÍA
    # ==========================================================

    def mostrar_detalle_dia(
        self,
        indice,
        diario,
        horario
    ):

        fecha = diario[
            "time"
        ][indice]

        self.ventana_detalle = (
            VentanaDetalleDia(
                self,
                fecha,
                indice,
                diario,
                horario
            )
        )

        self.ventana_detalle.show()

        self.ventana_detalle.raise_()

        self.ventana_detalle.activateWindow()

    # ==========================================================
    # CREAR TARJETA MOVILIDAD
    # ==========================================================

    def crear_tarjeta_movilidad(
        self,
        nombre,
        texto
    ):

        tarjeta = Tarjeta()

        layout = QVBoxLayout(
            tarjeta
        )

        titulo = QLabel(
            nombre
        )

        titulo.setObjectName(
            "diaPronostico"
        )

        titulo.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        descripcion = QLabel(
            texto
        )

        descripcion.setWordWrap(
            True
        )

        descripcion.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            titulo
        )

        layout.addWidget(
            descripcion
        )

        return tarjeta

    # ==========================================================
    # ICONOS METEOROLÓGICOS
    # ==========================================================

    def obtener_icono(
        self,
        codigo
    ):

        iconos = {

            0: "☀️",
            1: "🌤️",
            2: "⛅",
            3: "☁️",

            45: "🌫️",
            48: "🌫️",

            51: "🌦️",
            53: "🌦️",
            55: "🌧️",

            56: "🌧️",
            57: "🌧️",

            61: "🌧️",
            63: "🌧️",
            65: "🌧️",

            66: "🌧️",
            67: "🌧️",

            71: "🌨️",
            73: "🌨️",
            75: "❄️",
            77: "❄️",

            80: "🌦️",
            81: "🌧️",
            82: "⛈️",

            85: "🌨️",
            86: "❄️",

            95: "⛈️",
            96: "⛈️",
            99: "⛈️"
        }

        return iconos.get(
            codigo,
            "🌤️"
        )

    # ==========================================================
    # NIVEL UV
    # ==========================================================

    def nivel_uv(
        self,
        uv
    ):

        if uv < 3:

            return "Bajo"

        elif uv < 6:

            return "Moderado"

        elif uv < 8:

            return "Alto"

        elif uv < 11:

            return "Muy alto"

        else:

            return "Extremo"

    # ==========================================================
    # CONDICIÓN MOTO
    # ==========================================================

    def condicion_moto(
        self,
        actual,
        diario
    ):

        lluvia = (
            diario[
                "precipitation_probability_max"
            ][0]
        )

        viento = (
            diario[
                "wind_speed_10m_max"
            ][0]
        )

        if lluvia >= 70:

            return (
                "⚠️ Precaución. "
                "Alta probabilidad de lluvia."
            )

        if viento >= 50:

            return (
                "⚠️ Precaución. "
                "Viento fuerte."
            )

        if lluvia >= 40:

            return (
                "🟡 Condiciones regulares. "
                "Posibilidad de lluvia."
            )

        return (
            "🟢 Buenas condiciones "
            "para circular."
        )

    # ==========================================================
    # CONDICIÓN AUTO
    # ==========================================================

    def condicion_auto(
        self,
        actual,
        diario
    ):

        lluvia = (
            diario[
                "precipitation_probability_max"
            ][0]
        )

        if lluvia >= 70:

            return (
                "⚠️ Conducir con precaución "
                "por posible lluvia."
            )

        return (
            "🟢 Buenas condiciones "
            "para conducir."
        )

    # ==========================================================
    # CONDICIÓN CAMINANDO
    # ==========================================================

    def condicion_caminando(
        self,
        actual,
        diario
    ):

        lluvia = (
            diario[
                "precipitation_probability_max"
            ][0]
        )

        uv = (
            diario[
                "uv_index_max"
            ][0]
        )

        if lluvia >= 70:

            return (
                "🌧️ No es recomendable "
                "caminar sin protección."
            )

        if uv >= 8:

            return (
                "☀️ UV muy alto. "
                "Usar protección solar."
            )

        return (
            "🟢 Buenas condiciones "
            "para caminar."
        )

    # ==========================================================
    # ALERTAS
    # ==========================================================

    def generar_alertas(
        self,
        actual,
        diario
    ):

        alertas = []

        lluvia = (
            diario[
                "precipitation_probability_max"
            ][0]
        )

        viento = (
            diario[
                "wind_speed_10m_max"
            ][0]
        )

        uv = (
            diario[
                "uv_index_max"
            ][0]
        )

        if lluvia >= 70:

            alertas.append(
                "🌧️ Alta probabilidad de lluvia."
            )

        if viento >= 50:

            alertas.append(
                "💨 Se esperan vientos fuertes."
            )

        if uv >= 8:

            alertas.append(
                "☀️ Índice UV muy alto."
            )

        if not alertas:

            alertas.append(
                "✅ No se detectan condiciones "
                "meteorológicas destacables."
            )

        return alertas

    # ==========================================================
    # MENSAJE INICIAL
    # ==========================================================

    def mostrar_mensaje_inicial(
        self
    ):

        self.limpiar_contenido()

        mensaje = QLabel(
            "📍 Buscá una localidad para comenzar."
        )

        mensaje.setObjectName(
            "error"
        )

        mensaje.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        mensaje.setWordWrap(
            True
        )

        self.layout_contenido.addWidget(
            mensaje
        )

    # ==========================================================
    # LIMPIAR
    # ==========================================================

    def limpiar_contenido(
        self
    ):

        while (
            self.layout_contenido.count()
        ):

            item = (
                self.layout_contenido.takeAt(
                    0
                )
            )

            widget = item.widget()

            if widget:

                widget.deleteLater()

    # ==========================================================
    # IR A SECCIÓN
    # ==========================================================

    def ir_a_seccion(
        self,
        nombre
    ):

        for i in range(
            self.layout_contenido.count()
        ):

            item = (
                self.layout_contenido.itemAt(
                    i
                )
            )

            widget = item.widget()

            if widget is None:

                continue

            titulo_encontrado = None

            for hijo in widget.findChildren(
                QLabel
            ):

                texto = hijo.text()

                if (
                    nombre == "Hoy"
                    and texto
                    == "🌤️ Tiempo de hoy"
                ):

                    titulo_encontrado = hijo
                    break

                if (
                    nombre == "Pronóstico"
                    and texto
                    == "📅 Pronóstico de 7 días"
                ):

                    titulo_encontrado = hijo
                    break

                if (
                    nombre == "Lluvia"
                    and texto
                    == "🌧️ Información de lluvia"
                ):

                    titulo_encontrado = hijo
                    break

                if (
                    nombre == "Viento"
                    and texto
                    == "💨 Información de viento"
                ):

                    titulo_encontrado = hijo
                    break

                if (
                    nombre == "UV"
                    and texto
                    == "☀️ Índice UV"
                ):

                    titulo_encontrado = hijo
                    break

                if (
                    nombre == "Movilidad"
                    and texto
                    == "🚦 Condiciones de movilidad"
                ):

                    titulo_encontrado = hijo
                    break

                if (
                    nombre == "Alertas"
                    and texto
                    == "⚠️ Alertas y recomendaciones"
                ):

                    titulo_encontrado = hijo
                    break

            if titulo_encontrado is not None:

                self.layout_contenido.activate()

                posicion = widget.mapTo(
                    self.contenido,
                    widget.rect().topLeft()
                ).y()

                altura_tarjeta = widget.height()

                altura_visible = (
                    self.scroll.viewport().height()
                )

                posicion_centrada = (
                    posicion
                    - (
                        altura_visible
                        - altura_tarjeta
                    ) // 2
                )

                posicion_centrada = max(
                    0,
                    posicion_centrada
                )

                barra = (
                    self.scroll.verticalScrollBar()
                )

                posicion_centrada = min(
                    posicion_centrada,
                    barra.maximum()
                )

                barra.setValue(
                    posicion_centrada
                )

                return

    # ==========================================================
    # ERROR
    # ==========================================================

    def mostrar_error(
        self,
        mensaje
    ):

        self.limpiar_contenido()

        error = QLabel(
            "❌ No se pudo obtener el clima.\n\n"
            + mensaje
        )

        error.setObjectName(
            "error"
        )

        error.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        error.setWordWrap(
            True
        )

        self.layout_contenido.addWidget(
            error
        )

    # ==========================================================
    # ESTILOS
    # ==========================================================

    def aplicar_estilos(
        self
    ):

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f4f6f8;
            }

            QWidget {
                color: #202124;
                font-family: Arial;
                font-size: 14px;
            }

            #barraLateral {
                background-color: #202124;
            }

            #tituloBarra {
                color: white;
                font-size: 24px;
                font-weight: bold;
            }

            QPushButton {
                background-color: #ffffff;
                color: #202124;
                border: 1px solid #d9d9d9;
                border-radius: 8px;
                padding: 10px;
                text-align: left;
            }

            QPushButton:hover {
                background-color: #e9eef5;
            }

            QPushButton:disabled {
                color: #999999;
                background-color: #eeeeee;
            }

            QLineEdit {
                background-color: white;
                color: #202124;
                border: 1px solid #cfd4da;
                border-radius: 8px;
                padding: 10px;
            }

            QLineEdit:focus {
                border: 2px solid #4a90e2;
            }

            QComboBox {
                background-color: white;
                color: #202124;
                border: 1px solid #cfd4da;
                border-radius: 8px;
                padding: 8px;
            }

            QComboBox:focus {
                border: 2px solid #4a90e2;
            }

            QComboBox QAbstractItemView {
                background-color: white;
                color: #202124;
                selection-background-color: #e9eef5;
                selection-color: #202124;
            }

            QCompleter QListView {
                background-color: white;
                color: #202124;
                border: 1px solid #cfd4da;
                padding: 5px;
            }

            QCompleter QListView::item {
                padding: 8px;
            }

            QCompleter QListView::item:hover {
                background-color: #e9eef5;
            }

            QScrollArea {
                border: none;
                background-color: #f4f6f8;
            }

            #tarjeta {
                background-color: white;
                border: 1px solid #e1e5e9;
                border-radius: 12px;
            }

            #tituloSeccion {
                font-size: 20px;
                font-weight: bold;
                color: #202124;
                padding: 5px;
            }

            #ubicacion {
                font-size: 24px;
                font-weight: bold;
                color: #202124;
            }

            #coordenadas {
                color: #6c757d;
            }

            #estado {
                color: #1769aa;
                font-weight: bold;
            }

            #temperatura {
                font-size: 52px;
                font-weight: bold;
            }

            #valorDato {
                font-size: 20px;
                font-weight: bold;
            }

            #iconoGrande {
                font-size: 60px;
            }

            #iconoMediano {
                font-size: 35px;
            }

            #diaPronostico {
                font-size: 17px;
                font-weight: bold;
            }

            #actualizacion {
                color: #777777;
                padding: 10px;
            }

            #error {
                font-size: 20px;
                color: #b3261e;
                padding: 50px;
            }
        """)


# ==============================================================
# EJECUTAR
# ==============================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    # ==========================================================
    # ICONO DE LA APLICACIÓN
    # ==========================================================

    app.setWindowIcon(
        QIcon(ARCHIVO_ICONO)
    )

    ventana = EstacionMeteorologica()

    # ==========================================================
    # ABRIR MAXIMIZADA
    # ==========================================================

    ventana.showMaximized()

    sys.exit(
        app.exec()
    )