# 10 - Integraciones

---

## 1. Resumen de Integraciones

| Integración | Propósito | Obligatoria |
|-------------|-----------|-------------|
| **N8N** | Orquestador de workflows de IA | Sí |
| **Google Gemini** | Modelo de IA para corrección | Sí |
| **Google Drive/Sheets** | ~~Sincronización de archivos~~ | ❌ Eliminada |

### Decisiones Clave

| Aspecto | Decisión |
|---------|----------|
| **Workflows N8N** | 2 workflows: Corrección + Generación de rúbricas |
| **Modelo IA** | gemini-2.0-flash (predeterminado) |
| **Respuesta IA** | JSON estructurado estricto |
| **Reintentos** | 1 reintento automático, luego marcar fallida |
| **Timeout** | 60s nominal, extensible a 120s |
| **Health Check** | Sí, endpoint `/webhook/health` |

---

## 2. Arquitectura de Integración

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                        │
│                           (React + Vite)                                     │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ HTTP/REST
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                         │
│                            (FastAPI)                                         │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      CorreccionService                               │    │
│  │                                                                      │    │
│  │  1. Valida permisos del usuario                                     │    │
│  │  2. Obtiene API Key Gemini (desencriptada)                          │    │
│  │  3. Prepara payload para N8N                                        │    │
│  │  4. Envía request a webhook N8N                                     │    │
│  │  5. Procesa respuesta                                               │    │
│  │  6. Guarda corrección en BD                                         │    │
│  └──────────────────────────────────┬──────────────────────────────────┘    │
│                                     │                                        │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │ HTTP POST (webhook)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                N8N                                           │
│                         (Orquestador de IA)                                  │
│                                                                              │
│  ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐  │
│  │  Webhook Trigger  │────▶│  Construir Prompt │────▶│   Llamar Gemini   │  │
│  └───────────────────┘     └───────────────────┘     └─────────┬─────────┘  │
│                                                                 │            │
│                                                                 ▼            │
│  ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐  │
│  │  Retornar JSON    │◀────│  Parsear Response │◀────│  Respuesta Gemini │  │
│  └───────────────────┘     └───────────────────┘     └───────────────────┘  │
│                                                                              │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │ HTTPS
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GOOGLE GEMINI API                                   │
│                                                                              │
│  Endpoint: generativelanguage.googleapis.com                                │
│  Modelo: gemini-2.0-flash                                                   │
│  Auth: API Key por usuario                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. N8N - Configuración

### 3.1 Información General

| Aspecto | Especificación |
|---------|----------------|
| **Versión** | Latest (self-hosted) |
| **Puerto interno** | 5678 |
| **Base URL interna** | `http://n8n:5678` (Docker network) |
| **Autenticación** | Basic Auth (usuario/password) |
| **Timezone** | America/Argentina/Buenos_Aires |

### 3.2 Variables de Entorno N8N

```yaml
# docker-compose.yml - servicio n8n
environment:
  # Autenticación para panel de administración
  N8N_BASIC_AUTH_ACTIVE: "true"
  N8N_BASIC_AUTH_USER: "${N8N_USER}"
  N8N_BASIC_AUTH_PASSWORD: "${N8N_PASSWORD}"

  # Configuración de red
  N8N_HOST: "0.0.0.0"
  N8N_PORT: "5678"
  N8N_PROTOCOL: "http"
  WEBHOOK_URL: "http://n8n:5678"

  # Timezone
  GENERIC_TIMEZONE: "America/Argentina/Buenos_Aires"

  # Ejecuciones
  EXECUTIONS_DATA_PRUNE: "true"
  EXECUTIONS_DATA_MAX_AGE: "168"  # 7 días
```

### 3.3 URLs de Webhooks

El backend debe configurar estas URLs en su `.env`:

```bash
# URLs de webhooks N8N (red interna Docker)
N8N_BASE_URL=http://n8n:5678

# Webhooks específicos
N8N_WEBHOOK_CORRECCION=http://n8n:5678/webhook/corregir
N8N_WEBHOOK_RUBRICA=http://n8n:5678/webhook/generar-rubrica
N8N_WEBHOOK_HEALTH=http://n8n:5678/webhook/health
```

---

## 4. Workflows de N8N

### 4.1 Workflow: Health Check

