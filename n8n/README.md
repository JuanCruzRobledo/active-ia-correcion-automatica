# N8N Preconfigurado para Active-IA

Este directorio contiene la infraestructura para crear una **imagen Docker personalizada de N8N** con workflows preconfigurados para Active-IA.

---

## 📋 ¿Qué incluye esta imagen?

La imagen preconfigurada de N8N expone **4 webhooks** listos para usar:

| Endpoint | Función |
|----------|---------|
| `/webhook/corregir` | Evalúa código del alumno usando Gemini y retorna nota + feedback |
| `/webhook/corregir-pdf` | Corrige entregas en PDF con Gemini |
| `/webhook/generar-rubrica` | Extrae criterios desde PDF de consigna usando Gemini |
| `/webhook/health` | Verifica que N8N y Gemini están operativos |

> **🧠 Importante (arquitectura real):** los 4 webhooks viven dentro de **UN solo workflow** llamado **"Correcion Automatica"** (no son 4 workflows separados). La **fuente de verdad es la data baked dentro de la imagen** (`/home/node/.n8n`), no la carpeta `workflows/` — esos `.json` son exports de referencia y pueden quedar desactualizados.

---

## 🎯 ¿Por qué preconfigurar?

Sin preconfiguración, cada usuario debería:
- ❌ Aprender a usar N8N
- ❌ Crear workflows desde cero
- ❌ Configurar webhooks manualmente
- ❌ Conectar nodos de Gemini

Con la imagen preconfigurada:
- ✅ Los workflows ya están creados
- ✅ Los webhooks ya están configurados
- ✅ Solo ejecutar `docker-compose up`
- ✅ Las API Keys de Gemini las provee cada usuario en el backend (no se almacenan en N8N)

---

## 🚀 Proceso de Preconfiguración

Sigue estos pasos **UNA VEZ** para crear la imagen personalizada.

### PASO 1: Preparar Permisos (Solo Windows)

```powershell
# En la carpeta n8n/
docker run --rm -v "${PWD}/data:/data" alpine chown -R 1000:1000 /data
```

### PASO 2: Levantar N8N en Modo Configuración

```powershell
# Detener cualquier instancia anterior
docker rm -f n8n-config

# Iniciar N8N sin autenticación para configurar
docker run -d `
  --name n8n-config `
  -p 5678:5678 `
  -e N8N_BASIC_AUTH_ACTIVE=false `
  -v "${PWD}/data:/home/node/.n8n" `
  n8nio/n8n:latest
```

**Accede a:** http://localhost:5678

### PASO 3: Crear los Workflows

⚠️ **IMPORTANTE:** NO necesitas configurar credenciales de Gemini en N8N. Las API Keys las proporcionan los usuarios en cada request.

---

#### **Workflow 1: Corrección Automática**

**Path del webhook:** `/webhook/corregir`

**Nodos a crear:**

1. **Webhook**
   - HTTP Method: `POST`
   - Path: `corregir`
   - Response Mode: `When Last Node Finishes`
   - Authentication: `None`

2. **Code** (Preparar Prompt)
   - Language: `JavaScript`
   - Code:
     ```javascript
     const { codigo, rubrica, contexto, api_key } = $input.item.json.body;

     const prompt = `Eres un evaluador de código para ${contexto.materia}.

Evalúa el siguiente código según la rúbrica proporcionada:

CÓDIGO:
\`\`\`${contexto.lenguaje || 'python'}
${codigo}
\`\`\`

RÚBRICA:
${JSON.stringify(rubrica.criterios, null, 2)}

Responde SOLO con JSON válido con esta estructura:
{
  "nota": <número 0-100>,
  "criterios": [
    {
      "nombre": "<nombre del criterio>",
      "puntaje_obtenido": <número>,
      "puntaje_maximo": <número>,
      "estado": "OK|WARNING|ERROR",
      "feedback": "<feedback específico>"
    }
  ],
  "fortalezas": ["<fortaleza 1>", "<fortaleza 2>"],
  "recomendaciones": ["<recomendación 1>", "<recomendación 2>"],
  "comentario_general": "<comentario de cierre>"
}`;

     return [{
       json: {
         prompt,
         api_key
       }
     }];
     ```

3. **HTTP Request** (Llamar a Gemini)
   - Method: `POST`
   - URL: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={{$json.api_key}}`
   - Send Body: `true`
   - Body Content Type: `JSON`
   - Body:
     ```json
     {
       "contents": [{
         "parts": [{
           "text": "{{$json.prompt}}"
         }]
       }],
       "generationConfig": {
         "temperature": 0.3,
         "maxOutputTokens": 4096
       }
     }
     ```
   - Timeout: `90000` (90 segundos)

