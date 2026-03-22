# =============================================================================
# generator.py — Simulador de Aerogeneradores del Parque Eólico
# =============================================================================
# Ejecución (todos los generadores a la vez):  python generator.py
# Ejecución (un generador concreto):           python generator.py --id 3
# =============================================================================

import random
import threading
import time
import argparse
from datetime import datetime, timezone

import requests

# -----------------------------------------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------------------------------------
CONCENTRADOR_URL = "http://localhost:8000/ingesta"
API_KEY = "clave-secreta-parque-eolico"   # Debe coincidir con main.py
INTERVALO_SEGUNDOS = 2                    # Frecuencia de envío por generador
PROB_ERROR = 0.1                          # 10 % de probabilidad de dato erróneo

HEADERS = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}

# Rango de potencia realista para una turbina de 2 MW
POTENCIA_MIN_KW = 0.0
POTENCIA_MAX_KW = 2000.0

# Distribución de estados operativos (pesos relativos)
ESTADOS = ["operativo", "operativo", "operativo", "mantenimiento", "avería"]


# -----------------------------------------------------------------------------
# GENERADOR DE DATOS SINTÉTICOS
# -----------------------------------------------------------------------------
def generar_lectura_valida(id_generador: int) -> dict:
    """
    Produce un diccionario con datos plausibles para el generador indicado.
    La potencia sigue una distribución normal centrada en 1200 kW (viento medio),
    recortada al rango [0, 2000] kW para ser realista.
    """
    potencia = max(POTENCIA_MIN_KW, min(POTENCIA_MAX_KW, random.gauss(1200, 400)))

    # Si la turbina está en mantenimiento o avería, la potencia es 0
    estado = random.choice(ESTADOS)
    if estado != "operativo":
        potencia = 0.0

    return {
        "id_generador": id_generador,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "potencia_kw": round(potencia, 2),
        "estado": estado,
    }


def generar_lectura_erronea(id_generador: int) -> dict:
    """
    Produce intencionadamente un dato mal formado para probar la validación
    del Concentrador. Elige aleatoriamente qué campo corromper.
    """
    tipo_error = random.choice(["potencia_string", "id_fuera_rango", "estado_invalido", "timestamp_sin_tz"])

    base = {
        "id_generador": id_generador,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "potencia_kw": round(random.uniform(POTENCIA_MIN_KW, POTENCIA_MAX_KW), 2),
        "estado": "operativo",
    }

    if tipo_error == "potencia_string":
        base["potencia_kw"] = "MUCHO_VIENTO"          # string en campo float
    elif tipo_error == "id_fuera_rango":
        base["id_generador"] = random.choice([0, 11, 99])  # fuera de [1, 10]
    elif tipo_error == "estado_invalido":
        base["estado"] = "girando_rapido"              # valor no permitido
    elif tipo_error == "timestamp_sin_tz":
        base["timestamp"] = datetime.now().isoformat() # sin zona horaria

    return base


# -----------------------------------------------------------------------------
# BUCLE PRINCIPAL DE UN GENERADOR
# -----------------------------------------------------------------------------
def ejecutar_generador(id_generador: int):
    """
    Bucle infinito que, cada INTERVALO_SEGUNDOS segundos:
    1. Decide si envía un dato válido o erróneo (según PROB_ERROR).
    2. Serializa el payload a JSON y lo POST-ea al Concentrador.
    3. Imprime el resultado en consola para facilitar la depuración.
    """
    nombre = f"[Gen-{id_generador:02d}]"
    print(f"{nombre} Iniciado. Enviando cada {INTERVALO_SEGUNDOS}s. (PROB_ERROR={PROB_ERROR})")

    while True:
        es_error = random.random() < PROB_ERROR

        if es_error:
            payload = generar_lectura_erronea(id_generador)
            etiqueta = "⚠ ERROR"
        else:
            payload = generar_lectura_valida(id_generador)
            etiqueta = "✓ OK   "

        try:
            respuesta = requests.post(CONCENTRADOR_URL, json=payload, headers=HEADERS, timeout=5)
            estado_http = respuesta.status_code

            if estado_http == 201:
                print(f"{nombre} {etiqueta} | {payload['potencia_kw']:>8.1f} kW | "
                      f"{payload['estado']:<14} → {estado_http} Aceptado")
            else:
                detalle = respuesta.json().get("detail", respuesta.text)[:80]
                print(f"{nombre} {etiqueta} | payload={str(payload)[:60]} "
                      f"→ {estado_http} Rechazado: {detalle}")

        except requests.exceptions.ConnectionError:
            print(f"{nombre} ✗ Sin conexión al Concentrador ({CONCENTRADOR_URL}). "
                  "¿Está uvicorn en marcha?")
        except Exception as exc:
            print(f"{nombre} ✗ Error inesperado: {exc}")

        time.sleep(INTERVALO_SEGUNDOS)


# -----------------------------------------------------------------------------
# PUNTO DE ENTRADA
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulador de aerogeneradores.")
    parser.add_argument(
        "--id",
        type=int,
        default=None,
        help="ID de un generador concreto (1-10). "
             "Si se omite, lanza los 10 generadores en hilos separados.",
    )
    args = parser.parse_args()

    if args.id is not None:
        # ── Modo individual: un solo generador en el hilo principal ──────────
        if not (1 <= args.id <= 10):
            print("Error: el ID debe estar entre 1 y 10.")
            raise SystemExit(1)
        ejecutar_generador(args.id)
    else:
        # ── Modo completo: 10 generadores, cada uno en su propio hilo ────────
        print("═" * 60)
        print("  PARQUE EÓLICO — Lanzando 10 generadores en paralelo")
        print(f"  Destino : {CONCENTRADOR_URL}")
        print(f"  PROB_ERROR: {PROB_ERROR}  |  Intervalo: {INTERVALO_SEGUNDOS}s")
        print("═" * 60)

        hilos = []
        for gen_id in range(1, 11):
            hilo = threading.Thread(
                target=ejecutar_generador,
                args=(gen_id,),
                daemon=True,          # El hilo muere cuando el proceso principal muere
                name=f"generador-{gen_id:02d}",
            )
            hilos.append(hilo)
            hilo.start()
            time.sleep(0.1)           # Pequeño escalonado para no saturar el arranque

        print("\nTodos los generadores en marcha. Pulsa Ctrl+C para detener.\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nSimulación detenida por el usuario.")