**Propósito:** Verificar que N8N está operativo y puede conectar con Gemini.

**Endpoint:** `POST /webhook/health`

**Request:**
```json
{
  "api_key": "AIza..."
}
```

**Response (éxito):**
```json
{
  "status": "ok",
  "n8n_version": "1.x.x",
  "gemini_available": true,
  "timestamp": "2026-01-24T10:30:00Z"
}
```

**Response (error Gemini):**
```json
{
  "status": "degraded",
  "n8n_version": "1.x.x",
  "gemini_available": false,
  "gemini_error": "API key inválida",
  "timestamp": "2026-01-24T10:30:00Z"
}
```

**Flujo del Workflow:**
```
1. Webhook Trigger (POST /webhook/health)
   │
   ▼
2. Extraer api_key del body
   │
   ▼
3. Llamar a Gemini con prompt simple: "Responde OK"
   │
   ├── Éxito ──▶ 4a. Retornar status: "ok", gemini_available: true
   │
   └── Error ──▶ 4b. Retornar status: "degraded", gemini_available: false
```

---

### 4.2 Workflow: Corrección de Entrega

**Propósito:** Evaluar código de un alumno usando una rúbrica y retornar calificación estructurada.

**Endpoint:** `POST /webhook/corregir`

**Request:**
```json
{
  "codigo": "// Código consolidado del alumno...\nclass MiClase {\n  ...\n}",
  "rubrica": {
    "nombre": "TP1 - Clases y Objetos",
    "tipo": "TP",
    "puntaje_maximo": 100,
    "criterios": [
      {
        "nombre": "Correctitud funcional",
        "descripcion": "El código compila y ejecuta correctamente",
        "puntaje_maximo": 40
      },
      {
        "nombre": "Diseño de clases",
        "descripcion": "Uso correcto de encapsulamiento, herencia si aplica",
        "puntaje_maximo": 30
      },
      {
        "nombre": "Buenas prácticas",
        "descripcion": "Nombres descriptivos, código limpio, sin código muerto",
        "puntaje_maximo": 30
      }
    ]
  },
  "api_key": "AIza...",
  "contexto": {
    "materia": "Programación I",
    "lenguaje": "Java"
  }
}
```

**Response (éxito):**
```json
{
  "success": true,
  "correccion": {
    "nota": 75,
    "criterios": [
      {
        "nombre": "Correctitud funcional",
        "puntaje_obtenido": 35,
        "puntaje_maximo": 40,
        "estado": "WARNING",
        "feedback": "El código compila pero hay un error en el método calcularTotal() que retorna null en vez de 0 cuando la lista está vacía."
      },
      {
        "nombre": "Diseño de clases",
        "puntaje_obtenido": 25,
        "puntaje_maximo": 30,
        "estado": "OK",
        "feedback": "Buen uso de encapsulamiento. Los atributos son privados y se acceden mediante getters/setters."
      },
      {
        "nombre": "Buenas prácticas",
        "puntaje_obtenido": 15,
        "puntaje_maximo": 30,
        "estado": "ERROR",
        "feedback": "Hay variables con nombres poco descriptivos (a, b, x). Se detectó código comentado que debería eliminarse."
      }
    ],
    "fortalezas": [
      "Estructura de clases bien organizada",
      "Uso correcto de constructores",
      "Manejo adecuado de excepciones en la lectura de archivos"
    ],
    "recomendaciones": [
      "Renombrar variables 'a' y 'b' por nombres descriptivos como 'cantidad' y 'precio'",
      "Eliminar el código comentado en líneas 45-52",
      "Agregar validación para lista vacía en calcularTotal()"
    ],
    "comentario_general": "Trabajo con buena base estructural pero con detalles importantes a corregir. El error en calcularTotal() puede causar NullPointerException en producción. Se recomienda revisar las buenas prácticas de naming."
  },
  "metadata": {
    "modelo": "gemini-2.0-flash",
    "tokens_entrada": 1250,
    "tokens_salida": 580,
    "tiempo_ms": 3200
  }
}
```

**Response (error):**
```json
{
  "success": false,
  "error": {
    "code": "GEMINI_ERROR",
    "message": "Error al procesar con Gemini: cuota excedida",
    "retry": false
  }
}
```

**Estados de Criterio:**

