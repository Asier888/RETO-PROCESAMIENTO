# =============================================================================
# dashboard.py — Dashboard Streamlit para el Parque Eólico
# =============================================================================
# Ejecución: streamlit run dashboard.py
# =============================================================================

import time
from collections import deque
from datetime import datetime

import requests
import streamlit as st

# -----------------------------------------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------------------------------------
CONCENTRADOR_URL = "http://localhost:8000"
API_KEY = "clave-secreta-parque-eolico"
HEADERS = {"X-Api-Key": API_KEY}
REFRESCO_SEGUNDOS = 3          # Con qué frecuencia se actualiza el dashboard
HISTORIAL_PUNTOS = 30          # Cuántos puntos conserva el gráfico de línea
POTENCIA_MAX_PARQUE_KW = 20000 # 10 turbinas × 2 MW = 20 000 kW (referencia 100 %)

# -----------------------------------------------------------------------------
# ESTADO DE SESIÓN — historial en memoria mientras la app esté abierta
# -----------------------------------------------------------------------------
if "historial_tiempo" not in st.session_state:
    st.session_state.historial_tiempo = deque(maxlen=HISTORIAL_PUNTOS)
if "historial_potencia" not in st.session_state:
    st.session_state.historial_potencia = deque(maxlen=HISTORIAL_PUNTOS)


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def consultar_estadisticas() -> dict | None:
    """Llama a GET /estadisticas y devuelve el JSON o None si falla."""
    try:
        r = requests.get(f"{CONCENTRADOR_URL}/estadisticas", headers=HEADERS, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as exc:
        st.error(f"Error al consultar el concentrador: {exc}")
        return None


def color_estado(potencia_kw: float) -> str:
    """Devuelve un color semáforo según la potencia media del parque."""
    porcentaje = potencia_kw / POTENCIA_MAX_PARQUE_KW * 100
    if porcentaje >= 60:
        return "🟢"
    elif porcentaje >= 30:
        return "🟡"
    else:
        return "🔴"


# -----------------------------------------------------------------------------
# LAYOUT DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Parque Eólico — Dashboard",
    page_icon="🌬️",
    layout="wide",
)

st.title("🌬️ Dashboard — Parque Eólico")
st.caption(
    f"Datos actualizados cada {REFRESCO_SEGUNDOS}s · "
    f"Concentrador: `{CONCENTRADOR_URL}` · Ventana: último minuto"
)

# Contenedores reutilizables para evitar duplicar widgets en cada refresco
placeholder_estado = st.empty()
placeholder_metricas = st.empty()
placeholder_grafico = st.empty()
placeholder_tabla = st.empty()

# -----------------------------------------------------------------------------
# BUCLE DE REFRESCO
# -----------------------------------------------------------------------------
while True:
    datos = consultar_estadisticas()

    if datos is None:
        placeholder_estado.error(
            "⚠️ No se puede conectar al Concentrador. "
            "Asegúrate de que `uvicorn main:app` está corriendo en el puerto 8000."
        )
    else:
        parque = datos["parque"]
        media_kw = parque["media_potencia_kw"]
        total_kw = parque["potencia_total_kw"]
        n_lecturas = parque["n_lecturas"]
        ts = datetime.now().strftime("%H:%M:%S")

        # Acumular historial
        st.session_state.historial_tiempo.append(ts)
        st.session_state.historial_potencia.append(media_kw)

        placeholder_estado.success(
            f"{color_estado(media_kw)}  Estado del parque — {ts}"
        )

        # ── Fila de métricas ──────────────────────────────────────────────
        with placeholder_metricas.container():
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(
                label="⚡ Media potencia parque",
                value=f"{media_kw:,.1f} kW",
                help="Media de todos los generadores en el último minuto",
            )
            c2.metric(
                label="🔋 Potencia total",
                value=f"{total_kw:,.1f} kW",
                help="Suma de potencias en el último minuto",
            )
            c3.metric(
                label="📊 Lecturas recibidas",
                value=n_lecturas,
                help="Número de lecturas válidas en el último minuto",
            )
            capacidad_pct = round(media_kw / POTENCIA_MAX_PARQUE_KW * 100, 1)
            c4.metric(
                label="📈 Capacidad utilizada",
                value=f"{capacidad_pct} %",
                help=f"Respecto al máximo teórico de {POTENCIA_MAX_PARQUE_KW:,} kW",
            )

        # ── Gráfico de línea histórico ────────────────────────────────────
        with placeholder_grafico.container():
            st.subheader("Evolución media de potencia del parque (último minuto)")
            if len(st.session_state.historial_potencia) > 1:
                chart_data = {
                    "Hora": list(st.session_state.historial_tiempo),
                    "Media kW": list(st.session_state.historial_potencia),
                }
                # st.line_chart acepta dict directamente con el parámetro x/y
                import pandas as pd
                df = pd.DataFrame(chart_data).set_index("Hora")
                st.line_chart(df, height=300)
            else:
                st.info("Esperando más datos para mostrar el gráfico…")

        # ── Tabla de generadores ──────────────────────────────────────────
        with placeholder_tabla.container():
            st.subheader("Detalle por generador (último minuto)")
            generadores = datos.get("por_generador", [])
            if generadores:
                import pandas as pd
                df_gen = pd.DataFrame(generadores).rename(columns={
                    "id_generador": "Generador",
                    "media_potencia_kw": "Media kW",
                    "n_lecturas": "Lecturas",
                })
                df_gen["Generador"] = df_gen["Generador"].apply(lambda x: f"Turbina {x:02d}")
                st.dataframe(
                    df_gen,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("Sin datos de generadores individuales aún.")

    time.sleep(REFRESCO_SEGUNDOS)
    st.rerun()