4. **Code** (Parsear Respuesta)
   - Code:
     ```javascript
     const response = $input.item.json;

     try {
       const text = response.candidates[0].content.parts[0].text;
       const jsonMatch = text.match(/\{[\s\S]*\}/);
       const correccion = JSON.parse(jsonMatch[0]);

       return [{
         json: {
           success: true,
           correccion,
           metadata: {
             modelo: 'gemini-2.0-flash',
             tokens_entrada: response.usageMetadata?.promptTokenCount,
             tokens_salida: response.usageMetadata?.candidatesTokenCount,
             tiempo_ms: Date.now() - $execution.startedAt
           }
         }
       }];
     } catch (error) {
       return [{
         json: {
           success: false,
           error: {
             code: 'PARSING_ERROR',
             message: error.message,
             retry: true
           }
         }
       }];
     }
     ```

5. **Respond to Webhook**
   - Conectar el nodo Code al nodo Respond

**Activar el workflow** (toggle verde en la esquina superior derecha)

---

#### **Workflow 2: Generación de Rúbrica desde PDF**

**Path del webhook:** `/webhook/generar-rubrica`

**Nodos a crear:**

1. **Webhook**
   - HTTP Method: `POST`
   - Path: `generar-rubrica`

2. **Code** (Preparar Prompt)
   - Code:
     ```javascript
     const { pdf_base64, tipo_rubrica, api_key } = $input.item.json.body;

     const prompt = `Analiza esta consigna de trabajo práctico y genera una rúbrica de evaluación.

Identifica los requisitos principales y crea 4-6 criterios de evaluación.
La suma de puntajes máximos debe ser 100.

Responde SOLO con JSON:
{
  "nombre_sugerido": "<nombre del TP>",
  "descripcion": "<resumen breve>",
  "puntaje_maximo": 100,
  "criterios": [
    {
      "nombre": "<nombre del criterio>",
      "descripcion": "<qué se evalúa>",
      "puntaje_maximo": <número>
    }
  ]
}`;

     return [{
       json: {
         prompt,
         pdf_base64,
         api_key
       }
     }];
     ```

3. **HTTP Request** (Llamar a Gemini con PDF)
   - URL: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={{$json.api_key}}`
   - Body:
     ```json
     {
       "contents": [{
         "parts": [
           {
             "text": "{{$json.prompt}}"
           },
           {
             "inline_data": {
               "mime_type": "application/pdf",
               "data": "{{$json.pdf_base64}}"
             }
           }
         ]
       }]
     }
     ```
   - Timeout: `120000` (120 segundos)

4. **Code** (Parsear Respuesta)
   - Similar al workflow anterior

5. **Respond to Webhook**

**Activar el workflow**

---

#### **Workflow 3: Health Check**

**Path del webhook:** `/webhook/health`

**Nodos a crear:**

1. **Webhook**
   - HTTP Method: `POST`
   - Path: `health`

2. **Code**
   - Code:
     ```javascript
     const { api_key } = $input.item.json.body;

     return [{
       json: {
         api_key,
         test_prompt: "Responde solo: OK"
       }
     }];
     ```

3. **HTTP Request** (Test Gemini)
   - URL: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={{$json.api_key}}`
   - Body:
     ```json
     {
       "contents": [{
         "parts": [{
           "text": "{{$json.test_prompt}}"
         }]
       }]
     }
     ```
   - Timeout: `10000` (10 segundos)

4. **Code** (Verificar)
   - Code:
     ```javascript
     return [{
       json: {
         status: 'ok',
         n8n_version: $env.N8N_VERSION,
         gemini_available: true,
         timestamp: new Date().toISOString()
       }
     }];
     ```

5. **Respond to Webhook**

**Activar el workflow**

---

### PASO 4: Verificar Workflows

Prueba cada webhook con curl:

```bash
# Health Check
curl -X POST http://localhost:5678/webhook/health \
  -H "Content-Type: application/json" \
  -d '{"api_key": "AIza..."}'

# Corrección (simplificado)
curl -X POST http://localhost:5678/webhook/corregir \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "AIza...",
    "codigo": "print(\"hola\")",
    "rubrica": {"criterios": []},
    "contexto": {"materia": "Prog1"}
  }'
```

### PASO 5: Detener N8N

```powershell
docker stop n8n-config
docker rm n8n-config
```

Los datos quedan guardados en `data/`.

### PASO 6: Construir Imagen

```bash
# Git Bash (o cualquier terminal con bash)
cd n8n/
./build-image.sh
```

Sigue las instrucciones del script:
1. Ingresa el nombre de tu imagen (ej: `tuusuario/n8n-active-ia`)
2. Tag (default: `latest`)
3. Decide si pushear a Docker Hub

---

## 🐳 Usar la Imagen en Docker Compose

En el `docker-compose.yml` de la raíz del proyecto:

```yaml
services:
  n8n:
    image: tuusuario/n8n-active-ia:latest  # Tu imagen custom
    ports:
      - "5678:5678"  # Solo en desarrollo
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - WEBHOOK_URL=http://n8n:5678
      - GENERIC_TIMEZONE=America/Argentina/Buenos_Aires
    networks:
      - internal
    # NO montar volumen en producción (la imagen ya tiene todo)
```

**Backend `.env`:**
```env
N8N_BASE_URL=http://n8n:5678
N8N_WEBHOOK_CORRECCION=http://n8n:5678/webhook/corregir
N8N_WEBHOOK_RUBRICA=http://n8n:5678/webhook/generar-rubrica
N8N_WEBHOOK_HEALTH=http://n8n:5678/webhook/health
```

---

## 🔄 Actualizar Workflows

> ⚠️ **Para ACTUALIZAR no sirven los PASO 1-6 de arriba** (esos crean la imagen desde cero con la imagen vacía `n8nio/n8n` → te quedás SIN flujos). Para actualizar hay que partir de **tu imagen existente**, que ya tiene los workflows.
>
> 🪟 **Y en Windows NO uses bind-mount de `data/`** (rompe los webhooks por SQLite WAL → 404).

**El flujo correcto de actualización está documentado en [`MAINTENANCE.md`](./MAINTENANCE.md).** En resumen:

1. Levantá n8n desde **tu imagen actual** con storage interno (sin `-v`):
   ```bash
   docker run -d --name n8n-edit -p 5678:5678 \
     -e N8N_USER_MANAGEMENT_DISABLED=true -e N8N_BASIC_AUTH_ACTIVE=false \
     juancruzrobledo/n8n-active-ia:latest
   ```
2. Editá el workflow en http://localhost:5678, **Save** + dejalo activo.
3. Extraé la data y reconstruí:
   ```bash
   docker stop n8n-edit
   rm -rf data && mkdir data && docker cp n8n-edit:/home/node/.n8n/. ./data/
   docker build -t juancruzrobledo/n8n-active-ia:latest -f Dockerfile.preconfigured .
   docker push juancruzrobledo/n8n-active-ia:latest
   ```

---

## 🔒 Seguridad

- ✅ `data/` está en `.gitignore` (no se commitean credenciales)
- ✅ Las API Keys de Gemini las proporcionan los usuarios (no se almacenan en N8N)
- ✅ N8N solo debe ser accesible desde la red interna Docker
- ✅ En producción, NO exponer puerto 5678 externamente

---

## 📚 Referencias

- **Documentación del proyecto:** `docs/specs/10-INTEGRACIONES.md`
- **Especificación de workflows:** Ver pasos 3.1-3.3 arriba
- **N8N oficial:** https://docs.n8n.io/
- **Gemini API:** https://ai.google.dev/docs

---

## ✅ Checklist de Preconfiguración

- [ ] N8N levantado en modo configuración
- [ ] Workflow 1 creado y activo (corrección)
- [ ] Workflow 2 creado y activo (rúbrica)
- [ ] Workflow 3 creado y activo (health)
- [ ] Webhooks probados con curl
- [ ] N8N detenido (datos guardados en `data/`)
- [ ] Imagen construida con `build-image.sh`
- [ ] Imagen pusheada a Docker Hub (opcional)
- [ ] `docker-compose.yml` actualizado con la imagen
