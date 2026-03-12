# modelos.py
# Modelo de datos del parque eólico usando Pydantic

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Literal

class LecturaGenerador(BaseModel):
    """Representa una lectura de un generador eólico."""
    
    generador_id: str                        # Ej: "GEN-01"
    timestamp: str                           # Fecha y hora ISO8601
    potencia_kw: float                       # Potencia actual (kW)
    velocidad_viento_ms: float               # Velocidad del viento (m/s)
    temperatura_c: float                     # Temperatura del generador (°C)
    estado: Literal["online", "error"]       # Estado operativo
    es_dato_erroneo: bool = False            # True si fue inyectado como error

    @field_validator("potencia_kw")
    @classmethod
    def validar_potencia(cls, v):
        if v < 0 or v > 5000:
            raise ValueError(f"Potencia fuera de rango: {v} kW (debe ser 0-5000)")
        return v

    @field_validator("velocidad_viento_ms")
    @classmethod
    def validar_viento(cls, v):
        if v < 0 or v > 40:
            raise ValueError(f"Velocidad de viento inválida: {v} m/s (debe ser 0-40)")
        return v

    @field_validator("temperatura_c")
    @classmethod
    def validar_temperatura(cls, v):
        if v < -20 or v > 120:
            raise ValueError(f"Temperatura fuera de rango: {v} °C (debe ser -20 a 120)")
        return v
