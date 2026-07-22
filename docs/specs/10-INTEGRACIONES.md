# 10 - Integraciones

---

## 1. Resumen de Integraciones

| Integración | Propósito | Obligatoria |
|-------------|-----------|-------------|
| **Google Gemini (Gemini Studio)** | Modelo de IA para corrección — llamada HTTP directa desde el backend | Sí (o OpenRouter) |
| **OpenRouter** | Proveedor de IA alternativo — llamada HTTP directa desde el backend | Sí (o Gemini) |
| **Google Drive/Sheets** | ~~Sincronización de archivos~~ | ❌ Eliminada |

> **Nota de arquitectura:** la corrección es **nativa del backend**. Ya NO existe un intermediario N8N. El backend (`backend/app/integrations/`) llama directamente al proveedor de IA por HTTP: `ia_provider.py` rutea según `usuario.correction_provider` hacia `gemini_correction_client.py` (Gemini Studio) o `openrouter_client.py` (OpenRouter).

### Decisiones Clave

| Aspecto | Decisión |
|---------|----------|
| **Ruteo de proveedor** | `ia_provider.py` lee `usuario.correction_provider` (`"gemini"` \| `"openrouter"`); normaliza vacío/desconocido → `"gemini"`. Sin failover automático. |
| **Clientes** | `gemini_correction_client.py` (Gemini Studio) y `openrouter_client.py` (OpenRouter) |
| **Modelo IA** | Gemini Studio: `gemini-3.5-flash` (`settings.GEMINI_MODEL`) · OpenRouter: `google/gemini-3.5-flash` (`settings.OPENROUTER_MODEL`) |
| **Respuesta IA** | JSON estructurado estricto (Gemini: `responseSchema` · OpenRouter: `response_format: json_object`) |
| **Temperatura** | 0 (respuestas determinísticas) |
| **Timeout** | 90s (cliente Gemini) |
| **Reintentos** | 1 reintento automático, luego marcar fallida |
| **API Key** | Una key encriptada por proveedor y por usuario (Fernet) |

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
│  │  2. Consolida el código de la entrega (ZIP/TXT → string, PDF → b64) │    │
│  │  3. Obtiene la API Key del proveedor (desencriptada con Fernet)     │    │
│  │  4. Llama a ia_provider.py                                          │    │
│  │  6. Guarda corrección en BD                                         │    │
│  └──────────────────────────────────┬──────────────────────────────────┘    │
│                                     │                                        │
│  ┌──────────────────────────────────▼──────────────────────────────────┐    │
│  │            integrations/ia_provider.py  (ruteo por proveedor)        │    │
│  │   usuario.correction_provider → normaliza vacío/desconocido → gemini │    │
│  └──────────────┬──────────────────────────────────┬────────────────────┘   │
│                 │ "gemini"                          │ "openrouter"           │
│                 ▼                                   ▼                        │
│  ┌───────────────────────────┐      ┌───────────────────────────────────┐   │
│  │ gemini_correction_client  │      │      openrouter_client            │   │
│  └──────────────┬────────────┘      └──────────────────┬────────────────┘   │
└─────────────────┼──────────────────────────────────────┼────────────────────┘
                  │ HTTPS POST                             │ HTTPS POST
                  ▼                                        ▼
