# Integración N8N - Resumen de Implementación

## ✅ Estado de la Integración

**Fecha:** 2026-02-06
**Estado:** ✅ **COMPLETADO**

Todos los workflows de N8N han sido creados y son compatibles con el backend existente.

---

## 📁 Archivos de Workflows

### 1. Workflow de Corrección (`correccion-workflow.json`)

**Ubicación:** `n8n/workflows/correccion-workflow.json`

**Endpoint:** `POST /webhook/corregir`

**Características:**
- ✅ Compatible con payload del backend
- ✅ Usa API key del usuario (no credenciales de N8N)
- ✅ Prompt con detección de inyecciones de prompt
- ✅ Respuesta estructurada con schema JSON estricto
- ✅ Manejo de errores con retry
- ✅ Timeout: 90 segundos

**Input esperado:**
```json
{
  "codigo": "string - código consolidado",
  "rubrica": {
    "nombre": "string",
    "tipo": "string",
    "puntaje_maximo": 100,
    "criterios": [
      {
        "nombre": "string",
        "descripcion": "string",
        "puntaje_maximo": number
      }
    ]
  },
  "api_key": "string - Gemini API key del usuario",
  "contexto": {
    "materia": "string",
    "alumno": "string"
  }
}
```

**Output:**
```json
{
  "success": true,
  "correccion": {
    "nota": number,
    "criterios": [
      {
        "nombre": "string",
        "puntaje_obtenido": number,
        "puntaje_maximo": number,
        "estado": "OK|WARNING|ERROR",
        "feedback": "string"
      }
    ],
    "fortalezas": ["string"],
    "recomendaciones": ["string"],
    "comentario_general": "string"
  },
  "metadata": {
    "modelo": "gemini-2.0-flash",
    "tokens_entrada": number,
    "tokens_salida": number,
    "tiempo_ms": number
  }
}
```

---

### 2. Workflow de Health Check (`health-check-workflow.json`)

**Ubicación:** `n8n/workflows/health-check-workflow.json`

**Endpoint:** `POST /webhook/health`

**Características:**
- ✅ Verifica conectividad de N8N
- ✅ Valida API key de Gemini
- ✅ Timeout: 10 segundos
- ✅ Respuesta rápida para monitoring

**Input:**
```json
{
  "api_key": "string - Gemini API key a validar"
}
```

**Output (OK):**
```json
{
  "status": "ok",
  "n8n_version": "1.0.0",
  "gemini_available": true,
  "timestamp": "2026-02-06T10:30:00Z"
}
```

**Output (Degradado):**
```json
{
  "status": "degraded",
  "n8n_version": "1.0.0",
  "gemini_available": false,
  "gemini_error": "[429] Quota exceeded",
  "timestamp": "2026-02-06T10:30:00Z"
}
```

---

### 3. Workflow de Generación de Rúbricas (`generar-rubrica-workflow.json`)

**Ubicación:** `n8n/workflows/generar-rubrica-workflow.json`

**Endpoint:** `POST /webhook/generar-rubrica`

**Características:**
- ✅ Modificado del workflow original para compatibilidad
- ✅ Usa API key del usuario (no credenciales de N8N)
- ✅ Prompt completo y robusto para extracción de criterios
- ✅ Mapea esquema complejo a esquema simple del backend
- ✅ Timeout: 120 segundos (2 minutos)

**Input:**
```json
{
  "pdf_base64": "string - PDF en base64",
  "filename": "string - nombre del archivo",
  "api_key": "string - Gemini API key del usuario",
  "tipo_rubrica": "string - TP, PARCIAL_1, etc. (opcional)"
}
```

**Output:**
```json
{
  "success": true,
  "rubrica": {
    "nombre_sugerido": "TP1 - Sistema de Gestión",
    "descripcion": "Implementar un sistema...",
    "puntaje_maximo": 100,
    "criterios": [
      {
        "nombre": "Correctitud funcional",
        "descripcion": "El código funciona correctamente",
        "puntaje_maximo": 35
      }
    ]
  },
  "metadata": {
    "assessment_type": "tp",
    "language_or_stack": ["python", "sql"],
    "pages_parsed": [1, 2, 3],
    "rubrica_completa": { /* esquema completo para referencia */ }
  }
}
```

