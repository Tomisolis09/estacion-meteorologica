# -*- coding: utf-8 -*-
"""
Estación Meteorológica
----------------------
App de escritorio del clima (PySide6 + Open-Meteo) para Argentina.

Novedades de esta versión:
  * La ubicación se guarda en %APPDATA% (antes se perdía al instalar/compilar).
  * Ícono de la app (icono.ico / icono.png) y AppUserModelID para la barra de tareas.
  * Ícono en la bandeja del sistema que rota: temperatura, máxima, mínima y lluvia.
  * El título de la ventana (miniatura de la barra de tareas) rota con el resumen.
  * Widget flotante siempre visible, arrastrable, con la misma info rotativa.
  * Lectura de "radar" y "satélite" a partir de precipitación y nubosidad del modelo.
  * Interfaz rediseñada con tema claro / oscuro.
"""

import sys
import os
import json
import time
import ctypes
import tempfile
import subprocess
import unicodedata
import webbrowser
from datetime import datetime
from string import Template

import requests

from PySide6.QtCore import (
    Qt, QTimer, QStringListModel, QThread, Signal, QPoint,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QFont, QAction, QLinearGradient, QBrush,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QScrollArea, QSizePolicy,
    QMessageBox, QComboBox, QCompleter, QDialog, QProgressBar,
    QSystemTrayIcon, QMenu, QButtonGroup,
)


# ==============================================================
# CONSTANTES
# ==============================================================

APP_NOMBRE = "Estación Meteorológica"
APP_ID = "estacion.meteorologica.app"

# IMPORTANTE: subí este número ANTES de compilar cada versión nueva y
# poné el mismo número en version.json del repositorio.
VERSION = "2.0.0"

URL_VERSION = (
    "https://raw.githubusercontent.com/"
    "Tomisolis09/estacion-meteorologica/main/version.json"
)

URL_CLIMA = "https://api.open-meteo.com/v1/forecast"
URL_GEO = "https://geocoding-api.open-meteo.com/v1/search"

INTERVALO_ROTACION_MS = 6000

CENTRO = Qt.AlignmentFlag.AlignCenter
DERECHA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MANO = Qt.CursorShape.PointingHandCursor

DIAS_SEMANA = [
    "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
]

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

PROVINCIAS = [
    "Buenos Aires", "Catamarca", "Chaco", "Chubut",
    "Ciudad Autónoma de Buenos Aires", "Córdoba", "Corrientes",
    "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", "Mendoza",
    "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan", "San Luis",
    "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego",
    "Tucumán"
]

NAVEGACION = [
    ("🏠  Hoy", "Hoy"),
    ("📅  Pronóstico", "Pronóstico"),
    ("🕐  Por hora", "Horas"),
    ("🌧️  Lluvia", "Lluvia"),
    ("💨  Viento", "Viento"),
    ("☀️  Índice UV", "UV"),
    ("📡  Radar y satélite", "Radar"),
    ("🏍️  Movilidad", "Movilidad"),
    ("⚠️  Alertas", "Alertas"),
]

PARAMETROS_CLIMA = {
    "current": (
        "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
        "precipitation,weather_code,cloud_cover,pressure_msl,"
        "wind_speed_10m,wind_direction_10m,wind_gusts_10m"
    ),
    "hourly": (
        "temperature_2m,precipitation_probability,precipitation,weather_code,"
        "is_day,cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,"
        "visibility,cape,wind_speed_10m,uv_index"
    ),
    "daily": (
        "weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_sum,precipitation_probability_max,"
        "wind_speed_10m_max,wind_gusts_10m_max,uv_index_max"
    ),
    "minutely_15": "precipitation",
    "timezone": "auto",
    "forecast_days": 7,
}


# ==============================================================
# RUTAS Y CONFIGURACIÓN
# ==============================================================
# Antes la configuración se guardaba junto al script. Cuando la app se
# compila con PyInstaller (--onefile) esa carpeta es temporal y se borra al
# cerrar, y si se instala en "Program Files" ni siquiera se puede escribir.
# Por eso ahora se guarda en %APPDATA%\EstacionMeteorologica.

def ruta_recurso(nombre):
    """Ruta a un archivo incluido con la app (funciona con PyInstaller)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.abspath(__file__)
    )
    return os.path.join(base, nombre)


def carpeta_datos():
    base = os.environ.get("APPDATA") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    carpeta = os.path.join(base, "EstacionMeteorologica")
    try:
        os.makedirs(carpeta, exist_ok=True)
    except OSError:
        carpeta = tempfile.gettempdir()
    return carpeta


ARCHIVO_CONFIG = os.path.join(carpeta_datos(), "configuracion.json")


def _rutas_config_antiguas():
    carpetas = {os.path.dirname(os.path.abspath(__file__))}
    carpetas.add(os.path.dirname(os.path.abspath(sys.argv[0] or ".")))
    if getattr(sys, "frozen", False):
        carpetas.add(os.path.dirname(sys.executable))
    return [os.path.join(c, "configuracion.json") for c in carpetas]


def leer_config():
    for ruta in [ARCHIVO_CONFIG] + _rutas_config_antiguas():
        if os.path.exists(ruta):
            try:
                with open(ruta, "r", encoding="utf-8") as archivo:
                    datos = json.load(archivo)
                if isinstance(datos, dict):
                    return datos
            except Exception:
                continue
    return {}


def guardar_config(nuevos):
    """Mezcla `nuevos` con lo ya guardado y escribe de forma segura."""
    datos = leer_config()
    datos.update(nuevos)
    temporal = ARCHIVO_CONFIG + ".tmp"
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=4)
    os.replace(temporal, ARCHIVO_CONFIG)


# ==============================================================
# ÍCONOS
# ==============================================================

def icono_por_defecto():
    """Ícono dibujado por código, por si no existe icono.png / icono.ico."""
    pm = QPixmap(256, 256)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    grad = QLinearGradient(0, 0, 256, 256)
    grad.setColorAt(0, QColor("#2563eb"))
    grad.setColorAt(1, QColor("#38bdf8"))
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(0, 0, 256, 256, 56, 56)
    p.setBrush(QColor("#fbbf24"))
    p.drawEllipse(146, 36, 64, 64)
    p.setBrush(QColor("#ffffff"))
    p.drawEllipse(50, 120, 76, 76)
    p.drawEllipse(88, 82, 98, 98)
    p.drawEllipse(140, 108, 70, 70)
    p.drawRoundedRect(62, 140, 146, 56, 28, 28)
    p.end()
    return QIcon(pm)


def cargar_icono_app():
    for nombre in ("icono.ico", "icono.png.ico", "icono.png"):
        ruta = ruta_recurso(nombre)
        if os.path.exists(ruta):
            icono = QIcon(ruta)
            if not icono.isNull():
                return icono
    return icono_por_defecto()


def icono_numero(texto, color):
    """Ícono cuadrado de color con un número (para la bandeja del sistema)."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(0, 0, 64, 64, 16, 16)
    fuente = QFont("Segoe UI")
    fuente.setBold(True)
    largo = len(texto)
    fuente.setPixelSize(44 if largo <= 2 else 32 if largo == 3 else 26)
    p.setFont(fuente)
    p.setPen(QColor("white"))
    p.drawText(pm.rect(), CENTRO, texto)
    p.end()
    return QIcon(pm)


def color_temperatura(t):
    if t <= 5:
        return "#3b82f6"
    if t <= 15:
        return "#0ea5e9"
    if t <= 24:
        return "#10b981"
    if t <= 30:
        return "#f59e0b"
    return "#ef4444"


# ==============================================================
# UTILIDADES METEOROLÓGICAS
# ==============================================================

DESCRIPCIONES = {
    0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado",
    3: "Nublado", 45: "Niebla", 48: "Niebla con escarcha",
    51: "Llovizna débil", 53: "Llovizna", 55: "Llovizna intensa",
    56: "Llovizna helada", 57: "Llovizna helada intensa",
    61: "Lluvia débil", 63: "Lluvia", 65: "Lluvia fuerte",
    66: "Lluvia helada", 67: "Lluvia helada fuerte",
    71: "Nevada débil", 73: "Nevada", 75: "Nevada fuerte", 77: "Granizo fino",
    80: "Chubascos débiles", 81: "Chubascos", 82: "Chubascos violentos",
    85: "Chubascos de nieve", 86: "Chubascos de nieve fuertes",
    95: "Tormenta", 96: "Tormenta con granizo",
    99: "Tormenta con granizo fuerte",
}


def describir(codigo):
    return DESCRIPCIONES.get(codigo, "Variable")


def obtener_icono(codigo, es_dia=True):
    if codigo in (0, 1):
        return "☀️" if es_dia and codigo == 0 else "🌤️" if es_dia else "🌙"
    iconos = {
        2: "⛅" if es_dia else "☁️", 3: "☁️", 45: "🌫️", 48: "🌫️",
        51: "🌦️", 53: "🌦️", 55: "🌧️", 56: "🌧️", 57: "🌧️",
        61: "🌧️", 63: "🌧️", 65: "🌧️", 66: "🌧️", 67: "🌧️",
        71: "🌨️", 73: "🌨️", 75: "❄️", 77: "❄️",
        80: "🌦️", 81: "🌧️", 82: "⛈️", 85: "🌨️", 86: "❄️",
        95: "⛈️", 96: "⛈️", 99: "⛈️",
    }
    return iconos.get(codigo, "🌤️")


def gradiente_clima(codigo, es_dia):
    if codigo in (95, 96, 99):
        return "#1e1b4b", "#6d28d9"
    if not es_dia:
        return "#0f172a", "#3730a3"
    if codigo in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "#334155", "#0369a1"
    if codigo in (71, 73, 75, 77, 85, 86, 45, 48):
        return "#64748b", "#94a3b8"
    if codigo == 3:
        return "#475569", "#94a3b8"
    if codigo == 2:
        return "#2563eb", "#64748b"
    return "#1d4ed8", "#38bdf8"


def cielo_por_nubosidad(porcentaje):
    if porcentaje < 10:
        return "Despejado"
    if porcentaje < 30:
        return "Poco nublado"
    if porcentaje < 60:
        return "Parcialmente nublado"
    if porcentaje < 85:
        return "Mayormente nublado"
    return "Nublado"


def nivel_uv(uv):
    if uv < 3:
        return "Bajo"
    if uv < 6:
        return "Moderado"
    if uv < 8:
        return "Alto"
    if uv < 11:
        return "Muy alto"
    return "Extremo"


def direccion_viento(grados):
    if grados is None:
        return ""
    puntos = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    return puntos[int((grados % 360) / 45 + 0.5) % 8]


def dato(datos, clave, indice, predeterminado=0):
    valores = datos.get(clave, [])
    if 0 <= indice < len(valores) and valores[indice] is not None:
        return valores[indice]
    return predeterminado


def indice_hora_actual(horario, actual):
    referencia = (actual.get("time") or "")[:13]
    for i, t in enumerate(horario.get("time", [])):
        if t[:13] >= referencia:
            return i
    return 0


def fecha_larga(fecha_texto):
    try:
        f = datetime.strptime(fecha_texto, "%Y-%m-%d")
        return f"{DIAS_SEMANA[f.weekday()]} {f.day} de {MESES[f.month - 1]}"
    except Exception:
        return fecha_texto


def clasificar_intensidad(mm_h):
    if mm_h < 0.1:
        return "nula"
    if mm_h < 2.5:
        return "débil"
    if mm_h < 7.6:
        return "moderada"
    if mm_h < 50:
        return "fuerte"
    return "muy fuerte"


# ==============================================================
# LECTURA DE RADAR Y SATÉLITE
# ==============================================================
# Importante: esto NO analiza las imágenes del SMN. Interpreta lo mismo que
# muestran un radar y un satélite, pero a partir de los datos del modelo de
# Open-Meteo: precipitación en pasos de 15 minutos (radar), cobertura de
# nubes por capas (satélite) e inestabilidad atmosférica (CAPE).

