# concentrador.py
# Concentrador del parque eólico: recibe, valida y agrega datos de los 10 generadores.
# Uso: python -m uvicorn concentrador:app --reload

import sqlite3
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from datetime import datetime, timezone
from collections import defaultdict
from modelos import LecturaGenerador

app = FastAPI(title="Concentrador Parque Eólico")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_VALIDA = "clave-secreta-123"
DB_FICHERO = "parque_eolico.db"

# Última lectura por generador (para el dashboard, en memoria)
ultimo_estado: dict[str, dict] = {}


# ── Base de datos ──────────────────────────────────────────────────────────────

def conectar():
    """Devuelve una conexión a SQLite."""
    conn = sqlite3.connect(DB_FICHERO)
    conn.row_factory = sqlite3.Row  # permite acceder por nombre de columna
    return conn

def inicializar_db():
    """Crea las tablas si no existen."""
    conn = conectar()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS lecturas_validas (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            generador_id        TEXT,
            timestamp           TEXT,
            potencia_kw         REAL,
            velocidad_viento_ms REAL,
            temperatura_c       REAL,
            estado              TEXT,
            recibido_en         TEXT
        );

        CREATE TABLE IF NOT EXISTS lecturas_invalidas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            generador_id TEXT,
            errores      TEXT,
            datos_raw    TEXT,
            recibido_en  TEXT
        );
    """)
    conn.commit()
    conn.close()
    print("Base de datos lista:", DB_FICHERO)

inicializar_db()


# ── Seguridad ──────────────────────────────────────────────────────────────────

def verificar_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY_VALIDA:
        raise HTTPException(status_code=401, detail="API Key invalida")


# ── Endpoint: recibir lectura ─────────────────────────────────────────────────

@app.post("/lectura")
def recibir_lectura(datos: dict, x_api_key: str = Header(...)):
    verificar_api_key(x_api_key)
    ahora = datetime.now(timezone.utc).isoformat()

    try:
        lectura = LecturaGenerador(**datos)
    except ValidationError as e:
        errores = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        conn = conectar()
        conn.execute(
            "INSERT INTO lecturas_invalidas (generador_id, errores, datos_raw, recibido_en) VALUES (?,?,?,?)",
            (datos.get("generador_id", "?"), str(errores), str(datos), ahora)
        )
        conn.commit()
        conn.close()
        raise HTTPException(status_code=422, detail={"errores": errores})

    conn = conectar()
    conn.execute(
        """INSERT INTO lecturas_validas
           (generador_id, timestamp, potencia_kw, velocidad_viento_ms, temperatura_c, estado, recibido_en)
           VALUES (?,?,?,?,?,?,?)""",
        (lectura.generador_id, lectura.timestamp, lectura.potencia_kw,
         lectura.velocidad_viento_ms, lectura.temperatura_c, lectura.estado, ahora)
    )
    conn.commit()
    conn.close()

    ultimo_estado[lectura.generador_id] = lectura.model_dump()
    ultimo_estado[lectura.generador_id]["recibido_en"] = ahora

    return {"ok": True, "generador": lectura.generador_id}


# ── Endpoint: estado actual ────────────────────────────────────────────────────

@app.get("/estado")
def estado_parque(x_api_key: str = Header(...)):
    verificar_api_key(x_api_key)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "generadores_activos": len(ultimo_estado),
        "potencia_total_kw": round(sum(g["potencia_kw"] for g in ultimo_estado.values()), 1),
        "generadores": ultimo_estado,
    }


# ── Endpoint: agregacion ───────────────────────────────────────────────────────

@app.get("/agregacion")
def agregacion(x_api_key: str = Header(...), ultimos_n: int = 50):
    verificar_api_key(x_api_key)
    conn = conectar()
    filas = conn.execute(
        "SELECT * FROM lecturas_validas ORDER BY id DESC LIMIT ?", (ultimos_n,)
    ).fetchall()
    conn.close()

    if not filas:
        return {"mensaje": "Sin datos todavia"}

    potencias = [f["potencia_kw"] for f in filas]
    vientos   = [f["velocidad_viento_ms"] for f in filas]
    por_generador = defaultdict(list)
    for f in filas:
        por_generador[f["generador_id"]].append(f["potencia_kw"])

    return {
        "lecturas_analizadas": len(filas),
        "potencia_media_kw":   round(sum(potencias) / len(potencias), 1),
        "potencia_max_kw":     round(max(potencias), 1),
        "potencia_min_kw":     round(min(potencias), 1),
        "viento_medio_ms":     round(sum(vientos) / len(vientos), 1),
        "media_por_generador": {
            gen_id: round(sum(vals) / len(vals), 1)
            for gen_id, vals in sorted(por_generador.items())
        },
    }


# ── Endpoint: calidad de datos ─────────────────────────────────────────────────

@app.get("/calidad")
def calidad_datos(x_api_key: str = Header(...)):
    verificar_api_key(x_api_key)
    conn = conectar()
    validas    = conn.execute("SELECT COUNT(*) FROM lecturas_validas").fetchone()[0]
    rechazadas = conn.execute("SELECT COUNT(*) FROM lecturas_invalidas").fetchone()[0]
    ultimos_errores = conn.execute(
        "SELECT generador_id, errores, recibido_en FROM lecturas_invalidas ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()

    total = validas + rechazadas
    return {
        "total_recibidas":    total,
        "validas":            validas,
        "rechazadas":         rechazadas,
        "porcentaje_calidad": round(100 * validas / total, 1) if total > 0 else 100,
        "ultimos_errores":    [dict(e) for e in ultimos_errores],
    }