| Estado | Significado | Color UI |
|--------|-------------|----------|
| `OK` | Criterio cumplido satisfactoriamente (≥80% del puntaje) | Verde |
| `WARNING` | Criterio parcialmente cumplido (40-79% del puntaje) | Amarillo |
| `ERROR` | Criterio no cumplido (<40% del puntaje) | Rojo |

**Flujo del Workflow:**
```
1. Webhook Trigger (POST /webhook/corregir)
   │
   ▼
2. Validar campos requeridos (codigo, rubrica, api_key)
   │
   ▼
3. Construir prompt de corrección (ver sección 5.1)
   │
   ▼
4. Llamar a Gemini API
   │   - Modelo: gemini-2.0-flash
   │   - Timeout: 60s (extensible a 120s)
   │   - Temperatura: 0.3 (respuestas consistentes)
   │
   ├── Éxito ──▶ 5a. Parsear JSON de respuesta
   │                  │
   │                  ▼
   │             6a. Validar schema de respuesta
   │                  │
   │                  ├── Válido ──▶ 7a. Retornar success: true
   │                  │
   │                  └── Inválido ──▶ 7b. Reintentar 1 vez
   │                                        │
   │                                        ├── Éxito ──▶ Retornar success: true
   │                                        │
   │                                        └── Fallo ──▶ Retornar error parsing
   │
   └── Error ──▶ 5b. Clasificar error (cuota, red, API key)
                      │
                      └── Retornar success: false con código de error
```

---

### 4.3 Workflow: Generación de Rúbrica desde PDF

**Propósito:** Extraer criterios de evaluación desde un PDF de consigna.

**Endpoint:** `POST /webhook/generar-rubrica`

**Request:** (multipart/form-data)
```
pdf: [archivo PDF de la consigna]
api_key: AIza...
tipo_rubrica: TP  (opcional, default: TP)
```

**Response (éxito):**
```json
{
  "success": true,
  "rubrica": {
    "nombre_sugerido": "TP1 - Sistema de Gestión de Biblioteca",
    "descripcion": "Implementar un sistema de gestión de biblioteca con clases Libro, Usuario y Prestamo",
    "puntaje_maximo": 100,
    "criterios": [
      {
        "nombre": "Clase Libro",
        "descripcion": "Implementación correcta de la clase Libro con atributos isbn, titulo, autor y métodos getters/setters",
        "puntaje_maximo": 25
      },
      {
        "nombre": "Clase Usuario",
        "descripcion": "Implementación de Usuario con validación de datos y lista de préstamos activos",
        "puntaje_maximo": 25
      },
      {
        "nombre": "Clase Prestamo",
        "descripcion": "Gestión de préstamos con fechas y cálculo de multas por demora",
        "puntaje_maximo": 25
      },
      {
        "nombre": "Integración y Testing",
        "descripcion": "Funcionamiento integrado del sistema y casos de prueba",
        "puntaje_maximo": 25
      }
    ]
  },
  "metadata": {
    "paginas_procesadas": 3,
    "modelo": "gemini-2.0-flash"
  }
}
```

**Flujo del Workflow:**
```
1. Webhook Trigger (POST /webhook/generar-rubrica, multipart)
   │
   ▼
2. Extraer PDF y convertir a texto
   │   - Usar nodo "Extract from File" de N8N
   │   - O enviar PDF directo a Gemini (soporta multimodal)
   │
   ▼
3. Construir prompt de extracción (ver sección 5.2)
   │
   ▼
4. Llamar a Gemini API
   │   - Modelo: gemini-2.0-flash
   │   - Timeout: 60s
   │
   ├── Éxito ──▶ 5a. Parsear JSON de respuesta
   │                  │
   │                  ▼
   │             6a. Validar que tenga criterios
   │                  │
   │                  └── Retornar success: true
   │
   └── Error ──▶ 5b. Retornar error
```

---

## 5. Prompts de IA

### 5.1 Prompt: Corrección de Entrega