┌────────────────────────────────────┐   ┌────────────────────────────────────┐
│      GOOGLE GEMINI (Studio)         │   │             OPENROUTER             │
│                                     │   │                                    │
│ generativelanguage.googleapis.com   │   │ {OPENROUTER_BASE_URL}/chat/        │
│ modelo: gemini-3.5-flash            │   │   completions                      │
│ auth: ?key=API_KEY                  │   │ modelo: google/gemini-3.5-flash    │
│ responseSchema JSON · temp 0        │   │ auth: Authorization: Bearer        │
│                                     │   │ response_format: json_object       │
└────────────────────────────────────┘   └────────────────────────────────────┘
```

El backend elige **un** proveedor por usuario (el que el usuario configuró). No hay failover: si el proveedor elegido falla, la corrección se marca fallida tras el reintento.

---

## 3. Proveedores de IA - Configuración

### 3.1 Ruteo de Proveedor (`ia_provider.py`)

| Aspecto | Especificación |
|---------|----------------|
| **Fuente de la decisión** | `usuario.correction_provider` |
| **Valores válidos** | `"gemini"` \| `"openrouter"` |
| **Normalización** | Valor vacío o desconocido → `"gemini"` |
| **Failover** | No existe. Un solo proveedor por corrección. |
| **API Key** | Se lee la key encriptada del usuario para el proveedor elegido y se desencripta con Fernet antes de la llamada |

### 3.2 Variables de Entorno relevantes

```bash
# backend/.env — modelos por proveedor (backend/app/core/config.py es la fuente de verdad)
GEMINI_MODEL=gemini-3.5-flash
OPENROUTER_MODEL=google/gemini-3.5-flash
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Clave maestra de encriptación de API Keys (Fernet)
# 32 bytes aleatorios en base64 url-safe = 44 caracteres, generada con Fernet.generate_key()
ENCRYPTION_KEY=...
```

> Las API Keys de IA de cada usuario NO se configuran por variable de entorno: se guardan encriptadas por usuario en la BD (una por proveedor).

---

## 4. Flujos de IA (nativos en el backend)

### 4.1 Validación de API Key

**Propósito:** Verificar que la API Key del usuario es válida antes de usarla para corregir.

- **Gemini Studio:** `backend/app/integrations/gemini_studio_client.py` valida contra el **mismo** modelo que usa la corrección (`settings.GEMINI_MODEL`, es decir `gemini-3.5-flash`).
- **OpenRouter:** `openrouter_client.validar_api_key`.

Se dispara al guardar/actualizar la API Key del usuario. Si la key es inválida, se rechaza y no se persiste.

---

### 4.2 Corrección de Entrega

**Propósito:** Evaluar el código de un alumno usando una rúbrica y retornar una calificación estructurada.

**Entrada (construida por el backend):** código consolidado del alumno (o PDF en base64), la rúbrica con sus criterios, el contexto (materia, lenguaje) y la API Key del usuario ya desencriptada.

**Payload conceptual entregado al cliente de IA:**
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
  "contexto": {
    "materia": "Programación I",
    "lenguaje": "Java"
  }
}
```

**Respuesta de la IA (JSON estricto):**
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
    "modelo": "gemini-3.5-flash",
    "tokens_entrada": 1250,
    "tokens_salida": 580,
    "tiempo_ms": 3200
  }
}
```

**Respuesta de error:**
```json
{
  "success": false,
  "error": {
    "code": "N8N_ERROR",
    "message": "Error al procesar con el proveedor de IA: cuota excedida",
    "retry": false
  }
}
```

> **Nota sobre códigos de error:** los códigos `N8N_ERROR` / `N8N_TIMEOUT` y las excepciones `N8NError` / `N8NTimeoutError` (definidas en `backend/app/core/error_catalog.py`) se **conservan a propósito como nombres históricos** (están persistidos en datos). Hoy los **levantan los clientes de Gemini/OpenRouter**, no ningún servicio N8N. No hay N8N en ejecución.

**Estados de Criterio:**

| Estado | Significado | Color UI |
|--------|-------------|----------|
| `OK` | Criterio cumplido satisfactoriamente (≥80% del puntaje) | Verde |
| `WARNING` | Criterio parcialmente cumplido (40-79% del puntaje) | Amarillo |
| `ERROR` | Criterio no cumplido (<40% del puntaje) | Rojo |

**Flujo de corrección (backend nativo):**
```
1. CorreccionService recibe la solicitud de corrección
   │
   ▼
