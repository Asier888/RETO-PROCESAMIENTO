# concentrador.py
# Concentrador del parque eólico: recibe, valida y agrega datos de los 10 generadores.
# Uso: uvicorn concentrador:app --reload

from fastapi import FastAPI, Header, HTTPException
from pydantic import ValidationError
from datetime import datetime, timezone
from collections import defaultdict
from modelos import LecturaGenerador

app = FastAPI(title="Concentrador Parque Eólico")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Almacenamiento en memoria ──────────────────────────────────────────────────

lecturas_validas: list[dict] = []       # Todas las lecturas correctas
lecturas_invalidas: list[dict] = []     # Lecturas rechazadas

# Última lectura por generador (para el dashboard)
ultimo_estado: dict[str, dict] = {}

API_KEY_VALIDA = "clave-secreta-123"


# ── Seguridad: verificar API Key ───────────────────────────────────────────────

def verificar_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY_VALIDA:
        raise HTTPException(status_code=401, detail="API Key inválida")


# ── Endpoint principal: recibir lecturas ──────────────────────────────────────

@app.post("/lectura")
def recibir_lectura(datos: dict, x_api_key: str = Header(...)):
    """Recibe una lectura de un generador, la valida y la almacena."""
    
    # 1. Verificar autenticación
    verificar_api_key(x_api_key)

    # 2. Validar con el modelo Pydantic
    try:
        lectura = LecturaGenerador(**datos)
    except ValidationError as e:
        errores = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        
        # Guardar la lectura inválida para registro
        lecturas_invalidas.append({
            "datos_recibidos": datos,
            "errores": errores,
            "timestamp_recepcion": datetime.now(timezone.utc).isoformat(),
        })
        
        raise HTTPException(status_code=422, detail={"errores": errores})

    # 3. Guardar lectura válida
    lectura_dict = lectura.model_dump()
    lectura_dict["timestamp_recepcion"] = datetime.now(timezone.utc).isoformat()
    lecturas_validas.append(lectura_dict)
    
    # Actualizar estado del generador
    ultimo_estado[lectura.generador_id] = lectura_dict

    return {"ok": True, "generador": lectura.generador_id}


# ── Endpoint: estado actual del parque ────────────────────────────────────────

@app.get("/estado")
def estado_parque(x_api_key: str = Header(...)):
    """Devuelve el estado actual de todos los generadores."""
    verificar_api_key(x_api_key)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "generadores_activos": len(ultimo_estado),
        "potencia_total_kw": round(sum(g["potencia_kw"] for g in ultimo_estado.values()), 1),
        "generadores": ultimo_estado,
    }


# ── Endpoint: agregación (media de los últimos N minutos) ─────────────────────

@app.get("/agregacion")
def agregacion(x_api_key: str = Header(...), ultimos_n: int = 50):
    """Calcula estadísticas agregadas de las últimas N lecturas válidas."""
    verificar_api_key(x_api_key)
    
    recientes = lecturas_validas[-ultimos_n:]  # Últimas N lecturas
    
    if not recientes:
        return {"mensaje": "Sin datos todavía"}

    potencias = [l["potencia_kw"] for l in recientes]
    vientos = [l["velocidad_viento_ms"] for l in recientes]

    # Agrupar por generador
    por_generador = defaultdict(list)
    for l in recientes:
        por_generador[l["generador_id"]].append(l["potencia_kw"])

    return {
        "lecturas_analizadas": len(recientes),
        "potencia_media_kw": round(sum(potencias) / len(potencias), 1),
        "potencia_max_kw": round(max(potencias), 1),
        "potencia_min_kw": round(min(potencias), 1),
        "viento_medio_ms": round(sum(vientos) / len(vientos), 1),
        "media_por_generador": {
            gen_id: round(sum(vals) / len(vals), 1)
            for gen_id, vals in sorted(por_generador.items())
        },
    }


# ── Endpoint: estadísticas de calidad de datos ────────────────────────────────

@app.get("/calidad")
def calidad_datos(x_api_key: str = Header(...)):
    """Muestra cuántas lecturas fueron válidas vs rechazadas."""
    verificar_api_key(x_api_key)
    
    total = len(lecturas_validas) + len(lecturas_invalidas)
    return {
        "total_recibidas": total,
        "validas": len(lecturas_validas),
        "rechazadas": len(lecturas_invalidas),
        "porcentaje_calidad": round(100 * len(lecturas_validas) / total, 1) if total > 0 else 100,
        "ultimos_errores": lecturas_invalidas[-5:],  # últimos 5 errores
    }