---

## 🔧 Configuración del Backend

### Cliente N8N (`backend/app/integrations/n8n_client.py`)

**Estado:** ✅ **CORRECTO**

- ✅ URLs apuntan a los endpoints correctos
- ✅ Timeouts configurados correctamente:
  - Corrección: 90 segundos
  - Rúbrica: 120 segundos
  - Health: 10 segundos
- ✅ Manejo de errores con excepciones personalizadas
- ✅ Retry automático en cliente HTTP

### Variables de Entorno (`backend/app/core/config.py`)

**Estado:** ✅ **CORRECTO**

```python
# N8N Integration
N8N_BASE_URL: str = "http://n8n:5678"
N8N_WEBHOOK_CORRECCION: str = "http://n8n:5678/webhook/corregir"
N8N_WEBHOOK_RUBRICA: str = "http://n8n:5678/webhook/generar-rubrica"
N8N_WEBHOOK_HEALTH: str = "http://n8n:5678/webhook/health"
N8N_TIMEOUT_SECONDS: int = 90
```

---

## 📊 Servicios del Backend

### 1. CorreccionService (`backend/app/services/correccion_service.py`)

**Métodos:**
- ✅ `corregir_individual(entrega_id, api_key_encrypted, corregido_por_id)`
- ✅ `corregir_lote(data, api_key_encrypted, corregido_por_id)` - Corrección masiva con rate limiting
- ✅ `recorregir(entrega_id, api_key_encrypted, corregido_por_id)`
- ✅ `editar_correccion(correccion_id, data, editado_por_id)`

**Características:**
- ✅ Validación de permisos por rol
- ✅ Encriptación/desencriptación de API keys
- ✅ Retry con backoff exponencial
- ✅ Rate limiting: 2 segundos entre correcciones en lote
- ✅ Máximo 50 entregas por batch

### 2. RubricaIAService (`backend/app/services/rubrica_ia_service.py`)

**Métodos:**
- ✅ `generar_rubrica_desde_pdf(pdf_file, api_key_encrypted, tipo_rubrica)`

**Características:**
- ✅ Validación de tipo de archivo (solo PDF)
- ✅ Límite de tamaño: 10 MB
- ✅ Conversión a base64 para transmisión
- ✅ Validación de estructura de respuesta

---

## 🔒 Seguridad

### API Keys de Gemini

**Almacenamiento:**
- ✅ Encriptadas en BD con Fernet (AES-256)
- ✅ Se desencriptan solo al momento de uso
- ✅ Nunca se exponen en logs o respuestas

**Flujo:**
1. Usuario configura API key en su perfil
2. Backend encripta con `ENCRYPTION_KEY` y guarda en BD
3. Al corregir, backend desencripta y envía a N8N
4. N8N usa la API key para llamar a Gemini
5. API key nunca se almacena sin encriptar

### Validaciones

**N8N Client:**
- ✅ Timeouts para evitar requests colgados
- ✅ Retry automático con backoff exponencial
- ✅ Manejo de errores HTTP específicos (429, 503, etc.)

**Workflows:**
- ✅ Detección de prompt injection en correcciones
- ✅ Validación de schemas JSON en respuestas
- ✅ Manejo de errores de Gemini (cuota, timeout, etc.)

---

## 🚀 Cómo Importar los Workflows en N8N

### Opción 1: Importar vía UI

1. Accede a N8N en `http://localhost:5678`
2. Ve a **Workflows** → **Import from File**
3. Importa cada archivo:
   - `n8n/workflows/correccion-workflow.json`
   - `n8n/workflows/health-check-workflow.json`
   - `n8n/workflows/generar-rubrica-workflow.json`
4. Activa cada workflow