def analizar_radar_satelite(datos):
    actual = datos.get("current", {})
    horario = datos.get("hourly", {})
    min15 = datos.get("minutely_15") or {}
    i0 = indice_hora_actual(horario, actual)
    referencia = actual.get("time") or ""

    # ---------------- RADAR ----------------
    proximos = []  # (minutos desde ahora, mm/h)
    tiempos = min15.get("time", [])
    valores = min15.get("precipitation", [])
    if referencia and tiempos and valores:
        try:
            t0 = datetime.fromisoformat(referencia)
            for t, v in zip(tiempos, valores):
                if t >= referencia:
                    minutos = int(
                        (datetime.fromisoformat(t) - t0).total_seconds() // 60
                    )
                    proximos.append((minutos, (v or 0) * 4))
                    if len(proximos) >= 8:
                        break
        except ValueError:
            proximos = []
    if not proximos:
        for k in range(3):
            proximos.append((k * 60, dato(horario, "precipitation", i0 + k)))
    horizonte = "2 horas" if len(proximos) == 8 else "3 horas"

    mm_actual = max(
        actual.get("precipitation") or 0,
        proximos[0][1] if proximos else 0,
    )
    primera = next(((mn, mm) for mn, mm in proximos if mm >= 0.1), None)
    acum3 = sum(dato(horario, "precipitation", i0 + k) for k in range(3))
    prob6 = max(
        [dato(horario, "precipitation_probability", i0 + k) for k in range(6)]
        or [0]
    )
    cape = max([dato(horario, "cape", i0 + k) for k in range(6)] or [0])

    radar_lineas = []
    if mm_actual >= 0.1:
        radar_titulo = (
            f"Precipitación {clasificar_intensidad(mm_actual)} en la zona"
        )
        fin = next((mn for mn, mm in proximos if mn > 0 and mm < 0.1), None)
        if fin is not None:
            radar_lineas.append(f"🕒 Cesaría en unos {fin} min.")
        else:
            radar_lineas.append(
                f"🕒 Continuaría durante las próximas {horizonte}."
            )
    elif primera:
        intensidad = clasificar_intensidad(max(m for _, m in proximos))
        radar_titulo = f"Lluvia {intensidad} en camino"
        radar_lineas.append(f"🕒 Comenzaría en unos {primera[0]} min.")
    else:
        radar_titulo = f"Sin precipitación prevista en las próximas {horizonte}"

    radar_lineas.append(f"💧 Acumulado próximas 3 h: {acum3:.1f} mm")
    radar_lineas.append(f"🎯 Probabilidad máxima en 6 h: {prob6:.0f}%")
    if cape >= 2000 and prob6 >= 30:
        radar_lineas.append(
            f"⚡ Atmósfera muy inestable (CAPE {cape:.0f} J/kg): "
            "riesgo de tormentas fuertes."
        )
    elif cape >= 1000 and prob6 >= 20:
        radar_lineas.append(
            f"⚡ Inestabilidad moderada (CAPE {cape:.0f} J/kg): "
            "posibles tormentas aisladas."
        )

    # ---------------- SATÉLITE ----------------
    nubes = actual.get("cloud_cover")
    if nubes is None:
        nubes = dato(horario, "cloud_cover", i0)
    bajas = dato(horario, "cloud_cover_low", i0)
    medias = dato(horario, "cloud_cover_mid", i0)
    altas = dato(horario, "cloud_cover_high", i0)
    cielo = cielo_por_nubosidad(nubes)
    sat_titulo = f"{cielo} ({nubes:.0f}% de cobertura)"

    sat_lineas = []
    capas = {"bajas": bajas, "medias": medias, "altas": altas}
    dominante, valor = max(capas.items(), key=lambda kv: kv[1])
    if valor < 20:
        sat_lineas.append("🌤️ Sin capas de nubes significativas.")
    else:
        descripcion = {
            "bajas": "Predominan nubes bajas (estratos): cielo cubierto, "
                     "posible llovizna o neblina.",
            "medias": "Predominan nubes medias (altostratos/altocúmulos): "
                      "sol velado.",
            "altas": "Predominan nubes altas (cirros): cielo velado, "
                     "sin lluvia asociada.",
        }[dominante]
        sat_lineas.append(f"☁️ {descripcion}")
    sat_lineas.append(
        f"📊 Capas: bajas {bajas:.0f}% · medias {medias:.0f}% · "
        f"altas {altas:.0f}%"
    )

    futura = dato(horario, "cloud_cover", i0 + 6, nubes)
    delta = futura - nubes
    if delta >= 20:
        tendencia = f"📈 La nubosidad aumentaría en 6 h (→ {futura:.0f}%)."
        tendencia_txt = "con nubosidad en aumento"
    elif delta <= -20:
        tendencia = f"📉 La nubosidad disminuiría en 6 h (→ {futura:.0f}%)."
        tendencia_txt = "con tendencia a despejar"
    else:
        tendencia = "➖ La nubosidad se mantendría similar en las próximas 6 h."
        tendencia_txt = "sin cambios importantes en la nubosidad"
    sat_lineas.append(tendencia)

    visibilidad = dato(horario, "visibility", i0, None)
    if visibilidad is not None and visibilidad < 5000:
        sat_lineas.append(
            f"🌫️ Visibilidad reducida: {visibilidad / 1000:.1f} km."
        )

    # ---------------- RESUMEN ----------------
    partes = [f"Cielo {cielo.lower()}, {tendencia_txt}."]
    if mm_actual >= 0.1:
        partes.append(
            f"Hay precipitación {clasificar_intensidad(mm_actual)} ahora mismo."
        )
    elif primera:
        partes.append(f"Se espera lluvia en unos {primera[0]} minutos.")
    elif prob6 >= 40:
        partes.append(
            "Por ahora no llueve, pero hay chances de lluvia en las próximas horas."
        )
    else:
        partes.append("No se esperan lluvias en el corto plazo.")
    if cape >= 1000 and prob6 >= 20:
        partes.append("Ojo con la inestabilidad: pueden desarrollarse tormentas.")
    resumen = " ".join(partes)

    return {
        "radar_titulo": radar_titulo,
        "radar_lineas": radar_lineas,
        "sat_titulo": sat_titulo,
        "sat_lineas": sat_lineas,
        "resumen": resumen,
    }


# ==============================================================
# CONDICIONES, MOVILIDAD Y ALERTAS
# ==============================================================

def condicion_moto(actual, diario):
    lluvia = dato(diario, "precipitation_probability_max", 0)
    viento = dato(diario, "wind_speed_10m_max", 0)
    codigo = dato(diario, "weather_code", 0)
    if codigo >= 95:
        return "bad", "Tormentas previstas. Mejor no circular."
    if lluvia >= 70:
        return "bad", f"Alta probabilidad de lluvia ({lluvia:.0f}%). Pista resbalosa."
    if viento >= 50:
        return "bad", f"Viento fuerte ({viento:.0f} km/h). Precaución."
    if lluvia >= 40 or viento >= 35:
        return "warn", "Condiciones regulares. Posible lluvia o viento."
    return "ok", "Buenas condiciones para circular."


def condicion_auto(actual, diario):
    lluvia = dato(diario, "precipitation_probability_max", 0)
    viento = dato(diario, "wind_speed_10m_max", 0)
    codigo = dato(diario, "weather_code", 0)
    if codigo >= 95:
        return "bad", "Tormentas previstas. Conducí con mucha precaución."
    if codigo in (45, 48):
        return "warn", "Niebla: reducí la velocidad y usá luces bajas."
    if lluvia >= 70 or viento >= 60:
        return "warn", "Conducí con precaución por lluvia o viento."
    return "ok", "Buenas condiciones para conducir."


def condicion_caminando(actual, diario):
    lluvia = dato(diario, "precipitation_probability_max", 0)
    uv = dato(diario, "uv_index_max", 0)
    tmax = dato(diario, "temperature_2m_max", 0)
    if lluvia >= 70:
        return "bad", "Lluvia probable. Llevá paraguas o impermeable."
    if tmax >= 35:
        return "warn", "Calor intenso. Hidratate y evitá el mediodía."
    if uv >= 8:
        return "warn", "UV muy alto. Usá protector solar."
    return "ok", "Buenas condiciones para caminar."


def generar_alertas(actual, diario):
    alertas = []
    codigo = dato(diario, "weather_code", 0)
    lluvia = dato(diario, "precipitation_probability_max", 0)
    viento = dato(diario, "wind_speed_10m_max", 0)
    rafagas = dato(diario, "wind_gusts_10m_max", 0)
    uv = dato(diario, "uv_index_max", 0)
    tmax = dato(diario, "temperature_2m_max", 0)
    tmin = dato(diario, "temperature_2m_min", 0)

    if codigo >= 95:
        alertas.append(("bad", "⛈️ Se esperan tormentas hoy. Evitá zonas abiertas y resguardate."))
    if lluvia >= 70:
        alertas.append(("warn", f"🌧️ Alta probabilidad de lluvia hoy ({lluvia:.0f}%)."))
    if viento >= 50 or rafagas >= 70:
        alertas.append(("warn", f"💨 Vientos fuertes (hasta {max(viento, rafagas):.0f} km/h)."))
    if uv >= 8:
        alertas.append(("warn", f"☀️ Índice UV {nivel_uv(uv).lower()} ({uv:.1f}). Usá protección solar."))
    if tmax >= 35:
        alertas.append(("warn", f"🥵 Calor intenso: máxima de {tmax:.0f} °C."))
    if tmin <= 3:
        alertas.append(("warn", f"🥶 Frío intenso: mínima de {tmin:.0f} °C. Posibles heladas."))
    if dato(diario, "precipitation_probability_max", 1) >= 70 and lluvia < 70:
        alertas.append(("info", "🌧️ Mañana hay alta probabilidad de lluvia."))
    if not alertas:
        alertas.append(("ok", "✅ No se detectan condiciones meteorológicas destacables."))
    return alertas


# ==============================================================
# HILO DE DESCARGA DEL CLIMA
# ==============================================================

class HiloClima(QThread):
    listo = Signal(int, dict)
    fallo = Signal(int, str)

    def __init__(self, token, latitud, longitud):
        super().__init__()
        self.token = token
        self.latitud = latitud
        self.longitud = longitud

    def run(self):
        parametros = dict(
            PARAMETROS_CLIMA, latitude=self.latitud, longitude=self.longitud
        )
        try:
            try:
                r = requests.get(URL_CLIMA, params=parametros, timeout=20)
                r.raise_for_status()
            except requests.HTTPError:
                # Reintento sin los datos de 15 minutos por si no están disponibles
                parametros.pop("minutely_15", None)
                r = requests.get(URL_CLIMA, params=parametros, timeout=20)
                r.raise_for_status()
            self.listo.emit(self.token, r.json())
        except Exception as e:
            self.fallo.emit(self.token, str(e))


def version_tupla(texto):
    """'v1.2.0' -> (1, 2, 0, 0) para comparar versiones numéricamente."""
    partes = []
    for p in str(texto).strip().lstrip("vV").split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        partes.append(int(num) if num else 0)
    partes += [0] * (4 - len(partes))
    return tuple(partes[:4])


def carpeta_escribible(carpeta):
    """True si se puede escribir en la carpeta (para poder reemplazar el .exe)."""
    try:
        prueba = os.path.join(carpeta, ".prueba_escritura")
        with open(prueba, "w") as archivo:
            archivo.write("x")
        os.remove(prueba)
        return True
    except OSError:
        return False


class HiloActualizacion(QThread):
    """Consulta version.json en segundo plano; avisa solo si hay algo más nuevo."""
    disponible = Signal(str, str, str)

    def run(self):
        try:
            r = requests.get(URL_VERSION, timeout=10)
            r.raise_for_status()
            datos = r.json()
            version = datos.get("version", "")
            url = datos.get("url", "")
            notas = datos.get("notas", "No hay información sobre los cambios.")
            if (
                version and url
                and version_tupla(version) > version_tupla(VERSION)
            ):
                self.disponible.emit(version, url, notas)
        except Exception:
            pass  # sin internet o repo inaccesible: se ignora en silencio