2. Valida permisos y consolida el código (ZIP/TXT → string · PDF → base64)
   │
   ▼
3. Desencripta la API Key del proveedor del usuario (Fernet)
   │
   ▼
4. ia_provider.py rutea según usuario.correction_provider
   │
   ├── "gemini" ──▶ gemini_correction_client.py
   │      POST https://generativelanguage.googleapis.com/v1beta/
   │           models/gemini-3.5-flash:generateContent?key=API_KEY
   │      temperature 0 · responseSchema JSON estricto · timeout 90s
   │      (PDF: usa la Files API + visión)
   │
   └── "openrouter" ──▶ openrouter_client.py
          POST {OPENROUTER_BASE_URL}/chat/completions
          Authorization: Bearer API_KEY · response_format json_object
   │
   ▼
5. Parsear y validar el JSON de respuesta
   │
   ├── Válido ──▶ 6a. Guardar Correccion (nota + criterios JSONB) en BD
   │
   └── Inválido/Error ──▶ 6b. Reintentar 1 vez; si falla, marcar entrega fallida
                               (levanta N8NError / N8NTimeoutError — nombres históricos)
```

---

### 4.3 Generación de Rúbrica desde PDF

**Propósito:** Extraer criterios de evaluación desde un PDF de consigna, usando el mismo proveedor de IA del usuario.

**Entrada:** PDF de la consigna (procesado por el backend — para Gemini se usa la Files API + visión), la API Key del usuario y el tipo de rúbrica (opcional, default: `TP`).

**Respuesta (éxito):**
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
    "modelo": "gemini-3.5-flash"
  }
}
```

**Flujo:**
```
1. El backend recibe el PDF de la consigna
   │
   ▼
2. Prepara el PDF para la IA
   │   - Gemini: sube el PDF con la Files API y usa visión
   │   - OpenRouter: envía el contenido según el cliente correspondiente
   │
   ▼
3. Construir prompt de extracción (ver sección 5.2)
   │
   ▼
4. Llamar al proveedor de IA (gemini_correction_client / openrouter_client)
   │   - Gemini: modelo gemini-3.5-flash · OpenRouter: google/gemini-3.5-flash
   │
   ├── Éxito ──▶ 5a. Parsear JSON y validar que tenga criterios ──▶ success: true
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

> En Gemini Studio, este contrato de salida se refuerza además con `responseSchema` (JSON estricto). En OpenRouter se usa `response_format: json_object`.

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

## 6. Proveedores de IA - Detalle

### 6.1 Configuración

| Aspecto | Gemini Studio | OpenRouter |
|---------|---------------|------------|
| **Cliente** | `gemini_correction_client.py` | `openrouter_client.py` |
| **Modelo** | `gemini-3.5-flash` (`settings.GEMINI_MODEL`) | `google/gemini-3.5-flash` (`settings.OPENROUTER_MODEL`) |
| **Endpoint** | `generativelanguage.googleapis.com/v1beta/.../generateContent` | `{OPENROUTER_BASE_URL}/chat/completions` |
| **Autenticación** | `?key=API_KEY` (por usuario) | `Authorization: Bearer API_KEY` (por usuario) |
| **Formato de salida** | `responseSchema` (JSON estricto) | `response_format: json_object` |
| **Temperatura** | 0 | 0 |
| **Timeout** | 90s | — |
| **PDF** | Files API + visión | según cliente |

### 6.2 Modelos por Proveedor

| Proveedor | Modelo | Setting (fuente de verdad) |
|-----------|--------|-----------------------------|
| Gemini Studio | `gemini-3.5-flash` | `settings.GEMINI_MODEL` |
| OpenRouter | `google/gemini-3.5-flash` | `settings.OPENROUTER_MODEL` |

> El modelo está **unificado** en `backend/app/core/config.py`. La validación de API Key de Gemini se hace contra el mismo `settings.GEMINI_MODEL` que usa la corrección, para no validar contra un modelo distinto del que efectivamente corrige.

### 6.3 Validación de API Key

Antes de persistir una API Key, el backend la valida:

- **Gemini Studio** (`gemini_studio_client.py`): request de prueba contra `settings.GEMINI_MODEL` (`gemini-3.5-flash`).
- **OpenRouter** (`openrouter_client.validar_api_key`): verificación contra el endpoint de OpenRouter.

```python
# backend/app/integrations/gemini_studio_client.py (conceptual)
# Valida la API Key contra el MISMO modelo que corrige: settings.GEMINI_MODEL

url = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{settings.GEMINI_MODEL}:generateContent"   # gemini-3.5-flash
)
payload = {"contents": [{"parts": [{"text": "Responde OK"}]}]}
# POST url?key=API_KEY  →  200 = válida · 400 = inválida · 429 = sin cuota
```

### 6.4 Almacenamiento Seguro de API Keys

Las API Keys se almacenan **encriptadas con Fernet** (AES-128-CBC + HMAC-SHA256) en la base de datos:

```python
# backend/app/core/security.py

from cryptography.fernet import Fernet
from app.core.config import settings

def get_fernet() -> Fernet:
    """Obtiene instancia de Fernet para encriptación (AES-128-CBC + HMAC-SHA256)."""
    return Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_api_key(api_key: str) -> str:
    """Encripta una API Key para almacenamiento seguro (retorna base64)."""
    fernet = get_fernet()
    return fernet.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    """Desencripta una API Key almacenada."""
    fernet = get_fernet()
    return fernet.decrypt(encrypted_key.encode()).decode()
```

> `ENCRYPTION_KEY` es una **clave Fernet**: 32 bytes aleatorios codificados en base64 url-safe = **44 caracteres**, generada con `Fernet.generate_key()`.

---

## 7. Contrato de Comunicación Backend ↔ Proveedor de IA

### 7.1 Headers Comunes

```http
# Gemini Studio
Content-Type: application/json
# (API Key en la query string: ?key=API_KEY)

# OpenRouter
Content-Type: application/json
Authorization: Bearer <API_KEY>
```

### 7.2 Timeouts

| Operación | Timeout |
|-----------|---------|
| Validación de API Key | Corto (request de prueba) |
| Corrección (Gemini) | 90s |
| Generación de rúbrica | Según cliente |

### 7.3 Manejo de Errores

Los errores están centralizados en `backend/app/core/error_catalog.py`.

**Códigos de Error:**

| Código | Significado | Acción |
|--------|-------------|--------|
| `VALIDATION_ERROR` | Request inválido | No reintentar |
| `N8N_ERROR` | Error del proveedor de IA (nombre histórico) | Reintentar 1 vez |
| `N8N_TIMEOUT` | Timeout de la llamada a la IA (nombre histórico) | Reintentar 1 vez |
| `QUOTA_EXCEEDED` | Sin cuota en la API Key | No reintentar, notificar usuario |
| `PARSING_ERROR` | Respuesta de IA inválida | Reintentar 1 vez |

> `N8N_ERROR` / `N8N_TIMEOUT` (y las clases `N8NError` / `N8NTimeoutError`) son **nombres históricos conservados a propósito** (persistidos en datos). Hoy los levantan los clientes de Gemini/OpenRouter, no un servicio N8N.

**Lógica de Reintentos en Backend:**

```python
# backend/app/services/correccion_service.py

async def corregir_con_reintentos(
    self,
    entrega_id: int,
    max_reintentos: int = 1
) -> Correccion:
    """Corrige una entrega con lógica de reintentos (1 por defecto)."""
    errores_reintentables = {"N8N_ERROR", "N8N_TIMEOUT", "PARSING_ERROR"}

    for intento in range(max_reintentos + 1):
        try:
            return await self._ejecutar_correccion(entrega_id)

        except N8NError as e:  # nombre histórico; lo levanta el cliente de IA
            if e.code not in errores_reintentables:
                raise  # No reintentar

            if intento < max_reintentos:
                await asyncio.sleep(2 ** intento)  # Backoff exponencial
                continue

            # Último intento falló
            await self._marcar_entrega_fallida(entrega_id, e.message)
            raise