### Opción 2: Montar volumen en Docker

Edita `docker-compose.yml` para montar los workflows:

```yaml
services:
  n8n:
    image: n8nio/n8n:latest
    volumes:
      - ./n8n/workflows:/home/node/.n8n/workflows
      - n8n_data:/home/node/.n8n
```

Al iniciar N8N, los workflows estarán disponibles automáticamente.

---

## ✅ Checklist de Deployment

### Backend
- [ ] Configurar variable `ENCRYPTION_KEY` en `.env` (generarla con Fernet)
- [ ] Configurar variable `SECRET_KEY` para JWT
- [ ] Verificar que `N8N_BASE_URL` apunta correctamente (Docker: `http://n8n:5678`)
- [ ] Configurar `DATABASE_URL` con PostgreSQL

### N8N
- [ ] Importar los 3 workflows
- [ ] Activar cada workflow
- [ ] Verificar que N8N esté en la misma red Docker que el backend
- [ ] (Opcional) Configurar autenticación básica en N8N

### Validación
- [ ] Ejecutar health check: `POST http://backend:5000/api/v1/health`
- [ ] Probar corrección individual con una entrega de prueba
- [ ] Probar generación de rúbrica con un PDF de ejemplo
- [ ] Verificar logs de N8N para errores

---

## 🐛 Troubleshooting

### Error: "Timeout esperando respuesta de N8N"

**Causa:** N8N no responde o Gemini tarda demasiado

**Solución:**
1. Verificar que N8N esté corriendo: `docker ps | grep n8n`
2. Verificar logs de N8N: `docker logs n8n`
3. Aumentar timeout en `backend/app/integrations/n8n_client.py` si es necesario

### Error: "Error de Gemini [429]: Quota exceeded"

**Causa:** La API key del usuario no tiene cuota disponible

**Solución:**
1. Verificar cuota en Google AI Studio
2. Pedir al usuario que use otra API key
3. (Producción) Implementar sistema de fallback con múltiples keys

### Error: "API Key inválida o incorrecta"

**Causa:** La API key del usuario no es válida

**Solución:**
1. Verificar que la key empiece con "AIza"
2. Validar en Google AI Studio que esté activa
3. Regenerar la key si es necesario

### Error: "No se encontró texto en la respuesta"

**Causa:** Gemini retornó respuesta vacía o en formato inesperado

**Solución:**
1. Verificar logs de N8N para ver la respuesta cruda
2. Validar que el prompt no esté causando bloqueos de contenido
3. Reintentar la operación (el backend hace 1 retry automático)

---

## 📝 Próximos Pasos Recomendados

### Corto Plazo

1. **Implementar health check en startup**
   - Descomentar TODO en `main.py` línea 30
   - Agregar verificación de N8N al iniciar el backend

2. **Tests de integración**
   - Crear tests para cada workflow
   - Mockear respuestas de Gemini para tests unitarios

3. **Monitoring**
   - Agregar métricas de tiempos de respuesta
   - Log de errores de Gemini por tipo
   - Dashboard de uso de API keys

### Mediano Plazo

4. **Fallback de API Keys**
   - Sistema de múltiples API keys para distribución de carga
   - Rotación automática si una key agota cuota

5. **Optimizaciones**
   - Cache de correcciones duplicadas
   - Batch processing más eficiente
   - Compresión de código antes de enviar a Gemini

6. **Mejoras de UX**
   - Progress tracking para correcciones masivas (WebSocket)
   - Preview de rúbrica antes de guardar
   - Historial de correcciones por alumno

---

## 🔗 Referencias

- **Documentación de N8N:** https://docs.n8n.io/
- **Gemini API Docs:** https://ai.google.dev/docs
- **Spec 10-INTEGRACIONES.md:** `docs/specs/10-INTEGRACIONES.md`
- **Arquitectura Backend:** `docs/specs/05-ARQUITECTURA-STACK.md`

---

**Autor:** Claude Sonnet 4.5
**Última actualización:** 2026-02-06