# ==============================================================
# WIDGETS PROPIOS
# ==============================================================

class TarjetaClick(QFrame):
    clicked = Signal()

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(evento)


def crear_dato(titulo, valor, marco="tarjetaDato", nombre_valor="valorDato"):
    f = QFrame()
    f.setObjectName(marco)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(2)
    a = QLabel(titulo)
    a.setObjectName("etiquetaDato")
    a.setAlignment(CENTRO)
    b = QLabel(valor)
    b.setObjectName(nombre_valor)
    b.setAlignment(CENTRO)
    lay.addWidget(a)
    lay.addWidget(b)
    return f


def hay_app_pantalla_completa():
    """True si el programa en primer plano ocupa toda la pantalla
    (video, juego, presentación, o una ventana maximizada con la barra de
    tareas oculta). Solo Windows; en otros sistemas devuelve False."""
    if sys.platform != "win32":
        return False
    try:
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False

        # El escritorio y la barra de tareas no cuentan como "pantalla completa"
        clase = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, clase, 256)
        if clase.value in (
            "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"
        ):
            return False

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False
        m = info.rcMonitor
        return (
            rect.left <= m.left and rect.top <= m.top
            and rect.right >= m.right and rect.bottom >= m.bottom
        )
    except Exception:
        return False


class MiniWidget(QWidget):
    """Widget flotante: ventana normal (no siempre arriba), así que cualquier
    programa que abras queda por encima. Arrastrable, con info rotativa."""

    abrir = Signal()
    cerrar = Signal()
    movido = Signal(int, int)

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(300, 160)
        self.setToolTip("Doble clic: abrir la app · Arrastrá para mover")
        self._arrastre = None

        self.marco = QFrame()
        self.marco.setObjectName("miniMarco")
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(self.marco)

        v = QVBoxLayout(self.marco)
        v.setContentsMargins(18, 12, 12, 12)
        v.setSpacing(0)

        fila = QHBoxLayout()
        self.l_icono = QLabel("🌤️")
        self.l_icono.setObjectName("miniIcono")
        self.l_temp = QLabel("--°")
        self.l_temp.setObjectName("miniTemp")
        self.b_cerrar = QPushButton("✕")
        self.b_cerrar.setCursor(MANO)
        self.b_cerrar.clicked.connect(self.cerrar.emit)
        fila.addWidget(self.l_icono)
        fila.addWidget(self.l_temp)
        fila.addStretch()
        fila.addWidget(self.b_cerrar, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(fila)

        self.l_desc = QLabel("Cargando…")
        self.l_desc.setObjectName("miniDesc")
        self.l_minmax = QLabel("")
        self.l_minmax.setObjectName("miniMinMax")
        self.l_linea = QLabel("")
        self.l_linea.setObjectName("miniLinea")
        self.l_linea.setWordWrap(True)
        v.addWidget(self.l_desc)
        v.addWidget(self.l_minmax)
        v.addSpacing(6)
        v.addWidget(self.l_linea)
        v.addStretch()

        self._estilo("#1d4ed8", "#38bdf8")

    def _estilo(self, c1, c2):
        self.marco.setStyleSheet(f"""
            #miniMarco {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {c1}, stop:1 {c2});
                border-radius: 20px;
            }}
            QLabel {{ color: white; background: transparent;
                      font-family: 'Segoe UI', Arial; }}
            #miniTemp {{ font-size: 40px; font-weight: 700; }}
            #miniIcono {{ font-size: 32px; padding-right: 6px; }}
            #miniDesc {{ font-size: 15px; font-weight: 600; }}
            #miniMinMax {{ font-size: 13px; }}
            #miniLinea {{ font-size: 12px; }}
            QPushButton {{
                background: rgba(255,255,255,0.18); color: white; border: none;
                border-radius: 11px; min-width: 22px; max-width: 22px;
                min-height: 22px; max-height: 22px; font-size: 11px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.35); }}
        """)

    def actualizar(self, info):
        c1, c2 = gradiente_clima(info["codigo"], info["es_dia"])
        self._estilo(c1, c2)
        self.l_icono.setText(info["icono"])
        self.l_temp.setText(info["temp"])
        self.l_desc.setText(info["desc"])
        self.l_minmax.setText(info["minmax"])

    def set_linea(self, texto):
        self.l_linea.setText(texto)

    def en_arrastre(self):
        return self._arrastre is not None

    # --- arrastrar ---
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._arrastre = (
                e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, e):
        if self._arrastre is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._arrastre)

    def mouseReleaseEvent(self, e):
        if self._arrastre is not None:
            self._arrastre = None
            self.movido.emit(self.x(), self.y())

    def mouseDoubleClickEvent(self, e):
        self.abrir.emit()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.addAction("Abrir Estación Meteorológica", self.abrir.emit)
        menu.addAction("Ocultar widget", self.cerrar.emit)
        menu.exec(e.globalPos())


def posicion_barra_tareas(g, a, ancho, offset):
    """Calcula dónde poner la franja sobre la barra de tareas.

    g = geometría de la pantalla, a = área disponible (sin la barra de tareas);
    ambas como (izquierda, arriba, derecha, abajo).
    Devuelve (x, y, alto, hay_barra_horizontal).
    """
    gl, gt, gr, gb = g
    al, at, ar, ab = a
    if gb > ab:
        grosor, arriba = gb - ab, False
    elif at > gt:
        grosor, arriba = at - gt, True
    else:
        grosor, arriba = 0, False
    if grosor:
        alto = max(30, min(grosor - 8, 56))
        if arriba:
            y = gt + (grosor - alto) // 2
        else:
            y = ab + 1 + (grosor - alto) // 2
    else:
        # Barra oculta o vertical: queda flotando en la esquina inferior derecha
        alto = 44
        y = gb - alto - 8
    x = gr - ancho - offset + 1
    x = max(gl, min(x, gr - ancho + 1))
    return x, y, alto, bool(grosor)


class BarraTareasWidget(QWidget):
    """Franja con el clima que se apoya sobre la barra de tareas de Windows.

    Windows no deja que una app común incruste cosas dentro de la barra de
    tareas, así que esto es una ventanita sin bordes, siempre arriba, ubicada
    sobre la zona libre de la barra (junto a la bandeja del sistema).
    """

    abrir = Signal()
    cerrar = Signal()
    movido = Signal(int)

    ANCHO = 300
    OFFSET_INICIAL = 300

    def __init__(self, offset=300):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setToolTip(
            "Doble clic: abrir la app · Arrastrá para moverla a lo largo "
            "de la barra"
        )
        self.offset = offset
        self._arrastre = None
        self._offset_ini = offset
        self._ancho_texto = 178

        self.marco = QFrame()
        self.marco.setObjectName("barraMarco")
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(self.marco)

        h = QHBoxLayout(self.marco)
        h.setContentsMargins(10, 2, 10, 2)
        h.setSpacing(8)
        self.l_icono = QLabel("🌤️")
        self.l_icono.setObjectName("barraIcono")
        self.l_temp = QLabel("--°")
        self.l_temp.setObjectName("barraTemp")
        col = QVBoxLayout()
        col.setSpacing(0)
        self.l_desc = QLabel("Cargando…")
        self.l_desc.setObjectName("barraDesc")
        self.l_linea = QLabel("")
        self.l_linea.setObjectName("barraLinea")
        col.addStretch()
        col.addWidget(self.l_desc)
        col.addWidget(self.l_linea)
        col.addStretch()
        h.addWidget(self.l_icono)
        h.addWidget(self.l_temp)
        h.addLayout(col, 1)

        self.marco.setStyleSheet("""
            #barraMarco { background: rgba(15, 23, 42, 235); border-radius: 8px; }
            QLabel { color: white; background: transparent;
                     font-family: 'Segoe UI', Arial; }
            #barraIcono { font-size: 20px; }
            #barraTemp { font-size: 20px; font-weight: 700; }
            #barraDesc { font-size: 12px; font-weight: 600; }
            #barraLinea { font-size: 11px; color: #cbd5e1; }
        """)
        self.setFixedSize(self.ANCHO, 44)

    def _elidir(self, etiqueta, texto):
        return QFontMetrics(etiqueta.font()).elidedText(
            texto, Qt.TextElideMode.ElideRight, self._ancho_texto
        )

    def actualizar(self, info):
        self.l_icono.setText(info["icono"])
        self.l_temp.setText(info["temp"])
        self.l_desc.setText(self._elidir(self.l_desc, info["desc"]))

    def set_linea(self, texto):
        self.l_linea.setText(self._elidir(self.l_linea, texto))

    def colocar(self):
        pantalla = QApplication.primaryScreen()
        g = pantalla.geometry()
        a = pantalla.availableGeometry()
        x, y, alto, _ = posicion_barra_tareas(
            (g.left(), g.top(), g.right(), g.bottom()),
            (a.left(), a.top(), a.right(), a.bottom()),
            self.ANCHO, self.offset,
        )
        self.setFixedSize(self.ANCHO, alto)
        self.move(x, y)

    def reafirmar(self):
        """Vuelve a ponerla por encima de la barra de tareas (Windows)."""
        if sys.platform != "win32" or not self.isVisible():
            return
        try:
            ctypes.windll.user32.SetWindowPos(
                ctypes.c_void_p(int(self.winId())), ctypes.c_void_p(-1),
                0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010,  # sin mover/tamaño/activar
            )
        except Exception:
            pass

    def en_arrastre(self):
        return self._arrastre is not None

    # --- arrastrar (solo en horizontal) ---
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._arrastre = e.globalPosition().toPoint().x()
            self._offset_ini = self.offset

    def mouseMoveEvent(self, e):
        if self._arrastre is not None and e.buttons() & Qt.MouseButton.LeftButton:
            dx = e.globalPosition().toPoint().x() - self._arrastre
            ancho_pantalla = QApplication.primaryScreen().geometry().width()
            self.offset = max(0, min(self._offset_ini - dx,
                                     ancho_pantalla - self.ANCHO))
            self.colocar()

    def mouseReleaseEvent(self, e):
        if self._arrastre is not None:
            self._arrastre = None
            self.movido.emit(self.offset)

    def mouseDoubleClickEvent(self, e):
        self.abrir.emit()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.addAction("Abrir Estación Meteorológica", self.abrir.emit)
        menu.addAction("Restablecer posición", self._restablecer)
        menu.addAction("Ocultar de la barra de tareas", self.cerrar.emit)
        menu.exec(e.globalPos())

    def _restablecer(self):
        self.offset = self.OFFSET_INICIAL
        self.colocar()
        self.movido.emit(self.offset)


# ==============================================================
# ESTILOS (tema claro / oscuro)
# ==============================================================

TEMAS = {
    "claro": dict(
        fondo="#eef2f7", tarjeta="#ffffff", borde="#e2e8f0", texto="#0f172a",
        texto2="#64748b", acento="#2563eb", acento_hover="#1d4ed8",
        barra="#0f172a", barra_texto="#94a3b8", barra_hover="#1e293b",
        barra_activo="#2563eb", input="#f8fafc", hover="#eef4ff",
        sub="#f1f5f9",
    ),
    "oscuro": dict(
        fondo="#0b1220", tarjeta="#131c2e", borde="#223049", texto="#e5e9f0",
        texto2="#8b9bb4", acento="#3b82f6", acento_hover="#60a5fa",
        barra="#070c16", barra_texto="#8b9bb4", barra_hover="#111a2c",
        barra_activo="#2563eb", input="#0f1729", hover="#1b2740",
        sub="#182339",
    ),
}