```
Eres un evaluador experto de trabajos prácticos de programación para la materia "{materia}".

Tu tarea es evaluar el siguiente código de un alumno según la rúbrica proporcionada.

## RÚBRICA DE EVALUACIÓN

Nombre: {rubrica.nombre}
Tipo: {rubrica.tipo}
Puntaje máximo: {rubrica.puntaje_maximo}

Criterios:
{for criterio in rubrica.criterios}
- {criterio.nombre} ({criterio.puntaje_maximo} pts): {criterio.descripcion}
{endfor}

## CÓDIGO DEL ALUMNO

```{lenguaje}
{codigo}
```

## INSTRUCCIONES

Evalúa el código según cada criterio de la rúbrica. Para cada criterio:
1. Asigna un puntaje entre 0 y el máximo del criterio
2. Determina el estado: "OK" (≥80%), "WARNING" (40-79%), "ERROR" (<40%)
3. Proporciona feedback específico y constructivo

Además:
- Lista 2-4 fortalezas del código
- Lista 2-4 recomendaciones de mejora específicas
- Escribe un comentario general de 2-3 oraciones

## FORMATO DE RESPUESTA

Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:

{
  "nota": <número entre 0 y {rubrica.puntaje_maximo}>,
  "criterios": [
    {
      "nombre": "<nombre exacto del criterio>",
      "puntaje_obtenido": <número>,
      "puntaje_maximo": <número>,
      "estado": "<OK|WARNING|ERROR>",
      "feedback": "<feedback específico>"
    }
  ],
  "fortalezas": ["<fortaleza 1>", "<fortaleza 2>"],
  "recomendaciones": ["<recomendación 1>", "<recomendación 2>"],
  "comentario_general": "<comentario de 2-3 oraciones>"
}

IMPORTANTE:
- La suma de puntaje_obtenido de todos los criterios debe ser igual a "nota"
- Cada criterio de la rúbrica debe aparecer en la respuesta
- El estado debe calcularse correctamente según el porcentaje
- NO incluyas texto antes o después del JSON
- NO uses markdown, solo JSON puro
```

### 5.2 Prompt: Generación de Rúbrica desde PDF

```
Eres un experto en diseño de rúbricas de evaluación para programación.

Analiza la siguiente consigna de trabajo práctico y genera una rúbrica de evaluación.

## CONSIGNA

{contenido_pdf}

## INSTRUCCIONES

1. Identifica los requisitos principales del trabajo
2. Crea criterios de evaluación que cubran:
   - Correctitud funcional (el código funciona)
   - Diseño y estructura (buenas prácticas de POO si aplica)
   - Calidad de código (naming, legibilidad)
   - Requisitos específicos mencionados en la consigna

3. Distribuye 100 puntos entre los criterios de forma balanceada
4. Cada criterio debe tener una descripción clara de qué se evalúa

## FORMATO DE RESPUESTA

Responde ÚNICAMENTE con un JSON válido:

{
  "nombre_sugerido": "<nombre descriptivo del TP>",
  "descripcion": "<resumen de 1-2 oraciones de qué se pide>",
  "puntaje_maximo": 100,
  "criterios": [
    {
      "nombre": "<nombre del criterio>",
      "descripcion": "<qué se evalúa en este criterio>",
      "puntaje_maximo": <número>
    }
  ]
}

IMPORTANTE:
- La suma de puntaje_maximo de todos los criterios debe ser 100
- Incluye entre 3 y 6 criterios
- Las descripciones deben ser específicas, no genéricas
- NO incluyas texto antes o después del JSON
```

---

## 6. Google Gemini

### 6.1 Configuración

| Aspecto | Especificación |
|---------|----------------|
| **Modelo predeterminado** | gemini-2.0-flash |
| **Endpoint** | generativelanguage.googleapis.com |
| **Autenticación** | API Key por usuario |
| **Temperatura** | 0.3 (respuestas consistentes) |
| **Max tokens output** | 4096 |

### 6.2 Modelos Disponibles

| Modelo | Uso Recomendado | Velocidad | Costo |
|--------|-----------------|-----------|-------|
| `gemini-2.0-flash` | Correcciones masivas, uso general | Rápido | Bajo |
| `gemini-2.0-flash-thinking` | Análisis complejos | Medio | Medio |
| `gemini-1.5-pro` | Casos que requieren más contexto | Lento | Alto |

### 6.3 Validación de API Key

Antes de usar una API Key, el backend debe validarla:

```python
# app/services/gemini_service.py

import httpx
from app.core.exceptions import ValidationError

async def validate_gemini_api_key(api_key: str) -> bool:
    """
    Valida que una API Key de Gemini sea válida.

    Args:
        api_key: API Key a validar.

    Returns:
        True si la key es válida.

    Raises:
        ValidationError: Si la key es inválida o hay error de conexión.
    """
    # Validar formato básico
    if not api_key or not api_key.startswith("AIza"):
        raise ValidationError(
            message="Formato de API Key inválido (debe empezar con 'AIza')",
            field="gemini_api_key"
        )

    # Probar con request simple
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    payload = {
        "contents": [{"parts": [{"text": "Responde OK"}]}]
    }

    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{url}?key={api_key}",
                json=payload,
                headers=headers,
                timeout=10.0
            )

            if response.status_code == 200:
                return True
            elif response.status_code == 400:
                raise ValidationError("API Key inválida o incorrecta")
            elif response.status_code == 429:
                raise ValidationError("API Key sin cuota disponible")
            else:
                raise ValidationError(f"Error al validar: {response.status_code}")

        except httpx.TimeoutException:
            raise ValidationError("Timeout al validar API Key")
        except httpx.RequestError as e:
            raise ValidationError(f"Error de conexión: {str(e)}")
```

### 6.4 Almacenamiento Seguro de API Keys

Las API Keys se almacenan encriptadas en la base de datos:

```python
# app/core/security.py

from cryptography.fernet import Fernet
from app.core.config import settings

def get_fernet() -> Fernet:
    """Obtiene instancia de Fernet para encriptación."""
    return Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_api_key(api_key: str) -> str:
    """
    Encripta una API Key para almacenamiento seguro.

    Args:
        api_key: API Key en texto plano.

    Returns:
        API Key encriptada (base64).
    """
    fernet = get_fernet()
    return fernet.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    """
    Desencripta una API Key almacenada.

    Args:
        encrypted_key: API Key encriptada.

    Returns:
        API Key en texto plano.
    """
    fernet = get_fernet()
    return fernet.decrypt(encrypted_key.encode()).decode()
```

---

## 7. Contrato de Comunicación Backend ↔ N8N

### 7.1 Headers Comunes

```http
Content-Type: application/json
Accept: application/json
```

### 7.2 Timeouts

| Operación | Timeout | Extensible |
|-----------|---------|------------|
| Health check | 10s | No |
| Corrección | 60s | Sí (hasta 120s) |
| Generación rúbrica | 60s | No |

### 7.3 Manejo de Errores

**Códigos de Error:**

| Código | Significado | Acción |
|--------|-------------|--------|
| `VALIDATION_ERROR` | Request inválido | No reintentar |
| `GEMINI_ERROR` | Error de Gemini API | Reintentar 1 vez |
| `QUOTA_EXCEEDED` | Sin cuota en API Key | No reintentar, notificar usuario |
| `PARSING_ERROR` | Respuesta de IA inválida | Reintentar 1 vez |
| `TIMEOUT` | Timeout de operación | Reintentar 1 vez |
| `NETWORK_ERROR` | Error de red | Reintentar 1 vez |

**Lógica de Reintentos en Backend:**

```python
# app/services/correccion_service.py

async def corregir_con_reintentos(
    self,
    entrega_id: int,
    max_reintentos: int = 1
) -> Correccion:
    """
    Corrige una entrega con lógica de reintentos.

    Args:
        entrega_id: ID de la entrega.
        max_reintentos: Máximo de reintentos (default: 1).

    Returns:
        Correccion creada.

    Raises:
        ExternalServiceError: Si falla después de reintentos.
    """
    errores_reintentables = {"GEMINI_ERROR", "PARSING_ERROR", "TIMEOUT", "NETWORK_ERROR"}

    for intento in range(max_reintentos + 1):
        try:
            return await self._ejecutar_correccion(entrega_id)

        except N8NError as e:
            if e.code not in errores_reintentables:
                raise  # No reintentar

            if intento < max_reintentos:
                await asyncio.sleep(2 ** intento)  # Backoff exponencial
                continue

            # Último intento falló
            await self._marcar_entrega_fallida(entrega_id, e.message)
            raise ExternalServiceError("N8N", f"Falló después de {max_reintentos + 1} intentos: {e.message}")
```

---

## 8. Flujo Completo de Corrección

### 8.1 Diagrama de Secuencia

