# generador.py
# Simula un generador eólico que envía datos al concentrador.
# Uso: python generador.py GEN-01 --error-prob 0.1

import random
import time
import requests
import argparse
from datetime import datetime, timezone

# URL del concentrador
CONCENTRADOR_URL = "http://localhost:8000/lectura"
API_KEY = "clave-secreta-123"


def generar_lectura(generador_id: str, prob_error: float) -> dict:
    """Genera una lectura sintética. Con probabilidad prob_error, inyecta un dato erróneo."""
    
    es_error = random.random() < prob_error

    if es_error:
        # Dato erróneo: valores imposibles
        lectura = {
            "generador_id": generador_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "potencia_kw": random.choice([-500, 9999]),   # fuera de rango
            "velocidad_viento_ms": random.uniform(0, 15),
            "temperatura_c": random.choice([-99, 999]),   # fuera de rango
            "estado": "online",
            "es_dato_erroneo": True,
        }
    else:
        # Dato normal con variación realista
        viento = random.uniform(3, 18)
        potencia = min(3000, max(0, (viento - 3) / 9 * 3000 + random.gauss(0, 50)))
        lectura = {
            "generador_id": generador_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "potencia_kw": round(potencia, 1),
            "velocidad_viento_ms": round(viento, 1),
            "temperatura_c": round(random.uniform(40, 80), 1),
            "estado": "online",
            "es_dato_erroneo": False,
        }

    return lectura


def enviar_lectura(lectura: dict) -> bool:
    """Envía la lectura al concentrador. Devuelve True si fue aceptada."""
    try:
        respuesta = requests.post(
            CONCENTRADOR_URL,
            json=lectura,
            headers={"X-API-Key": API_KEY},
            timeout=5,
        )
        return respuesta.status_code == 200
    except requests.ConnectionError:
        print(f"[{lectura['generador_id']}] ERROR: No se puede conectar al concentrador")
        return False


def main():
    parser = argparse.ArgumentParser(description="Simulador de generador eólico")
    parser.add_argument("generador_id", help="ID del generador (ej: GEN-01)")
    parser.add_argument("--error-prob", type=float, default=0.1,
                        help="Probabilidad de dato erróneo (0.0 a 1.0, por defecto 0.1)")
    parser.add_argument("--intervalo", type=float, default=3.0,
                        help="Segundos entre lecturas (por defecto 3)")
    args = parser.parse_args()

    print(f"[{args.generador_id}] Iniciando — prob. error: {args.error_prob:.0%}, intervalo: {args.intervalo}s")

    enviados = 0
    rechazados = 0

    while True:
        lectura = generar_lectura(args.generador_id, args.error_prob)
        aceptado = enviar_lectura(lectura)
        enviados += 1

        if lectura["es_dato_erroneo"]:
            rechazados += 1
            print(f"[{args.generador_id}] 💥 Error inyectado — potencia={lectura['potencia_kw']} temp={lectura['temperatura_c']}")
        elif aceptado:
            print(f"[{args.generador_id}] ✓ {lectura['potencia_kw']} kW | {lectura['velocidad_viento_ms']} m/s")
        else:
            print(f"[{args.generador_id}] ✗ Lectura rechazada por el concentrador")

        time.sleep(args.intervalo)


if __name__ == "__main__":
    main()