CSS = Template("""
QMainWindow, QDialog { background: $fondo; }
QWidget {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 14px; color: $texto;
}
QLabel { background: transparent; }
QToolTip {
    background: $tarjeta; color: $texto; border: 1px solid $borde; padding: 6px;
}

/* ---------- barra lateral ---------- */
#barra { background: $barra; }
#barra QLabel { color: $barra_texto; }
#barra #logo { color: white; font-size: 22px; font-weight: 700; }
#barra #logoSub { font-size: 12px; }
#barra #navTitulo { font-size: 11px; font-weight: 700; padding: 14px 6px 4px 6px; }
#barra QPushButton {
    background: transparent; color: $barra_texto; border: none;
    border-radius: 10px; padding: 9px 14px; text-align: left;
}
#barra QPushButton:hover { background: $barra_hover; color: white; }
#barra QPushButton#nav:checked {
    background: $barra_activo; color: white; font-weight: 600;
}
#barra QPushButton#navSec { font-size: 13px; padding: 7px 14px; }
#barra QPushButton#navSec:checked { background: $barra_hover; color: white; }

/* ---------- botones ---------- */
QPushButton#primario {
    background: $acento; color: white; border: none; border-radius: 10px;
    padding: 10px 18px; font-weight: 600;
}
QPushButton#primario:hover { background: $acento_hover; }
QPushButton#primario:disabled { background: $borde; color: $texto2; }
QPushButton#secundario {
    background: $tarjeta; color: $texto; border: 1px solid $borde;
    border-radius: 10px; padding: 10px 16px;
}
QPushButton#secundario:hover { background: $hover; border: 1px solid $acento; }
QPushButton#secundario:disabled { color: $texto2; background: $sub; }

/* ---------- campos ---------- */
QLineEdit, QComboBox {
    background: $input; border: 1px solid $borde; border-radius: 10px;
    padding: 9px 12px; selection-background-color: $acento;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid $acento; }
QLineEdit:disabled, QComboBox:disabled { color: $texto2; background: $sub; }
QComboBox QAbstractItemView, QListView {
    background: $tarjeta; color: $texto; border: 1px solid $borde;
    selection-background-color: $hover; selection-color: $texto;
    outline: 0; padding: 4px;
}

/* ---------- tarjetas ---------- */
#contenido { background: $fondo; }
QScrollArea { border: none; background: $fondo; }
#scrollHoras, #contenidoHoras { background: transparent; border: none; }
#tarjeta, #tarjetaDato {
    background: $tarjeta; border: 1px solid $borde; border-radius: 16px;
}
#sub { background: $sub; border: none; border-radius: 12px; }
#diaCard { background: $sub; border: 1px solid transparent; border-radius: 14px; }
#diaCard:hover { background: $hover; border: 1px solid $acento; }
#horaCard { background: $sub; border: none; border-radius: 12px; }

#tituloSeccion { font-size: 17px; font-weight: 700; }
#subtitulo { font-size: 15px; font-weight: 700; }
#texto2 { color: $texto2; }
#estado { color: $acento; font-weight: 600; }
#etiquetaDato { color: $texto2; font-size: 12px; }
#valorDato { font-size: 20px; font-weight: 700; }
#diaPronostico { font-size: 15px; font-weight: 700; }
#iconoMediano { font-size: 32px; }
#tituloDetalle { font-size: 28px; font-weight: 700; }
#iconoDetalle { font-size: 54px; }
#error { font-size: 18px; color: #dc2626; padding: 40px; }

QLabel[nivel="ok"] { color: #16a34a; font-weight: 600; }
QLabel[nivel="info"] { color: $acento; font-weight: 600; }
QLabel[nivel="warn"] { color: #d97706; font-weight: 600; }
QLabel[nivel="bad"] { color: #dc2626; font-weight: 600; }

/* ---------- barras de progreso ---------- */
QProgressBar { background: $sub; border: none; border-radius: 4px; }
QProgressBar::chunk { background: $acento; border-radius: 4px; }
QProgressBar#barraViento::chunk { background: #14b8a6; }
QProgressBar#barraUV::chunk { background: #f59e0b; }

/* ---------- scrollbars ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical {
    background: $borde; border-radius: 4px; min-height: 30px;
}
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal {
    background: $borde; border-radius: 4px; min-width: 30px;
}
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
""")


# ==============================================================
# VENTANA DETALLE DEL DÍA
# ==============================================================

