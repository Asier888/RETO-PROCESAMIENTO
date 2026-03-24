# 🌬️ Sistema de Monitorización de Parque Eólico

> Proyecto de procesamiento de datos IoT para un parque eólico de 10 aerogeneradores, implementado con FastAPI, SQLAlchemy, Streamlit y Python puro.

---

## 👥 Miembros del Equipo

| Nombres |
|--------|
| *ALAIA YEREGUI* | 
| *ASIER SÁNCHEZ* | 


---

## 📋 Descripción del Proyecto

El sistema simula un parque eólico con 10 aerogeneradores que generan datos sintéticos de producción de energía. Un concentrador centraliza, valida y almacena las lecturas, y un dashboard en tiempo real muestra el estado del parque.

**Componentes:**
- `main.py` — Concentrador FastAPI + SQLite (backend)
- `generator.py` — Simulador de los 10 aerogeneradores
- `dashboard.py` — Dashboard Streamlit en tiempo real

---

## 🗺️ Pasos Seguidos

### 1. Diseño del Modelo de Datos
Definimos la clase `Lectura` con Pydantic v2, estableciendo:
- Validación de rangos (`id_generador` entre 1 y 10)
- Tipos estrictos (`potencia_kw` float ≥ 0)
- Estados permitidos con `Literal["operativo", "mantenimiento", "avería"]`
- Zona horaria obligatoria en `timestamp`

### 2. Implementación del Concentrador (FastAPI)
- Endpoint `POST /ingesta` con validación automática vía Pydantic
- Persistencia en SQLite mediante SQLAlchemy ORM
- Endpoint `GET /estadisticas` con consultas SQL agregadas (ventana de 1 minuto)
- Seguridad mediante `API_KEY` en cabeceras HTTP (`X-Api-Key`)

### 3. Simulador de Generadores
- Función de datos válidos con distribución gaussiana realista `N(1200, 400) kW`
- Función de datos erróneos con 4 tipos de error diferentes
- Variable `PROB_ERROR = 0.1` (10% de probabilidad de error)
- Soporte multihilo con `threading` para simular los 10 generadores simultáneamente

### 4. Dashboard Streamlit
- Consulta periódica al endpoint `/estadisticas` cada 3 segundos
- Historial acumulado en `st.session_state` con `deque(maxlen=30)`
- Métricas en tiempo real, gráfico de línea y tabla por generador
- Semáforo visual (🟢/🟡/🔴) según la capacidad utilizada del parque

---

## 🚀 Instrucciones de Uso

### Requisitos previos

```bash
pip install fastapi uvicorn sqlalchemy requests streamlit pydantic pandas
```

### Paso 1 — Arrancar el Concentrador

```bash
# Terminal 1: desde la carpeta donde están los archivos .py
python -m uvicorn main:app --reload --port 8000
```

Verificar que funciona:
```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

### Paso 2 — Arrancar los Generadores

```bash
# Terminal 2: lanza los 10 generadores en hilos paralelos
python generator.py

# Alternativamente, un generador concreto:
python generator.py --id 5
```

### Paso 3 — Abrir el Dashboard

```bash
# Terminal 3:
python -m streamlit run dashboard.py
```

Abre el navegador en `http://localhost:8501`

### Documentación interactiva de la API

Con el concentrador en marcha, visita:
- `http://localhost:8000/docs` — Swagger UI
- `http://localhost:8000/redoc` — ReDoc

---

## ⚠️ Problemas / Retos Encontrados

### 1. Zona horaria en SQLite
SQLite no almacena zona horaria. Solución: convertir siempre a UTC naive antes de persistir y reconstruir la ventana temporal con `datetime.now(timezone.utc).replace(tzinfo=None)`.

### 2. PATH de ejecutables en Windows
`streamlit` y `uvicorn` instalados con `pip` no siempre quedan en el PATH. Solución: usar `python -m streamlit run` y `python -m uvicorn` en lugar de los ejecutables directamente.

### 3. Thread-safety en SQLAlchemy con SQLite
SQLite por defecto no permite acceso desde múltiples hilos. Solución: pasar `connect_args={"check_same_thread": False}` en `create_engine` y usar el sistema de `Depends` de FastAPI para una sesión por petición.

### 4. Validación de timestamps sin TZ
Pydantic acepta strings ISO 8601 sin zona horaria por defecto. Solución: añadir un `@field_validator` personalizado que lanza `ValueError` si `tzinfo is None`.

---

## 💡 Posibles Vías de Mejora

### Corto plazo
- **Autenticación JWT**: reemplazar la API Key estática por tokens con expiración
- **Alertas**: enviar notificaciones (email/Slack) cuando una turbina entra en estado de avería
- **Tests unitarios**: añadir pytest con fixtures para los endpoints y el modelo

### Medio plazo
- **Cola de mensajes**: sustituir HTTP directo por MQTT o RabbitMQ para desacoplar generadores del concentrador
- **Base de datos en serie temporal**: migrar de SQLite a TimescaleDB o InfluxDB para consultas temporales más eficientes
- **Agregados configurables**: permitir ventanas de 5 min, 15 min, 1 hora vía parámetros

### Largo plazo
- **Despliegue con Docker Compose**: contenedorizar los tres servicios
- **Machine Learning**: modelos predictivos de mantenimiento basados en el histórico
- **API WebSocket**: push de datos al dashboard en lugar de polling

---

## 🔄 Alternativas Posibles

| Componente | Solución Actual | Alternativas |
|-----------|----------------|--------------|
| Framework API | FastAPI | Flask, Django REST, Litestar |
| Base de datos | SQLite + SQLAlchemy | PostgreSQL, InfluxDB, TimescaleDB |
| Transporte de datos | HTTP REST | MQTT, AMQP (RabbitMQ), WebSockets |
| Dashboard | Streamlit | Grafana, Dash (Plotly), Panel |
| Validación | Pydantic v2 | Marshmallow, attrs, dataclasses |
| Simulación paralela | threading | asyncio, multiprocessing, Celery |

---

## 📁 Estructura del Proyecto

```
parque_eolico/
├── main.py           # Concentrador FastAPI + SQLite
├── generator.py      # Simulador de los 10 aerogeneradores
├── dashboard.py      # Dashboard Streamlit
├── parque_eolico.db  # Base de datos SQLite (se crea automáticamente)
└── README.md         # Este archivo
```

---

## 📐 Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        PARQUE EÓLICO                            │
│                                                                 │
│  ┌──────────┐  POST /ingesta   ┌──────────────────────────────┐ │
│  │Gen-01..10│ ───────────────► │  main.py (FastAPI)           │ │
│  │          │  (X-Api-Key)     │  ┌────────┐  ┌────────────┐  │ │
│  │ PROB_ERROR│                 │  │Pydantic│  │SQLAlchemy  │  │ │
│  │  = 0.1   │                 │  │Validar │→ │SQLite DB   │  │ │
│  └──────────┘                 │  └────────┘  └────────────┘  │ │
│                               └──────────────────────────────┘ │
│                                          │ GET /estadisticas    │
│                               ┌──────────▼──────────────────┐  │
│                               │  dashboard.py (Streamlit)   │  │
│                               │  Métricas + Gráfico + Tabla │  │
│                               └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

*Proyecto educativo de IoT con Python — FastAPI · SQLAlchemy · Streamlit · Pydantic*
