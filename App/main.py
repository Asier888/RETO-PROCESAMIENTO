# =============================================================================
# main.py — Concentrador FastAPI para el Parque Eólico
# =============================================================================
# Ejecución: uvicorn main:app --reload --port 8000
# =============================================================================

import os
from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# -----------------------------------------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------------------------------------
API_KEY = os.getenv("EOLICO_API_KEY", "clave-secreta-parque-eolico")
DATABASE_URL = "sqlite:///./parque_eolico.db"

# -----------------------------------------------------------------------------
# BASE DE DATOS — SQLAlchemy
# -----------------------------------------------------------------------------
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class LecturaDB(Base):
    """Tabla SQLite para persistir lecturas válidas."""
    __tablename__ = "lecturas"

    id = Column(Integer, primary_key=True, index=True)
    id_generador = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    potencia_kw = Column(Float, nullable=False)
    estado = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency de FastAPI: abre y cierra la sesión de BD por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------------------------
# MODELO PYDANTIC — Validación de datos entrantes
# -----------------------------------------------------------------------------
class Lectura(BaseModel):
    """
    Modelo de datos para la lectura de un aerogenerador.

    Restricciones de negocio:
    - id_generador: entero entre 1 y 10 (solo hay 10 turbinas)
    - potencia_kw:  float no negativo (no se puede generar energía negativa)
    - estado:       solo se aceptan los valores del Literal
    - timestamp:    con zona horaria UTC
    """
    id_generador: int = Field(..., ge=1, le=10, description="ID del aerogenerador (1-10)")
    timestamp: datetime = Field(..., description="Marca de tiempo ISO 8601")
    potencia_kw: float = Field(..., ge=0.0, description="Potencia generada en kW (≥ 0)")
    estado: Literal["operativo", "mantenimiento", "avería"] = Field(
        ..., description="Estado operacional de la turbina"
    )

    @field_validator("timestamp")
    @classmethod
    def timestamp_debe_tener_tz(cls, v: datetime) -> datetime:
        """Asegura que el timestamp tenga información de zona horaria."""
        if v.tzinfo is None:
            raise ValueError("El timestamp debe incluir zona horaria (ej. UTC).")
        return v


# -----------------------------------------------------------------------------
# SEGURIDAD — Validación de API Key
# -----------------------------------------------------------------------------
def verificar_api_key(x_api_key: str = Header(..., description="Clave de API del parque")):
    """
    Dependency de FastAPI que comprueba la cabecera X-Api-Key.
    Lanza 401 si la clave no coincide.
    """
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida o ausente.")
    return x_api_key


# -----------------------------------------------------------------------------
# APLICACIÓN FASTAPI
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Concentrador Parque Eólico",
    description="Recibe, valida y agrega lecturas de los 10 aerogeneradores.",
    version="1.0.0",
)


# --- Endpoint de ingesta -------------------------------------------------------
@app.post(
    "/ingesta",
    summary="Ingestar lectura de un generador",
    status_code=201,
    dependencies=[Depends(verificar_api_key)],
)
def ingestar_lectura(lectura: Lectura, db: Session = Depends(get_db)):
    """
    Recibe una lectura JSON, la valida con Pydantic y la persiste en SQLite.
    Solo las lecturas que superen la validación llegan a la base de datos.
    """
    registro = LecturaDB(
        id_generador=lectura.id_generador,
        timestamp=lectura.timestamp.astimezone(timezone.utc).replace(tzinfo=None),
        potencia_kw=lectura.potencia_kw,
        estado=lectura.estado,
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return {
        "ok": True,
        "mensaje": f"Lectura del generador {lectura.id_generador} almacenada (id={registro.id}).",
    }


# --- Endpoint de estadísticas --------------------------------------------------
@app.get(
    "/estadisticas",
    summary="Estadísticas del parque en el último minuto",
    dependencies=[Depends(verificar_api_key)],
)
def obtener_estadisticas(db: Session = Depends(get_db)):
    """
    Consulta la base de datos y devuelve agregados del último minuto:
    - media de potencia de todo el parque
    - número de lecturas recibidas
    - potencia total del parque
    - media por generador

    La ventana temporal se calcula en Python y se pasa a SQLite como parámetro
    para mantener el código transparente y educativo.
    """
    ahora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hace_un_minuto = ahora_utc - timedelta(minutes=1)

    # Consulta principal: media y suma globales
    resultado = (
        db.query(
            func.avg(LecturaDB.potencia_kw).label("media_kw"),
            func.sum(LecturaDB.potencia_kw).label("total_kw"),
            func.count(LecturaDB.id).label("n_lecturas"),
        )
        .filter(LecturaDB.timestamp >= hace_un_minuto)
        .one()
    )

    # Consulta secundaria: media agrupada por generador
    por_generador = (
        db.query(
            LecturaDB.id_generador,
            func.avg(LecturaDB.potencia_kw).label("media_kw"),
            func.count(LecturaDB.id).label("n_lecturas"),
        )
        .filter(LecturaDB.timestamp >= hace_un_minuto)
        .group_by(LecturaDB.id_generador)
        .order_by(LecturaDB.id_generador)
        .all()
    )

    return {
        "ventana": "último minuto",
        "timestamp_consulta": ahora_utc.isoformat(),
        "parque": {
            "media_potencia_kw": round(resultado.media_kw or 0.0, 2),
            "potencia_total_kw": round(resultado.total_kw or 0.0, 2),
            "n_lecturas": resultado.n_lecturas or 0,
        },
        "por_generador": [
            {
                "id_generador": g.id_generador,
                "media_potencia_kw": round(g.media_kw, 2),
                "n_lecturas": g.n_lecturas,
            }
            for g in por_generador
        ],
    }


# --- Health check (sin autenticación) -----------------------------------------
@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