class VentanaDetalleDia(QDialog):

    def __init__(self, padre, fecha, indice, diario, horario):
        super().__init__(padre)
        self.setWindowTitle("Detalle del pronóstico")
        self.setWindowIcon(padre.icono_app)
        self.resize(980, 720)

        codigo = dato(diario, "weather_code", indice)
        maxima = dato(diario, "temperature_2m_max", indice)
        minima = dato(diario, "temperature_2m_min", indice)
        prob = dato(diario, "precipitation_probability_max", indice)
        lluvia = dato(diario, "precipitation_sum", indice)
        viento = dato(diario, "wind_speed_10m_max", indice)
        uv = dato(diario, "uv_index_max", indice)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)

        # --- cabecera ---
        cab = QHBoxLayout()
        icono = QLabel(obtener_icono(codigo))
        icono.setObjectName("iconoDetalle")
        textos = QVBoxLayout()
        textos.setSpacing(0)
        titulo = QLabel(padre.nombre_dia(fecha, indice))
        titulo.setObjectName("tituloDetalle")
        sub = QLabel(f"{fecha_larga(fecha)}  ·  {describir(codigo)}")
        sub.setObjectName("texto2")
        textos.addWidget(titulo)
        textos.addWidget(sub)
        cab.addWidget(icono)
        cab.addSpacing(8)
        cab.addLayout(textos)
        cab.addStretch()
        lay.addLayout(cab)

        # --- datos del día ---
        grid = QGridLayout()
        grid.setSpacing(10)
        datos = [
            ("🌡️ Máxima", f"{maxima:.0f} °C"),
            ("❄️ Mínima", f"{minima:.0f} °C"),
            ("🌧️ Prob. de lluvia", f"{prob:.0f}%"),
            ("💧 Precipitación", f"{lluvia:.1f} mm"),
            ("💨 Viento máximo", f"{viento:.0f} km/h"),
            ("☀️ Índice UV", f"{uv:.1f} · {nivel_uv(uv)}"),
        ]
        for pos, (nombre, valor) in enumerate(datos):
            grid.addWidget(crear_dato(nombre, valor), pos // 3, pos % 3)
        lay.addLayout(grid)

        # --- horas ---
        titulo_h = QLabel("🕐  Pronóstico por hora")
        titulo_h.setObjectName("tituloSeccion")
        lay.addWidget(titulo_h)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        contenido = QWidget()
        contenido.setObjectName("contenido")
        g = QGridLayout(contenido)
        g.setSpacing(10)
        g.setContentsMargins(0, 0, 8, 0)

        indices = [
            i for i, t in enumerate(horario.get("time", []))
            if t.startswith(fecha)
        ]
        columnas = 6
        for pos, i in enumerate(indices):
            try:
                hora = datetime.fromisoformat(horario["time"][i]).strftime("%H:%M")
            except Exception:
                hora = horario["time"][i]
            es_dia = dato(horario, "is_day", i, 1) == 1
            tarjeta = QFrame()
            tarjeta.setObjectName("horaCard")
            l = QVBoxLayout(tarjeta)
            l.setContentsMargins(8, 10, 8, 10)
            l.setSpacing(2)
            filas = [
                (hora, "diaPronostico"),
                (obtener_icono(dato(horario, "weather_code", i), es_dia), "iconoMediano"),
                (f"{dato(horario, 'temperature_2m', i):.0f}°", "valorDato"),
                (f"🌧️ {dato(horario, 'precipitation_probability', i):.0f}%", "texto2"),
                (f"💧 {dato(horario, 'precipitation', i):.1f} mm", "texto2"),
                (f"💨 {dato(horario, 'wind_speed_10m', i):.0f} km/h", "texto2"),
                (f"☀️ UV {dato(horario, 'uv_index', i):.1f}", "texto2"),
            ]
            for texto, nombre in filas:
                e = QLabel(texto)
                e.setObjectName(nombre)
                e.setAlignment(CENTRO)
                l.addWidget(e)
            g.addWidget(tarjeta, pos // columnas, pos % columnas)
        for c in range(columnas):
            g.setColumnStretch(c, 1)
        g.setRowStretch(len(indices) // columnas + 1, 1)
        scroll.setWidget(contenido)
        lay.addWidget(scroll, 1)

        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("secundario")
        cerrar.setCursor(MANO)
        cerrar.clicked.connect(self.close)
        lay.addWidget(cerrar)


# ==============================================================
# VENTANA PRINCIPAL
# ==============================================================

class EstacionMeteorologica(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NOMBRE)
        self.icono_app = cargar_icono_app()
        self.setWindowIcon(self.icono_app)
        self.setMinimumSize(1000, 650)

        cfg = leer_config()
        self.tema = cfg.get("tema") if cfg.get("tema") in TEMAS else "claro"

        self.nombre_ubicacion = ""
        self.provincia_actual = ""
        self.provincia_filtro = ""
        self.localidad_actual = ""
        self.latitud = None
        self.longitud = None
        self.resultados_ubicacion = []
        self.datos_clima = None
        self.ventana_detalle = None
        self.secciones = {}
        self.bandeja = None
        self.accion_widget = None
        self.accion_barra = None
        self._barra_deseada = False  # la franja está activada por el usuario

        self._token = 0
        self._hilos = set()
        self._saliendo = False
        self._aviso_bandeja = False
        self._version_ofrecida = ""
        self._anim = None
        self.indice_rotacion = 0
        self.lineas = []
        self.iconos_rotativos = []
        self.ultima_carga = 0.0
        self.ultima_hora = datetime.now().hour

        # Timers
        self.timer_busqueda = QTimer(self)
        self.timer_busqueda.setSingleShot(True)
        self.timer_busqueda.timeout.connect(
            self.buscar_localidades_automaticamente
        )

        self.timer_reloj = QTimer(self)
        self.timer_reloj.timeout.connect(self.actualizar_pronostico_por_hora)
        self.timer_reloj.start(60000)

        self.timer_rotacion = QTimer(self)
        self.timer_rotacion.timeout.connect(self.rotar_info)
        self.timer_rotacion.start(INTERVALO_ROTACION_MS)

        self.crear_interfaz()
        self.crear_bandeja()
        self.crear_mini_widget()
        self.crear_barra_widget()
        self.aplicar_estilos()
        self.cargar_configuracion(cfg)

        if self.latitud is not None and self.longitud is not None:
            self.cargar_clima()
        else:
            self.mostrar_mensaje_inicial()

        # Búsqueda automática de actualizaciones (solo en la versión instalada)
        QTimer.singleShot(5000, self.buscar_actualizacion_silenciosa)
        self.timer_actualizacion = QTimer(self)
        self.timer_actualizacion.timeout.connect(self.buscar_actualizacion_silenciosa)
        self.timer_actualizacion.start(6 * 60 * 60 * 1000)

    # ==========================================================
    # ESTILOS
    # ==========================================================

    def aplicar_estilos(self):
        self.setStyleSheet(CSS.substitute(TEMAS[self.tema]))
        if hasattr(self, "boton_tema"):
            self.boton_tema.setText(
                "☀️  Tema claro" if self.tema == "oscuro" else "🌙  Tema oscuro"
            )

    def alternar_tema(self):
        self.tema = "oscuro" if self.tema == "claro" else "claro"
        self.aplicar_estilos()
        try:
            guardar_config({"tema": self.tema})
        except Exception:
            pass

    # ==========================================================
    # INTERFAZ
    # ==========================================================

    def crear_interfaz(self):
        contenedor = QWidget()
        raiz = QHBoxLayout(contenedor)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self.crear_barra_lateral())
        raiz.addWidget(self.crear_zona_derecha(), 1)
        self.setCentralWidget(contenedor)

    def crear_barra_lateral(self):
        barra = QFrame()
        barra.setObjectName("barra")
        barra.setFixedWidth(240)
        lay = QVBoxLayout(barra)
        lay.setContentsMargins(16, 22, 16, 16)
        lay.setSpacing(3)

        logo = QLabel("🌦️  Clima")
        logo.setObjectName("logo")
        sub = QLabel("Estación meteorológica")
        sub.setObjectName("logoSub")
        lay.addWidget(logo)
        lay.addWidget(sub)

        titulo = QLabel("SECCIONES")
        titulo.setObjectName("navTitulo")
        lay.addWidget(titulo)

        self.grupo_nav = QButtonGroup(self)
        self.grupo_nav.setExclusive(True)
        for texto, nombre in NAVEGACION:
            b = QPushButton(texto)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(MANO)
            b.clicked.connect(lambda checked=False, n=nombre: self.ir_a_seccion(n))
            self.grupo_nav.addButton(b)
            lay.addWidget(b)
            if nombre == "Hoy":
                b.setChecked(True)

        lay.addStretch()

        titulo2 = QLabel("HERRAMIENTAS")
        titulo2.setObjectName("navTitulo")
        lay.addWidget(titulo2)

        self.boton_widget = QPushButton("🪟  Widget flotante")
        self.boton_widget.setCheckable(True)
        self.boton_widget.toggled.connect(self.mostrar_widget)

        self.boton_barra = QPushButton("📌  En la barra de tareas")
        self.boton_barra.setCheckable(True)
        self.boton_barra.toggled.connect(self.mostrar_barra)

        self.boton_tema = QPushButton("🌙  Tema oscuro")
        self.boton_tema.clicked.connect(self.alternar_tema)

        boton_act = QPushButton("🔄  Buscar actualización")
        boton_act.clicked.connect(self.comprobar_actualizacion)

        boton_radar = QPushButton("📡  SMN Radar")
        boton_radar.clicked.connect(
            lambda: webbrowser.open("https://www.smn.gob.ar/radar")
        )
        boton_sat = QPushButton("🛰️  SMN Satélite")
        boton_sat.clicked.connect(
            lambda: webbrowser.open("https://www.smn.gob.ar/satelite")
        )

        for b in (self.boton_widget, self.boton_barra, self.boton_tema, boton_act,
                  boton_radar, boton_sat):
            b.setObjectName("navSec")
            b.setCursor(MANO)
            lay.addWidget(b)

        version = QLabel(f"Versión {VERSION}")
        version.setObjectName("logoSub")
        version.setAlignment(CENTRO)
        lay.addSpacing(6)
        lay.addWidget(version)
        return barra

    def crear_zona_derecha(self):
        zona = QWidget()
        lay = QVBoxLayout(zona)
        lay.setContentsMargins(24, 20, 24, 8)
        lay.setSpacing(14)
        lay.addWidget(self.crear_panel_busqueda())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.contenido = QWidget()
        self.contenido.setObjectName("contenido")
        self.layout_contenido = QVBoxLayout(self.contenido)
        self.layout_contenido.setContentsMargins(0, 0, 8, 20)
        self.layout_contenido.setSpacing(16)
        self.scroll.setWidget(self.contenido)
        lay.addWidget(self.scroll, 1)
        return zona

    def crear_panel_busqueda(self):
        panel = QFrame()
        panel.setObjectName("tarjeta")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(18, 14, 18, 12)
        lay.setSpacing(8)

        fila = QHBoxLayout()
        fila.setSpacing(10)

        self.lista_provincias = QComboBox()
        self.lista_provincias.setMinimumHeight(42)
        self.lista_provincias.setMinimumWidth(240)
        self.lista_provincias.addItem("📍 Provincia")
        self.lista_provincias.addItems(PROVINCIAS)
        self.lista_provincias.currentIndexChanged.connect(
            self.provincia_seleccionada
        )
        fila.addWidget(self.lista_provincias)

        self.entrada_ubicacion = QLineEdit()
        self.entrada_ubicacion.setPlaceholderText("🏙️  Escribí una localidad...")
        self.entrada_ubicacion.setMinimumHeight(42)
        self.entrada_ubicacion.setEnabled(False)
        self.entrada_ubicacion.textEdited.connect(self.programar_busqueda)
        self.entrada_ubicacion.returnPressed.connect(self.buscar_localidad)
        fila.addWidget(self.entrada_ubicacion, 1)

        self.boton_buscar = QPushButton("🔎  Buscar")
        self.boton_buscar.setObjectName("primario")
        self.boton_buscar.setMinimumHeight(42)
        self.boton_buscar.setCursor(MANO)
        self.boton_buscar.setEnabled(False)
        self.boton_buscar.clicked.connect(self.buscar_localidad)
        fila.addWidget(self.boton_buscar)

        self.boton_guardar = QPushButton("💾  Guardar")
        self.boton_guardar.setObjectName("secundario")
        self.boton_guardar.setMinimumHeight(42)
        self.boton_guardar.setCursor(MANO)
        self.boton_guardar.setEnabled(False)
        self.boton_guardar.clicked.connect(self.guardar_ubicacion)
        fila.addWidget(self.boton_guardar)
        lay.addLayout(fila)

        # Autocompletado
        self.modelo_completador = QStringListModel()
        self.completador = QCompleter(
            self.modelo_completador, self.entrada_ubicacion
        )
        self.completador.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.completador.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self.completador.setMaxVisibleItems(8)
        self.completador.popup().setMinimumWidth(350)
        self.entrada_ubicacion.setCompleter(self.completador)
        self.completador.activated.connect(self.seleccionar_sugerencia)

        fila_estado = QHBoxLayout()
        self.label_estado = QLabel("Seleccioná una provincia.")
        self.label_estado.setObjectName("estado")
        self.label_coordenadas = QLabel("")
        self.label_coordenadas.setObjectName("texto2")
        fila_estado.addWidget(self.label_estado, 1)
        fila_estado.addWidget(self.label_coordenadas)
        lay.addLayout(fila_estado)
        return panel

    # ==========================================================
    # BANDEJA DEL SISTEMA Y WIDGET FLOTANTE
    # ==========================================================

    def crear_bandeja(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.bandeja = QSystemTrayIcon(self.icono_app, self)
        self.bandeja.setToolTip(APP_NOMBRE)

        self.menu_bandeja = QMenu(self)
        a_abrir = QAction("Abrir Estación Meteorológica", self)
        a_abrir.triggered.connect(self.mostrar_ventana)
        self.accion_widget = QAction("Widget flotante", self)
        self.accion_widget.setCheckable(True)
        self.accion_widget.toggled.connect(self.mostrar_widget)
        self.accion_barra = QAction("Fijar en la barra de tareas", self)
        self.accion_barra.setCheckable(True)
        self.accion_barra.toggled.connect(self.mostrar_barra)
        a_actualizar = QAction("Actualizar clima ahora", self)
        a_actualizar.triggered.connect(self.cargar_clima)
        a_salir = QAction("Salir", self)
        a_salir.triggered.connect(self.salir)

        self.menu_bandeja.addAction(a_abrir)
        self.menu_bandeja.addAction(self.accion_widget)
        self.menu_bandeja.addAction(self.accion_barra)
        self.menu_bandeja.addAction(a_actualizar)
        self.menu_bandeja.addSeparator()
        self.menu_bandeja.addAction(a_salir)
        self._acciones_bandeja = [a_abrir, a_actualizar, a_salir]

        self.bandeja.setContextMenu(self.menu_bandeja)
        self.bandeja.activated.connect(self.al_activar_bandeja)
        self.bandeja.show()

    def al_activar_bandeja(self, razon):
        if razon in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.mostrar_ventana()

    def mostrar_ventana(self):
        self.setWindowState(
            self.windowState() & ~Qt.WindowState.WindowMinimized
        )
        self.show()
        self.raise_()
        self.activateWindow()

    def crear_mini_widget(self):
        self.mini = MiniWidget()
        self.mini.abrir.connect(self.mostrar_ventana)
        self.mini.cerrar.connect(lambda: self.mostrar_widget(False))
        self.mini.movido.connect(self.guardar_posicion_widget)

        cfg = leer_config()
        pantalla = QApplication.primaryScreen().availableGeometry()
        pos = cfg.get("widget_pos")
        if (
            isinstance(pos, list) and len(pos) == 2
            and pantalla.contains(QPoint(int(pos[0]), int(pos[1])))
        ):
            self.mini.move(int(pos[0]), int(pos[1]))
        else:
            self.mini.move(
                pantalla.right() - self.mini.width() - 24,
                pantalla.bottom() - self.mini.height() - 24,
            )
        if cfg.get("widget_visible"):
            self.mostrar_widget(True)

    def mostrar_widget(self, visible):
        if visible:
            self.mini.show()
        else:
            self.mini.hide()
        for control in (self.boton_widget, self.accion_widget):
            if control is not None and control.isChecked() != visible:
                control.blockSignals(True)
                control.setChecked(visible)
                control.blockSignals(False)
        try:
            guardar_config({"widget_visible": bool(visible)})
        except Exception:
            pass

    def guardar_posicion_widget(self, x, y):
        try:
            guardar_config({"widget_pos": [x, y]})
        except Exception:
            pass

    def crear_barra_widget(self):
        cfg = leer_config()
        try:
            offset = int(cfg.get("barra_offset", BarraTareasWidget.OFFSET_INICIAL))
        except (TypeError, ValueError):
            offset = BarraTareasWidget.OFFSET_INICIAL
        self.barra = BarraTareasWidget(offset)
        self.barra.abrir.connect(self.mostrar_ventana)
        self.barra.cerrar.connect(lambda: self.mostrar_barra(False))
        self.barra.movido.connect(self.guardar_offset_barra)

        # Mantiene la franja sobre la barra de tareas (y la oculta si hay un
        # programa a pantalla completa).
        self.timer_barra = QTimer(self)
        self.timer_barra.timeout.connect(self.mantener_widgets)
        self.timer_barra.start(1000)

        if cfg.get("barra_visible"):
            self.mostrar_barra(True)

    def mostrar_barra(self, visible):
        self._barra_deseada = bool(visible)
        if visible:
            self.barra.colocar()
            if not hay_app_pantalla_completa():
                self.barra.show()
                self.barra.reafirmar()
        else:
            self.barra.hide()
        for control in (self.boton_barra, self.accion_barra):
            if control is not None and control.isChecked() != visible:
                control.blockSignals(True)
                control.setChecked(visible)
                control.blockSignals(False)
        try:
            guardar_config({"barra_visible": bool(visible)})
        except Exception:
            pass

    def guardar_offset_barra(self, offset):
        try:
            guardar_config({"barra_offset": int(offset)})
        except Exception:
            pass

    def mantener_widgets(self):
        # Franja de la barra de tareas: se oculta mientras haya un programa
        # a pantalla completa y vuelve sola cuando se cierra
        if not self._barra_deseada or self.barra.en_arrastre():
            return
        if hay_app_pantalla_completa():
            if self.barra.isVisible():
                self.barra.hide()
            return
        if not self.barra.isVisible():
            self.barra.show()
        self.barra.colocar()
        self.barra.reafirmar()

    def salir(self):
        self._saliendo = True
        if self.bandeja is not None:
            self.bandeja.hide()
        self.mini.close()
        self.barra.close()
        QApplication.quit()

    def closeEvent(self, evento):
        if (
            not self._saliendo
            and self.bandeja is not None
            and self.bandeja.isVisible()
        ):
            evento.ignore()
            self.hide()
            if not self._aviso_bandeja:
                self._aviso_bandeja = True
                self.bandeja.showMessage(
                    APP_NOMBRE,
                    "Sigue funcionando en segundo plano. Para cerrarla del "
                    "todo usá «Salir» en el ícono de la bandeja.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )
            return
        self._saliendo = True
        self.mini.close()
        self.barra.close()
        evento.accept()
        QApplication.quit()

    # ==========================================================
    # INFORMACIÓN ROTATIVA (título, bandeja, widget)
    # ==========================================================

    def lineas_rotativas(self):
        datos = self.datos_clima
        if not datos:
            return ["Buscá una localidad para comenzar"]
        a = datos["current"]
        d = datos["daily"]
        lugar = self.localidad_actual or self.nombre_ubicacion
        temp = a.get("temperature_2m", 0)
        nubes = a.get("cloud_cover") or 0
        tmin = dato(d, "temperature_2m_min", 0)
        tmax = dato(d, "temperature_2m_max", 0)
        lluvia = dato(d, "precipitation_probability_max", 0)
        mm = dato(d, "precipitation_sum", 0)
        uv = dato(d, "uv_index_max", 0)

        lineas = [
            f"{lugar}: {temp:.0f} °C · {describir(a.get('weather_code', 0))}",
            f"Mín {tmin:.0f} °C  ·  Máx {tmax:.0f} °C",
            f"{cielo_por_nubosidad(nubes)} ({nubes:.0f}% de nubes)",
            f"Lluvia hoy: {lluvia:.0f}% · {mm:.1f} mm",
            f"Viento {a.get('wind_speed_10m', 0):.0f} km/h "
            f"{direccion_viento(a.get('wind_direction_10m'))}",
            f"Humedad {a.get('relative_humidity_2m', 0):.0f}% · "
            f"Sensación {a.get('apparent_temperature', 0):.0f} °C",
            f"UV máx {uv:.1f} ({nivel_uv(uv)})",
        ]
        for nivel, texto in generar_alertas(a, d):
            if nivel in ("warn", "bad"):
                lineas.append(texto)
        return lineas

    def actualizar_superficies(self):
        """Actualiza ícono de bandeja, tooltip, widget flotante y título."""
        if not self.datos_clima:
            return
        a = self.datos_clima["current"]
        d = self.datos_clima["daily"]
        codigo = a.get("weather_code", 0)
        es_dia = a.get("is_day", 1) == 1
        temp = a.get("temperature_2m", 0)
        tmin = dato(d, "temperature_2m_min", 0)
        tmax = dato(d, "temperature_2m_max", 0)
        prob = dato(d, "precipitation_probability_max", 0)
        nubes = a.get("cloud_cover") or 0

        self.lineas = self.lineas_rotativas()
        self.indice_rotacion = 0

        # Íconos que van rotando en la bandeja: temp -> máx -> mín -> lluvia
        self.iconos_rotativos = [
            icono_numero(str(int(round(temp))), color_temperatura(temp)),
            icono_numero(str(int(round(tmax))), "#dc2626"),
            icono_numero(str(int(round(tmin))), "#2563eb"),
            icono_numero(f"{prob:.0f}%", "#0f766e"),
        ]

        lugar = self.localidad_actual or self.nombre_ubicacion
        if self.bandeja is not None:
            self.bandeja.setToolTip(
                f"{lugar}: {temp:.0f} °C · {describir(codigo)}\n"
                f"Mín {tmin:.0f}° / Máx {tmax:.0f}° · {cielo_por_nubosidad(nubes)}\n"
                f"Lluvia {prob:.0f}% · Viento {a.get('wind_speed_10m', 0):.0f} km/h"
            )

        self.mini.actualizar({
            "codigo": codigo,
            "es_dia": es_dia,
            "icono": obtener_icono(codigo, es_dia),
            "temp": f"{temp:.0f}°",
            "desc": f"{lugar} · {describir(codigo)}",
            "minmax": f"⬇ Mín {tmin:.0f}°   ⬆ Máx {tmax:.0f}°",
        })
        self.barra.actualizar({
            "icono": obtener_icono(codigo, es_dia),
            "temp": f"{temp:.0f}°",
            "desc": f"{lugar} · {describir(codigo)}",
        })
        self.aplicar_rotacion()

    def aplicar_rotacion(self):
        if not self.lineas:
            return
        linea = self.lineas[self.indice_rotacion % len(self.lineas)]
        # Título: se ve al pasar el mouse por el botón de la barra de tareas
        self.setWindowTitle(f"{linea}  —  {APP_NOMBRE}")
        self.mini.set_linea(linea)
        self.barra.set_linea(linea)
        if self.bandeja is not None and self.iconos_rotativos:
            self.bandeja.setIcon(
                self.iconos_rotativos[
                    self.indice_rotacion % len(self.iconos_rotativos)
                ]
            )

    def rotar_info(self):
        if not self.lineas:
            return
        self.indice_rotacion = (self.indice_rotacion + 1) % len(self.lineas)
        self.aplicar_rotacion()

    # ==========================================================
    # ACTUALIZACIONES DE LA APP
    # ==========================================================

    def buscar_actualizacion_silenciosa(self):
        if not getattr(sys, "frozen", False):
            return  # desde el código fuente no se actualiza solo
        hilo = HiloActualizacion()
        hilo.disponible.connect(self.al_haber_actualizacion)
        self._hilos.add(hilo)
        hilo.finished.connect(lambda h=hilo: self._hilos.discard(h))
        hilo.start()

    def al_haber_actualizacion(self, version, url, notas):
        if version == self._version_ofrecida:
            return  # ya se le preguntó por esta versión en esta sesión
        self._version_ofrecida = version
        self.ofrecer_actualizacion(version, url, notas)

    def comprobar_actualizacion(self):
        """Botón manual 'Buscar actualización'."""
        try:
            respuesta = requests.get(URL_VERSION, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()
            nueva_version = datos.get("version", "")
            url_descarga = datos.get("url", "")
            notas = datos.get("notas", "No hay información sobre los cambios.")

            if not nueva_version:
                QMessageBox.warning(
                    self, "Actualización",
                    "No se pudo obtener la versión disponible."
                )
                return

            if version_tupla(nueva_version) <= version_tupla(VERSION):
                QMessageBox.information(
                    self, "Actualización",
                    f"Ya tenés la última versión instalada.\n\n"
                    f"Versión actual: {VERSION}"
                )
                return

            self.ofrecer_actualizacion(nueva_version, url_descarga, notas)

        except Exception as e:
            QMessageBox.critical(
                self, "Error de actualización",
                f"No se pudo comprobar la actualización.\n\n{e}"
            )

    def ofrecer_actualizacion(self, nueva_version, url_descarga, notas):
        respuesta_usuario = QMessageBox.question(
            self, "Nueva actualización",
            f"Hay una nueva versión disponible.\n\n"
            f"Versión actual: {VERSION}\n"
            f"Nueva versión: {nueva_version}\n\n"
            f"Cambios:\n{notas}\n\n"
            "¿Querés descargarla e instalarla?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if respuesta_usuario != QMessageBox.StandardButton.Yes:
            return

        if not url_descarga:
            QMessageBox.warning(
                self, "Actualización",
                "La actualización no tiene un enlace de descarga."
            )
            return

        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self, "Actualización",
                "La instalación automática solo funciona en la versión "
                "compilada (.exe). Ejecutando desde el código fuente no "
                "se reemplaza ningún archivo."
            )
            return

        self.descargar_actualizacion(url_descarga, nueva_version)

    def descargar_actualizacion(self, url_descarga, nueva_version):
        try:
            if not carpeta_escribible(os.path.dirname(sys.executable)):
                raise Exception(
                    "La app está instalada en una carpeta protegida (por "
                    "ejemplo «Archivos de programa») y no puede "
                    "reemplazarse sola. Instalala en una carpeta de tu "
                    "usuario, o instalá la nueva versión manualmente."
                )

            carpeta_temp = tempfile.gettempdir()
            archivo_nuevo = os.path.join(
                carpeta_temp, "Estacion.Meteorologica_nueva.exe"
            )

            respuesta = requests.get(url_descarga, stream=True, timeout=60)
            respuesta.raise_for_status()
            with open(archivo_nuevo, "wb") as archivo:
                for bloque in respuesta.iter_content(chunk_size=1024 * 1024):
                    if bloque:
                        archivo.write(bloque)

            if not os.path.exists(archivo_nuevo):
                raise Exception("No se pudo guardar el archivo descargado.")
            if os.path.getsize(archivo_nuevo) < 100000:
                raise Exception("El archivo descargado parece estar incompleto.")

            archivo_actual = sys.executable

            archivo_bat = os.path.join(carpeta_temp, "actualizar_estacion.bat")
            # Espera a que el programa se cierre y reintenta la copia
            contenido_bat = f'''@echo off
set intentos=0
:reintentar
timeout /t 2 /nobreak >nul
copy /Y "{archivo_nuevo}" "{archivo_actual}" >nul 2>&1
if not errorlevel 1 goto listo
set /a intentos+=1
if %intentos% lss 10 goto reintentar
exit /b 1
:listo
start "" "{archivo_actual}"
del "%~f0"
'''
            with open(archivo_bat, "w", encoding="utf-8") as archivo:
                archivo.write(contenido_bat)

            QMessageBox.information(
                self, "Actualización",
                f"La versión {nueva_version} se descargó correctamente.\n\n"
                "El programa se cerrará y se instalará la actualización."
            )

            subprocess.Popen(
                ["cmd", "/c", archivo_bat],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            self.salir()

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"No se pudo instalar la actualización.\n\n{e}"
            )

    # ==========================================================
    # ACTUALIZACIÓN AUTOMÁTICA DEL CLIMA
    # ==========================================================

    def actualizar_pronostico_por_hora(self):
        if self.latitud is None or self.longitud is None:
            return
        hora = datetime.now().hour
        if hora != self.ultima_hora or time.time() - self.ultima_carga > 1800:
            self.ultima_hora = hora
            self.cargar_clima()

    # ==========================================================
    # BÚSQUEDA DE LOCALIDADES
    # ==========================================================

    def provincia_seleccionada(self, indice):
        self.timer_busqueda.stop()
        self.modelo_completador.setStringList([])
        self.completador.popup().hide()
        self.entrada_ubicacion.clear()
        self.resultados_ubicacion = []
        self.boton_guardar.setEnabled(False)

        if indice == 0:
            self.entrada_ubicacion.setEnabled(False)
            self.boton_buscar.setEnabled(False)
            self.label_estado.setText("Seleccioná una provincia.")
            return

        self.provincia_filtro = self.lista_provincias.currentText()
        self.entrada_ubicacion.setEnabled(True)
        self.boton_buscar.setEnabled(True)
        self.label_estado.setText(
            f"Escribí una localidad de {self.provincia_filtro}."
        )
        self.entrada_ubicacion.setFocus()

    def programar_busqueda(self, texto):
        self.timer_busqueda.stop()
        if len(texto.strip()) < 2:
            self.modelo_completador.setStringList([])
            self.completador.popup().hide()
            self.label_estado.setText("Escribí al menos 2 letras...")
            return
        self.label_estado.setText("🔎 Buscando localidades...")
        self.timer_busqueda.start(500)

    def consultar_localidades(self, texto, provincia):
        parametros = {
            "name": f"{texto}, {provincia}",
            "count": 20,
            "language": "es",
            "format": "json",
        }
        r = requests.get(URL_GEO, params=parametros, timeout=10)
        r.raise_for_status()
        resultados = r.json().get("results", [])
        if not resultados:
            parametros["name"] = texto
            r = requests.get(URL_GEO, params=parametros, timeout=10)
            r.raise_for_status()
            resultados = r.json().get("results", [])
        return [
            x for x in resultados
            if x.get("country", "") == "Argentina"
            and self.provincia_coincide(x.get("admin1", ""), provincia)
        ]

    def buscar_localidades_automaticamente(self):
        texto = self.entrada_ubicacion.text().strip()
        provincia = self.lista_provincias.currentText()
        if len(texto) < 2 or self.lista_provincias.currentIndex() == 0:
            return
        try:
            self.resultados_ubicacion = self.consultar_localidades(
                texto, provincia
            )
            sugerencias = list(dict.fromkeys(
                r.get("name", "") for r in self.resultados_ubicacion
                if r.get("name")
            ))
            self.modelo_completador.setStringList(sugerencias)
            if sugerencias:
                self.label_estado.setText(
                    f"📍 {len(sugerencias)} localidades encontradas"
                )
                self.completador.setCompletionPrefix(texto)
                self.completador.complete()
            else:
                self.label_estado.setText(
                    f"❌ No se encontró '{texto}' en {provincia}."
                )
                self.completador.popup().hide()
        except Exception as e:
            print("Error de búsqueda:", e)
            self.label_estado.setText("⚠️ No se pudo realizar la búsqueda.")

    def provincia_coincide(self, provincia_resultado, provincia_seleccionada):
        if not provincia_resultado:
            return True

        def normalizar(texto):
            texto = unicodedata.normalize("NFD", texto)
            texto = "".join(
                c for c in texto if unicodedata.category(c) != "Mn"
            )
            return (
                texto.lower().replace("province", "")
                .replace("provincia", "").strip()
            )

        res = normalizar(provincia_resultado)
        sel = normalizar(provincia_seleccionada)
        if "buenos aires" in sel:
            return "buenos aires" in res
        return sel in res or res in sel

    def seleccionar_sugerencia(self, nombre_localidad):
        self.timer_busqueda.stop()
        for i, resultado in enumerate(self.resultados_ubicacion):
            if resultado.get("name", "") == nombre_localidad:
                self.seleccionar_resultado(i)
                return

    def buscar_localidad(self):
        if self.lista_provincias.currentIndex() == 0:
            QMessageBox.warning(
                self, "Provincia", "Primero seleccioná una provincia."
            )
            return
        texto = self.entrada_ubicacion.text().strip()
        if not texto:
            QMessageBox.warning(
                self, "Buscar localidad", "Escribí una localidad."
            )
            return

        for i, resultado in enumerate(self.resultados_ubicacion):
            if resultado.get("name", "").lower() == texto.lower():
                self.seleccionar_resultado(i)
                return

        self.label_estado.setText("🔎 Buscando localidad...")
        QApplication.processEvents()
        provincia = self.lista_provincias.currentText()
        try:
            filtrados = self.consultar_localidades(texto, provincia)
            if not filtrados:
                self.label_estado.setText(
                    f"❌ No se encontró '{texto}' en {provincia}."
                )
                return
            self.resultados_ubicacion = filtrados
            self.seleccionar_resultado(0)
        except Exception as e:
            self.label_estado.setText("❌ Error al buscar localidad.")
            QMessageBox.warning(
                self, "Error", f"No se pudo buscar la localidad.\n\n{e}"
            )

    def construir_nombre(self, resultado):
        partes = []
        nombre = resultado.get("name")
        admin1 = resultado.get("admin1")
        pais = resultado.get("country")
        if nombre:
            partes.append(nombre)
        if admin1 and admin1 != nombre:
            partes.append(admin1)
        if pais:
            partes.append(pais)
        return ", ".join(partes)

    def seleccionar_resultado(self, indice):
        if not (0 <= indice < len(self.resultados_ubicacion)):
            return
        resultado = self.resultados_ubicacion[indice]

        self.localidad_actual = resultado.get("name", "")
        self.provincia_filtro = self.lista_provincias.currentText()
        self.provincia_actual = resultado.get("admin1", self.provincia_filtro)
        self.nombre_ubicacion = self.construir_nombre(resultado)
        self.latitud = resultado.get("latitude")
        self.longitud = resultado.get("longitude")

        self.entrada_ubicacion.setText(self.localidad_actual)
        self.label_coordenadas.setText(
            f"📍 {self.latitud:.4f}, {self.longitud:.4f}"
        )
        self.label_estado.setText(
            f"✅ Localidad seleccionada: {self.nombre_ubicacion}"
        )
        self.boton_guardar.setEnabled(True)
        self.completador.popup().hide()

        self.datos_clima = None
        self.cargar_clima()

    # ==========================================================
    # GUARDAR / CARGAR UBICACIÓN
    # ==========================================================

    def guardar_ubicacion(self):
        if self.latitud is None or self.longitud is None:
            return
        try:
            guardar_config({
                "nombre": self.nombre_ubicacion,
                "provincia": self.provincia_actual,
                "provincia_filtro": self.provincia_filtro,
                "localidad": self.localidad_actual,
                "latitud": self.latitud,
                "longitud": self.longitud,
            })
            self.label_estado.setText(
                f"💾 Ubicación guardada: {self.nombre_ubicacion}"
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Error",
                f"No se pudo guardar la ubicación.\n\n"
                f"Archivo: {ARCHIVO_CONFIG}\n{e}"
            )

    def cargar_configuracion(self, cfg):
        if not cfg:
            return
        self.nombre_ubicacion = cfg.get("nombre", "")
        self.provincia_actual = cfg.get("provincia", "")
        self.provincia_filtro = cfg.get("provincia_filtro", "")
        self.localidad_actual = cfg.get("localidad", "")
        self.latitud = cfg.get("latitud")
        self.longitud = cfg.get("longitud")

        # Elegir la provincia en el combo sin disparar la señal
        indice = self.lista_provincias.findText(self.provincia_filtro)
        if indice < 0 and self.provincia_actual:
            for i, nombre in enumerate(PROVINCIAS, start=1):
                if self.provincia_coincide(self.provincia_actual, nombre):
                    indice = i
                    break
        if indice > 0:
            self.lista_provincias.blockSignals(True)
            self.lista_provincias.setCurrentIndex(indice)
            self.lista_provincias.blockSignals(False)
            self.provincia_filtro = self.lista_provincias.currentText()
            self.entrada_ubicacion.setEnabled(True)
            self.boton_buscar.setEnabled(True)

        if self.localidad_actual:
            self.entrada_ubicacion.setText(self.localidad_actual)

        if self.latitud is not None and self.longitud is not None:
            self.label_coordenadas.setText(
                f"📍 {self.latitud:.4f}, {self.longitud:.4f}"
            )
            self.label_estado.setText(
                f"💾 Ubicación guardada: {self.nombre_ubicacion}"
            )
            self.boton_guardar.setEnabled(True)

    # ==========================================================
    # CARGAR CLIMA (en un hilo, para no congelar la ventana)
    # ==========================================================

    def cargar_clima(self):
        if self.latitud is None or self.longitud is None:
            return
        self._token += 1
        hilo = HiloClima(self._token, self.latitud, self.longitud)
        hilo.listo.connect(self.al_recibir_clima)
        hilo.fallo.connect(self.al_fallar_clima)
        self._hilos.add(hilo)
        hilo.finished.connect(lambda h=hilo: self._hilos.discard(h))
        hilo.start()
        if self.datos_clima is None:
            self.mostrar_cargando()

    def al_recibir_clima(self, token, datos):
        if token != self._token:
            return
        self.datos_clima = datos
        self.ultima_carga = time.time()
        self.ultima_hora = datetime.now().hour
        self.mostrar_clima(datos)
        self.actualizar_superficies()

    def al_fallar_clima(self, token, mensaje):
        if token != self._token:
            return
        if self.datos_clima is None:
            self.mostrar_error(mensaje)

    # ==========================================================
    # NOMBRE DEL DÍA
    # ==========================================================

    def nombre_dia(self, fecha_texto, indice=0):
        try:
            fecha = datetime.strptime(fecha_texto, "%Y-%m-%d")
            if indice == 0:
                return "Hoy"
            if indice == 1:
                return "Mañana"
            return DIAS_SEMANA[fecha.weekday()]
        except Exception:
            return fecha_texto

    # ==========================================================
    # CONSTRUCCIÓN DEL CONTENIDO
    # ==========================================================

    def nueva_tarjeta(self, titulo=None, seccion=None):
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")
        tarjeta.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        lay = QVBoxLayout(tarjeta)
        lay.setContentsMargins(22, 18, 22, 20)
        lay.setSpacing(12)
        if titulo:
            t = QLabel(titulo)
            t.setObjectName("tituloSeccion")
            lay.addWidget(t)
        if seccion:
            self.secciones[seccion] = tarjeta
        self.layout_contenido.addWidget(tarjeta)
        return lay

    def mostrar_clima(self, datos):
        barra = self.scroll.verticalScrollBar()
        posicion = barra.value()
        self.limpiar_contenido()

        actual = datos["current"]
        diario = datos["daily"]
        horario = datos["hourly"]
        cantidad = min(7, len(diario.get("time", [])))

        self.crear_hero(actual, diario)
        self.crear_resumen_rapido(actual, diario)
        self.crear_pronostico(diario, horario, cantidad)
        self.crear_por_hora(actual, horario)
        self.crear_lista_lluvia(diario, cantidad)
        self.crear_lista_viento(diario, cantidad)
        self.crear_lista_uv(diario, cantidad)
        self.crear_radar_satelite(datos)
        self.crear_movilidad(actual, diario)
        self.crear_alertas(actual, diario)

        pie = QLabel(
            f"Última actualización: {datetime.now():%d/%m/%Y %H:%M}  ·  "
            "Datos: Open-Meteo"
        )
        pie.setObjectName("texto2")
        pie.setAlignment(CENTRO)
        self.layout_contenido.addWidget(pie)
        self.layout_contenido.addStretch()

        if posicion:
            QTimer.singleShot(60, lambda: barra.setValue(posicion))

    # ---------- Hero ----------
    def crear_hero(self, actual, diario):
        codigo = actual.get("weather_code", 0)
        es_dia = actual.get("is_day", 1) == 1
        c1, c2 = gradiente_clima(codigo, es_dia)

        hero = QFrame()
        hero.setObjectName("hero")
        hero.setStyleSheet(
            f"#hero {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {c1}, stop:1 {c2}); border-radius: 22px; }}"
            "#hero QLabel { color: white; background: transparent; }"
            "#heroLugar { font-size: 16px; font-weight: 600; }"
            "#heroTemp { font-size: 84px; font-weight: 700; }"
            "#heroDesc { font-size: 24px; font-weight: 500; }"
            "#heroMinMax { font-size: 15px; }"
            "#heroIcono { font-size: 110px; }"
        )
        lay = QHBoxLayout(hero)
        lay.setContentsMargins(32, 24, 32, 24)

        col = QVBoxLayout()
        col.setSpacing(0)
        lugar = QLabel(f"📍 {self.nombre_ubicacion}")
        lugar.setObjectName("heroLugar")
        lugar.setWordWrap(True)
        temp = QLabel(f"{actual.get('temperature_2m', 0):.0f}°")
        temp.setObjectName("heroTemp")
        desc = QLabel(describir(codigo))
        desc.setObjectName("heroDesc")
        tmin = dato(diario, "temperature_2m_min", 0)
        tmax = dato(diario, "temperature_2m_max", 0)
        sens = actual.get("apparent_temperature", 0)
        minmax = QLabel(
            f"⬇ Mín {tmin:.0f}°    ⬆ Máx {tmax:.0f}°    ·    "
            f"Sensación {sens:.0f}°"
        )
        minmax.setObjectName("heroMinMax")
        for w in (lugar, temp, desc, minmax):
            col.addWidget(w)

        icono = QLabel(obtener_icono(codigo, es_dia))
        icono.setObjectName("heroIcono")
        icono.setAlignment(CENTRO)

        lay.addLayout(col, 1)
        lay.addWidget(icono)
        self.secciones["Hoy"] = hero
        self.layout_contenido.addWidget(hero)

    def crear_resumen_rapido(self, actual, diario):
        cont = QWidget()
        grid = QGridLayout(cont)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        uv = dato(diario, "uv_index_max", 0)
        datos = [
            ("💧 Humedad", f"{actual.get('relative_humidity_2m', 0):.0f}%"),
            ("💨 Viento",
             f"{actual.get('wind_speed_10m', 0):.0f} km/h "
             f"{direccion_viento(actual.get('wind_direction_10m'))}"),
            ("🌧️ Lluvia hoy",
             f"{dato(diario, 'precipitation_probability_max', 0):.0f}% · "
             f"{dato(diario, 'precipitation_sum', 0):.1f} mm"),
            ("☁️ Nubosidad", f"{actual.get('cloud_cover') or 0:.0f}%"),
            ("☀️ UV máximo", f"{uv:.1f} · {nivel_uv(uv)}"),
            ("🧭 Presión", f"{actual.get('pressure_msl', 0):.0f} hPa"),
        ]
        for i, (nombre, valor) in enumerate(datos):
            grid.addWidget(crear_dato(nombre, valor), i // 3, i % 3)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        self.layout_contenido.addWidget(cont)

    # ---------- Pronóstico ----------
    def crear_pronostico(self, diario, horario, cantidad):
        lay = self.nueva_tarjeta("📅  Pronóstico de 7 días", "Pronóstico")
        aviso = QLabel("Hacé clic en un día para ver el detalle hora por hora")
        aviso.setObjectName("texto2")
        lay.addWidget(aviso)

        grid = QGridLayout()
        grid.setSpacing(10)
        for i in range(cantidad):
            card = TarjetaClick()
            card.setObjectName("diaCard")
            card.setCursor(MANO)
            card.clicked.connect(
                lambda i=i: self.mostrar_detalle_dia(i, diario, horario)
            )
            l = QVBoxLayout(card)
            l.setContentsMargins(8, 12, 8, 12)
            l.setSpacing(3)
            filas = [
                (self.nombre_dia(diario["time"][i], i), "diaPronostico"),
                (obtener_icono(dato(diario, "weather_code", i)), "iconoMediano"),
                (f"{dato(diario, 'temperature_2m_max', i):.0f}°", "valorDato"),
                (f"{dato(diario, 'temperature_2m_min', i):.0f}°", "texto2"),
                (f"💧 {dato(diario, 'precipitation_probability_max', i):.0f}%", "texto2"),
            ]
            for texto, nombre in filas:
                e = QLabel(texto)
                e.setObjectName(nombre)
                e.setAlignment(CENTRO)
                l.addWidget(e)
            grid.addWidget(card, 0, i)
        for c in range(cantidad):
            grid.setColumnStretch(c, 1)
        lay.addLayout(grid)

    # ---------- Por hora ----------
    def crear_por_hora(self, actual, horario):
        lay = self.nueva_tarjeta("🕐  Pronóstico por hora", "Horas")
        scroll = QScrollArea()
        scroll.setObjectName("scrollHoras")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setFixedHeight(176)

        cont = QWidget()
        cont.setObjectName("contenidoHoras")
        fila = QHBoxLayout(cont)
        fila.setContentsMargins(0, 0, 0, 6)
        fila.setSpacing(10)

        i0 = indice_hora_actual(horario, actual)
        total = len(horario.get("time", []))
        for i in range(i0, min(i0 + 24, total)):
            try:
                hora = datetime.fromisoformat(horario["time"][i]).strftime("%H:%M")
            except Exception:
                hora = horario["time"][i]
            es_dia = dato(horario, "is_day", i, 1) == 1
            card = QFrame()
            card.setObjectName("horaCard")
            card.setFixedWidth(82)
            l = QVBoxLayout(card)
            l.setContentsMargins(6, 10, 6, 10)
            l.setSpacing(3)
            filas = [
                (hora, "diaPronostico"),
                (obtener_icono(dato(horario, "weather_code", i), es_dia), "iconoMediano"),
                (f"{dato(horario, 'temperature_2m', i):.0f}°", "valorDato"),
                (f"💧 {dato(horario, 'precipitation_probability', i):.0f}%", "texto2"),
            ]
            for texto, nombre in filas:
                e = QLabel(texto)
                e.setObjectName(nombre)
                e.setAlignment(CENTRO)
                l.addWidget(e)
            fila.addWidget(card)
        fila.addStretch()
        scroll.setWidget(cont)
        lay.addWidget(scroll)

    # ---------- Listas con barra ----------
    def fila_barra(self, dia, valor, maximo, texto, nombre_barra=None):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 2, 0, 2)
        l.setSpacing(12)
        d = QLabel(dia)
        d.setFixedWidth(86)
        d.setObjectName("diaPronostico")
        b = QProgressBar()
        b.setRange(0, 100)
        b.setValue(int(max(0, min(valor / maximo, 1)) * 100))
        b.setTextVisible(False)
        b.setFixedHeight(8)
        if nombre_barra:
            b.setObjectName(nombre_barra)
        t = QLabel(texto)
        t.setObjectName("texto2")
        t.setMinimumWidth(170)
        t.setAlignment(DERECHA)
        l.addWidget(d)
        l.addWidget(b, 1)
        l.addWidget(t)
        return w

    def crear_lista_lluvia(self, diario, cantidad):
        lay = self.nueva_tarjeta("🌧️  Lluvia", "Lluvia")
        for i in range(cantidad):
            prob = dato(diario, "precipitation_probability_max", i)
            mm = dato(diario, "precipitation_sum", i)
            lay.addWidget(self.fila_barra(
                self.nombre_dia(diario["time"][i], i), prob, 100,
                f"{prob:.0f}%  ·  {mm:.1f} mm"
            ))

    def crear_lista_viento(self, diario, cantidad):
        lay = self.nueva_tarjeta("💨  Viento", "Viento")
        for i in range(cantidad):
            v = dato(diario, "wind_speed_10m_max", i)
            r = dato(diario, "wind_gusts_10m_max", i)
            lay.addWidget(self.fila_barra(
                self.nombre_dia(diario["time"][i], i), v, 80,
                f"{v:.0f} km/h  ·  ráfagas {r:.0f}", "barraViento"
            ))

    def crear_lista_uv(self, diario, cantidad):
        lay = self.nueva_tarjeta("☀️  Índice UV", "UV")
        for i in range(cantidad):
            uv = dato(diario, "uv_index_max", i)
            lay.addWidget(self.fila_barra(
                self.nombre_dia(diario["time"][i], i), uv, 11,
                f"{uv:.1f}  ·  {nivel_uv(uv)}", "barraUV"
            ))

    # ---------- Radar y satélite ----------
    def bloque_lectura(self, superior, titulo, lineas):
        f = QFrame()
        f.setObjectName("sub")
        l = QVBoxLayout(f)
        l.setContentsMargins(16, 14, 16, 14)
        l.setSpacing(6)
        s = QLabel(superior)
        s.setObjectName("etiquetaDato")
        t = QLabel(titulo)
        t.setObjectName("subtitulo")
        t.setWordWrap(True)
        l.addWidget(s)
        l.addWidget(t)
        for texto in lineas:
            e = QLabel(texto)
            e.setWordWrap(True)
            l.addWidget(e)
        l.addStretch()
        return f

    def crear_radar_satelite(self, datos):
        lectura = analizar_radar_satelite(datos)
        lay = self.nueva_tarjeta("📡  Radar y satélite: lectura", "Radar")

        fila = QHBoxLayout()
        fila.setSpacing(12)
        fila.addWidget(self.bloque_lectura(
            "📡 RADAR · PRECIPITACIÓN",
            lectura["radar_titulo"], lectura["radar_lineas"]), 1)
        fila.addWidget(self.bloque_lectura(
            "🛰️ SATÉLITE · NUBOSIDAD",
            lectura["sat_titulo"], lectura["sat_lineas"]), 1)
        lay.addLayout(fila)

        general = QFrame()
        general.setObjectName("sub")
        g = QVBoxLayout(general)
        g.setContentsMargins(16, 14, 16, 14)
        g.setSpacing(4)
        t = QLabel("🧭  Lectura general")
        t.setObjectName("subtitulo")
        r = QLabel(lectura["resumen"])
        r.setWordWrap(True)
        g.addWidget(t)
        g.addWidget(r)
        lay.addWidget(general)

        nota = QLabel(
            "Esta lectura se genera con la precipitación a 15 minutos, la "
            "nubosidad por capas y la inestabilidad (CAPE) del modelo de "
            "Open-Meteo. No analiza las imágenes del SMN: para verlas usá "
            "los botones de abajo."
        )
        nota.setObjectName("texto2")
        nota.setWordWrap(True)
        lay.addWidget(nota)

        botones = QHBoxLayout()
        b1 = QPushButton("📡  Abrir radar del SMN")
        b2 = QPushButton("🛰️  Abrir satélite del SMN")
        b1.clicked.connect(lambda: webbrowser.open("https://www.smn.gob.ar/radar"))
        b2.clicked.connect(lambda: webbrowser.open("https://www.smn.gob.ar/satelite"))
        for b in (b1, b2):
            b.setObjectName("secundario")
            b.setCursor(MANO)
            botones.addWidget(b)
        botones.addStretch()
        lay.addLayout(botones)

    # ---------- Movilidad ----------
    def crear_movilidad(self, actual, diario):
        lay = self.nueva_tarjeta("🚦  Condiciones de movilidad", "Movilidad")
        fila = QHBoxLayout()
        fila.setSpacing(12)
        items = [
            ("🏍️  Moto", condicion_moto(actual, diario)),
            ("🚶  Caminar", condicion_caminando(actual, diario)),
            ("🚗  Auto", condicion_auto(actual, diario)),
        ]
        for titulo, (nivel, texto) in items:
            f = QFrame()
            f.setObjectName("sub")
            l = QVBoxLayout(f)
            l.setContentsMargins(16, 14, 16, 14)
            l.setSpacing(6)
            t = QLabel(titulo)
            t.setObjectName("subtitulo")
            e = QLabel(texto)
            e.setWordWrap(True)
            e.setProperty("nivel", nivel)
            l.addWidget(t)
            l.addWidget(e)
            l.addStretch()
            fila.addWidget(f, 1)
        lay.addLayout(fila)

    # ---------- Alertas ----------
    def crear_alertas(self, actual, diario):
        lay = self.nueva_tarjeta("⚠️  Alertas y recomendaciones", "Alertas")
        for nivel, texto in generar_alertas(actual, diario):
            f = QFrame()
            f.setObjectName("sub")
            l = QVBoxLayout(f)
            l.setContentsMargins(16, 10, 16, 10)
            e = QLabel(texto)
            e.setWordWrap(True)
            e.setProperty("nivel", nivel)
            l.addWidget(e)
            lay.addWidget(f)

    # ==========================================================
    # DETALLE DE UN DÍA
    # ==========================================================

    def mostrar_detalle_dia(self, indice, diario, horario):
        fecha = diario["time"][indice]
        self.ventana_detalle = VentanaDetalleDia(
            self, fecha, indice, diario, horario
        )
        self.ventana_detalle.show()
        self.ventana_detalle.raise_()
        self.ventana_detalle.activateWindow()

    # ==========================================================
    # ESTADOS (inicial, cargando, error)
    # ==========================================================

    def mostrar_mensaje(self, texto, nombre="texto2", boton=None):
        self.limpiar_contenido()
        self.secciones.clear()
        lay = self.nueva_tarjeta()
        m = QLabel(texto)
        m.setObjectName(nombre)
        m.setAlignment(CENTRO)
        m.setWordWrap(True)
        lay.addWidget(m)
        if boton:
            b = QPushButton(boton[0])
            b.setObjectName("primario")
            b.setCursor(MANO)
            b.clicked.connect(boton[1])
            lay.addWidget(b, 0, CENTRO)
        self.layout_contenido.addStretch()

    def mostrar_mensaje_inicial(self):
        self.mostrar_mensaje(
            "📍\n\nElegí una provincia y buscá tu localidad para comenzar.",
            "subtitulo",
        )

    def mostrar_cargando(self):
        self.mostrar_mensaje("⏳  Cargando el pronóstico...", "subtitulo")

    def mostrar_error(self, mensaje):
        self.mostrar_mensaje(
            "❌ No se pudo obtener el clima.\n\n" + mensaje,
            "error", ("🔄  Reintentar", self.cargar_clima),
        )

    def limpiar_contenido(self):
        while self.layout_contenido.count():
            item = self.layout_contenido.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.secciones = {}

    # ==========================================================
    # NAVEGACIÓN
    # ==========================================================

    def ir_a_seccion(self, nombre):
        widget = self.secciones.get(nombre)
        if widget is None:
            return
        self.layout_contenido.activate()
        barra = self.scroll.verticalScrollBar()
        objetivo = max(0, min(widget.y() - 4, barra.maximum()))
        self._anim = QPropertyAnimation(barra, b"value", self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(barra.value())
        self._anim.setEndValue(objetivo)
        self._anim.start()


# ==============================================================
# EJECUTAR
# ==============================================================

if __name__ == "__main__":

    # Para que Windows use el ícono de la app en la barra de tareas
    # (y no el de python.exe) cuando se ejecuta desde el código fuente.
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NOMBRE)
    app.setQuitOnLastWindowClosed(False)  # sigue viva en la bandeja
    app.setWindowIcon(cargar_icono_app())

    ventana = EstacionMeteorologica()
    ventana.showMaximized()

    sys.exit(app.exec())