```

---

## 8. Flujo Completo de Corrección

### 8.1 Diagrama de Secuencia

```
Usuario          Frontend         Backend                     Proveedor IA
   │                │                │                        (Gemini/OpenRouter)
   │  Click         │                │                              │
   │  "Corregir"    │                │                              │
   ├───────────────▶│                │                              │
   │                │ POST /corregir │                              │
   │                ├───────────────▶│                              │
   │                │                │ Validar permisos             │
   │                │                │                              │
   │                │                │ Consolidar código            │
   │                │                │ (ZIP/TXT → string · PDF b64) │
   │                │                │                              │
   │                │                │ Desencriptar API Key (Fernet)│
   │                │                │                              │
   │                │                │ ia_provider rutea por        │
   │                │                │ correction_provider          │
   │                │                │                              │
   │                │                │ POST HTTP directo            │
   │                │                ├─────────────────────────────▶│
   │                │                │                              │ Evaluar
   │                │                │                              │ código
   │                │                │◀─────────────────────────────┤
   │                │                │   JSON estricto (nota + crit)│
   │                │                │                              │
   │                │                │ Parsear + validar schema     │
   │                │                │ Guardar Correccion en BD     │
   │                │◀───────────────┤                              │
   │                │   Corrección   │                              │
   │◀───────────────┤                │                              │
   │   Mostrar      │                │                              │
   │   resultado    │                │                              │
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

### 9.1 Mock del Proveedor de IA para Testing

Para tests locales sin llamar a la IA real, se mockea el cliente de integración (`gemini_correction_client` / `openrouter_client`) para que retorne una corrección fija:

```python
# tests (conceptual): mockear el cliente de IA, no un servicio HTTP externo

def mock_corregir(*args, **kwargs):
    return {
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
    }
```

### 9.2 Variables de Entorno para Desarrollo

```bash
# backend/.env.development

# Modelos por proveedor
GEMINI_MODEL=gemini-3.5-flash
OPENROUTER_MODEL=google/gemini-3.5-flash
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Cada desarrollador configura su propia API Key por usuario (encriptada en BD),
# eligiendo el proveedor con correction_provider ("gemini" | "openrouter").
```

---

## 10. Resumen de Decisiones

| Aspecto | Decisión |
|---------|----------|
| **Google Drive/Sheets** | Eliminado del proyecto |
| **Intermediario N8N** | Eliminado — la corrección es nativa del backend |
| **Ruteo** | `ia_provider.py` por `usuario.correction_provider` (sin failover) |
| **Clientes** | `gemini_correction_client.py` · `openrouter_client.py` |
| **Modelo IA** | Gemini `gemini-3.5-flash` · OpenRouter `google/gemini-3.5-flash` |
| **Respuesta IA** | JSON estricto (responseSchema · json_object) |
| **Reintentos** | 1 reintento para errores recuperables |
| **Timeout corrección** | 90s (cliente Gemini) |
| **API Keys** | Por usuario y por proveedor, encriptadas con Fernet (AES-128-CBC + HMAC-SHA256) |
| **Códigos de error** | `N8N_ERROR` / `N8N_TIMEOUT` conservados como nombres históricos |

---

## 11. Próximos Pasos

Este documento define las integraciones. Los siguientes documentos detallarán:

- **11-SEGURIDAD.md**: Autenticación, protección de datos, validaciones
- **12-ACCESIBILIDAD.md**: WCAG, navegación por teclado, contraste

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.1 — actualizado a la arquitectura de IA nativa (sin N8N)*
*Fecha: Julio 2026*