```
Usuario          Frontend         Backend          N8N            Gemini
   │                │                │               │               │
   │  Click         │                │               │               │
   │  "Corregir"    │                │               │               │
   ├───────────────▶│                │               │               │
   │                │ POST /corregir │               │               │
   │                ├───────────────▶│               │               │
   │                │                │               │               │
   │                │                │ Validar       │               │
   │                │                │ permisos      │               │
   │                │                │               │               │
   │                │                │ Obtener       │               │
   │                │                │ API Key       │               │
   │                │                │               │               │
   │                │                │ POST webhook  │               │
   │                │                ├──────────────▶│               │
   │                │                │               │               │
   │                │                │               │ Construir     │
   │                │                │               │ prompt        │
   │                │                │               │               │
   │                │                │               │ POST API      │
   │                │                │               ├──────────────▶│
   │                │                │               │               │
   │                │                │               │    Evaluar    │
   │                │                │               │    código     │
   │                │                │               │               │
   │                │                │               │◀──────────────┤
   │                │                │               │   JSON resp   │
   │                │                │               │               │
   │                │                │               │ Parsear       │
   │                │                │               │ respuesta     │
   │                │                │               │               │
   │                │                │◀──────────────┤               │
   │                │                │  JSON result  │               │
   │                │                │               │               │
   │                │                │ Guardar en BD │               │
   │                │                │               │               │
   │                │◀───────────────┤               │               │
   │                │   Corrección   │               │               │
   │◀───────────────┤                │               │               │
   │   Mostrar      │                │               │               │
   │   resultado    │                │               │               │
```

### 8.2 Estados de Entrega Durante Corrección

| Estado | Descripción |
|--------|-------------|
| `uploaded` | Entrega subida, pendiente de corrección |
| `pending_correction` | Corrección en proceso |
| `corrected` | Corrección completada exitosamente |
| `failed` | Error en corrección (después de reintentos) |

---

## 9. Configuración de Desarrollo

### 9.1 Mock de N8N para Testing

Para tests locales sin N8N real:

```python
# tests/mocks/n8n_mock.py

from fastapi import FastAPI
from fastapi.responses import JSONResponse

mock_n8n = FastAPI()

@mock_n8n.post("/webhook/corregir")
async def mock_corregir(request: dict):
    """Mock de corrección para testing."""
    return JSONResponse({
        "success": True,
        "correccion": {
            "nota": 85,
            "criterios": [
                {
                    "nombre": "Criterio 1",
                    "puntaje_obtenido": 85,
                    "puntaje_maximo": 100,
                    "estado": "OK",
                    "feedback": "Buen trabajo"
                }
            ],
            "fortalezas": ["Código limpio"],
            "recomendaciones": ["Agregar más tests"],
            "comentario_general": "Trabajo aprobado."
        }
    })

@mock_n8n.post("/webhook/health")
async def mock_health():
    """Mock de health check."""
    return JSONResponse({
        "status": "ok",
        "n8n_version": "mock",
        "gemini_available": True
    })
```

### 9.2 Variables de Entorno para Desarrollo

```bash
# .env.development

# N8N local
N8N_WEBHOOK_CORRECCION=http://localhost:5678/webhook/corregir
N8N_WEBHOOK_RUBRICA=http://localhost:5678/webhook/generar-rubrica
N8N_WEBHOOK_HEALTH=http://localhost:5678/webhook/health

# Gemini (usar key de desarrollo)
# Cada desarrollador usa su propia API Key
```

---

## 10. Resumen de Decisiones

| Aspecto | Decisión |
|---------|----------|
| **Google Drive/Sheets** | Eliminado del proyecto |
| **Workflows N8N** | 2: Corrección + Generación rúbricas |
| **Health Check** | Sí, `/webhook/health` |
| **Modelo IA** | gemini-2.0-flash (predeterminado) |
| **Respuesta IA** | JSON estricto con schema fijo |
| **Reintentos** | 1 reintento para errores recuperables |
| **Timeout corrección** | 60s nominal, 120s máximo |
| **API Keys** | Por usuario, encriptadas con AES-256 |
| **Prompts** | Documentados con ejemplos completos |

---

## 11. Próximos Pasos

Este documento define las integraciones. Los siguientes documentos detallarán:

- **11-SEGURIDAD.md**: Autenticación, protección de datos, validaciones
- **12-ACCESIBILIDAD.md**: WCAG, navegación por teclado, contraste

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
