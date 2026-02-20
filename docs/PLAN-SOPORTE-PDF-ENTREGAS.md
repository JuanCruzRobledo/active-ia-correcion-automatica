# Plan: Soporte de Entregas en Formato PDF

**Versión:** 1.0  
**Fecha:** 2026-02-20  
**Ref. Specs:** `docs/specs/03-REQUISITOS-FUNCIONALES.md` secciones 7 y 8  
**Estado:** 🟡 Pendiente de implementación

---

## 1. Contexto y Objetivo

Actualmente el sistema solo acepta entregas de código en formato ZIP, TXT o archivos de código fuente individuales (`.py`, `.java`, etc.). Todo el pipeline gira alrededor de consolidar ese código en un texto plano y enviarlo a N8N → Gemini.

El objetivo de este plan es agregar soporte completo para entregas en **formato PDF**, tanto en carga individual como en carga masiva (lotes), y adaptar el pipeline de corrección para que, cuando la entrega sea un PDF, se llame a un **nuevo flujo de N8N distinto** que procese el archivo como binario (ideal para materias como Matemática, Física, etc. donde el alumno entrega ejercicios resueltos a mano escaneados).

---

## 2. Principios de Implementación

Todos los cambios deben respetar los siguientes principios del proyecto:

- **Arquitectura en capas:** Router → Service → Repository. Nunca saltearse capas. Nunca lógica de negocio en routers.
- **Comentarios:** Docstrings en todas las funciones/clases con sección `Args:`, `Returns:`, `Raises:`. Referencia a specs cuando aplique.
- **Encabezados de archivo:** Cada archivo `.py` y `.tsx` comienza con su ruta y docstring de módulo, con `Ref:` a la spec correspondiente.
- **Esquemas Pydantic:** Toda comunicación entre capas usa schemas, nunca dicts crudos.
- **Manejo de errores:** `HTTPException` con códigos correctos desde los servicios. Nunca exponer tracebacks.
- **Estilo Python:** Typing estricto (`str | None`, `list[str]`, etc.), sin `Any` salvo casos muy justificados.
- **Estilo TypeScript/React:** Hooks personalizados en `hooks/`, servicios en `services/`, tipos en `types/`. Componentes funcionales con tipos explícitos.
- **Tests:** Un test nuevo por cada caso de éxito y error relevante. Mismo patrón que `test_entrega_service.py` y `test_consolidacion_service.py`.

---

## 3. Resumen de Impacto

| Capa | Archivo(s) | Tipo de cambio |
|---|---|---|
| **Modelo BD** | `app/models/entrega.py` | Agregar campo `pdf_contenido_b64` (Text opcional) |
| **Migración** | `alembic/versions/` | Nueva migración Alembic |
| **Enums** | — | No se requiere nuevo enum (se usa `archivo_tipo = "pdf"` como string, ya existe el patrón) |
| **Consolidación** | `app/services/consolidacion_service.py` | Sacar `.pdf` de `BINARY_EXTENSIONS` y agregar manejo explícito |
| **Entrega Service** | `app/services/entrega_service.py` | Aceptar PDF en carga individual y masiva |
| **Corrección Service** | `app/services/correccion_service.py` | Bifurcar flujo según `archivo_tipo` |
| **N8N Client** | `app/integrations/n8n_client.py` | Agregar `trigger_correction_pdf()` |
| **Schemas** | `app/schemas/entrega.py` | Actualizar `ContenidoEntrega` para PDFs |
| **Router Entregas** | `app/routers/entregas.py` | Sin cambios en firma, solo documentación |
| **Frontend Modal** | `frontend/src/features/entregas/components/CargaEntregaModal.tsx` | Aceptar PDF en modo individual, ocultar modos de consolidación para PDF |
| **Frontend Viewer** | `frontend/src/features/entregas/components/EntregaViewModal.tsx` | Mostrar embed de PDF en lugar de texto |
| **Tests** | `backend/tests/unit/services/` | Nuevos tests para cada caso PDF |

---

## 4. Fases de Implementación

### ✅ Checklist de progreso entre sesiones

```
Fase 1 - Modelo de datos
  [ ] 1.1 Agregar campo `pdf_contenido_b64` al modelo Entrega
  [ ] 1.2 Crear migración Alembic
  [ ] 1.3 Verificar migración en dev

Fase 2 - Capa de servicio: carga
  [ ] 2.1 Sacar `.pdf` de BINARY_EXTENSIONS en consolidacion_service.py
  [ ] 2.2 Agregar `_get_file_type()` retorne "pdf" para .pdf
  [ ] 2.3 Adaptar `crear_entrega_individual()` para PDF
  [ ] 2.4 Adaptar `crear_entrega_masiva()` para PDF en carpeta de alumno
  [ ] 2.5 Tests: `test_entrega_service.py` - casos PDF

Fase 3 - Capa de integración: corrección
  [ ] 3.1 Agregar `trigger_correction_pdf()` en n8n_client.py
  [ ] 3.2 Adaptar `corregir_individual()` para bifurcar según tipo
  [ ] 3.3 Ajustar validación de `contenido_preview` para PDFs
  [ ] 3.4 Tests: correccion_service - mock de N8N PDF

Fase 4 - Casos borde y robustez
  [ ] 4.1 Re-corrección de PDF (recorregir)
  [ ] 4.2 Sobrescritura de entrega PDF
  [ ] 4.3 Corrección en lote con mezcla txt + pdf
  [ ] 4.4 Historial de entregas PDF sobrescritas
  [ ] 4.5 Endpoint `/contenido` para PDFs (no debe fallar)

Fase 5 - Frontend
  [ ] 5.1 CargaEntregaModal: aceptar .pdf, ocultar modos de consolidación
  [ ] 5.2 EntregaViewModal: mostrar PDF embed si archivo_tipo == "pdf"

Fase 6 - Verificación final
  [ ] 6.1 Correr suite de tests completa
  [ ] 6.2 Prueba manual en dev: subir PDF individual
  [ ] 6.3 Prueba manual en dev: subir lote con PDFs
  [ ] 6.4 Prueba manual en dev: corregir entrega PDF
  [ ] 6.5 Prueba manual en dev: re-corregir entrega PDF
  [ ] 6.6 Prueba manual en dev: lote con mezcla PDF + ZIP

Fase 7 - Configuración N8N (Tarea del Usuario)
  [ ] 7.1 Crear webhook POST en N8N (`/webhook/corregir-pdf`)
  [ ] 7.2 Procesar payload (base64, rúbrica, API key) y conectar con Gemini Visión
  [ ] 7.3 Retornar respuesta JSON con el mismo esquema de corrección
```

---

## 5. Detalle de Cada Fase

---

### Fase 1 — Modelo de Datos

**Archivo:** `app/models/entrega.py`

El modelo `Entrega` necesita un lugar donde guardar el contenido binario del PDF para poder enviarlo a N8N en el momento de la corrección. Se almacena como **Base64 en un campo `Text`**, siguiendo el mismo patrón que ya usa el sistema para PDFs de rúbricas (`rubric_service.py` → `trigger_rubric_generation` manda `pdf_base64`).

**Campo a agregar:**
```python
pdf_contenido_b64: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
)  # Contenido del PDF codificado en base64 (solo para archivo_tipo='pdf')
```

> ⚠️ **Importante:** El campo `archivo_tipo` ya es un `String(10)` sin restricción de enum a nivel base de datos, por lo que agregar `"pdf"` como valor no requiere alterar el tipo en Postgres — solo agregar el nuevo campo de datos.

**Migración Alembic:**
```bash
# Desde backend/
alembic revision --autogenerate -m "add_pdf_contenido_b64_to_entregas"
alembic upgrade head
```

Verificar que el archivo generado en `alembic/versions/` contenga correctamente `op.add_column('entregas', sa.Column('pdf_contenido_b64', sa.Text(), nullable=True))`.

---

### Fase 2 — Capa de Servicio: Carga de Entregas

#### 2.1 — `app/services/consolidacion_service.py`

- Remover `.pdf` del set `BINARY_EXTENSIONS`. El PDF ya no es un "binario rechazado" a nivel global; ahora es un tipo de archivo soportado con su propio camino.
- **No** agregar lógica de procesamiento de PDF aquí. Este servicio solo consolida código en texto; el PDF no pasa por aquí.

#### 2.2 — `app/services/entrega_service.py` — `_get_file_type()`

Agregar `"pdf"` como tipo de retorno reconocido:

```python
# Antes: .pdf caía en BINARY_EXTENSIONS → return "binary"
# Después:
elif extension == ".pdf":
    return "pdf"
```

#### 2.3 — `crear_entrega_individual()` - Soporte PDF

**Flujo actual (bloqueante para PDF):**
1. Detecta tipo → `.pdf` → `binary` → **rechaza con 400**

**Flujo nuevo:**
1. Detecta tipo → `.pdf` → `"pdf"` → **camino alternativo**
2. Lee el archivo en bytes
3. Codifica en base64: `base64.b64encode(contenido_bytes).decode("utf-8")`
4. `contenido_consolidado = None` (no aplica para PDFs)
5. `contenido_preview = "[Entrega en formato PDF]"` (placeholder legible)
6. `archivos_incluidos = [archivo.filename]`
7. Guarda en `pdf_contenido_b64` el base64
8. Crea la entrega con `archivo_tipo = "pdf"`

El flujo de sobrescritura (`sobrescribir=True`) aplica igual que para código — se guarda en historial y se reemplaza. El historial (`EntregaHistorial`) solo guarda `contenido_preview` y no el PDF en sí (mantener comportamiento actual; el historial no necesita guardar el binario).

#### 2.4 — `crear_entrega_masiva()` - Soporte PDF en lotes

En el bloque `elif len(alumno_files) == 1:` (archivo único en la carpeta del alumno), el código actual rechaza binarios. El cambio:

```python
archivo_tipo_temp = self._get_file_type(archivo_nombre)
if archivo_tipo_temp == "pdf":
    # Nuevo camino para PDF en lote
    pdf_contenido = zip_file.read(single_file_path)
    pdf_b64 = base64.b64encode(pdf_contenido).decode("utf-8")
    archivo_tipo = "pdf"
    contenido_bytes_alumno = pdf_contenido
    # El resto del flujo (hash, tamaño) continúa igual
    # Pero _consolidar_archivo NO se llama → se setea manualmente:
    #   contenido_consolidado = None
    #   contenido_preview = "[Entrega en formato PDF]"
    # y pdf_contenido_b64 = pdf_b64
elif archivo_tipo_temp == "binary":
    # Mantenemos el rechazo para otros binarios (imágenes, exe, etc.)
    errores.append(...)
    continue
```

> ⚠️ En el caso donde hay **múltiples archivos sueltos** en la carpeta, si uno de ellos es un PDF y los otros son de código, el PDF se **ignora** (comportamiento conservador — no sabemos cuál es la entrega real). Si la **única** forma de manejar esto de otra manera es requerimiento del usuario, se documenta como futura mejora.

#### 2.5 — Tests nuevos (`test_entrega_service.py`)

Siguiendo el mismo patrón de fixtures y estructura de clase:

- `test_crear_entrega_individual_pdf_success` — sube PDF, verifica `archivo_tipo=="pdf"`, `pdf_contenido_b64` no nulo, `contenido_consolidado` nulo
- `test_crear_entrega_individual_pdf_guarda_preview_placeholder` — verifica que `contenido_preview == "[Entrega en formato PDF]"`
- `test_crear_entrega_masiva_pdf_en_carpeta_alumno` — ZIP con carpeta de alumno que contiene solo un PDF
- `test_crear_entrega_masiva_otros_binarios_siguen_rechazados` — ZIP con imagen .png dentro de carpeta → sigue en errores

---

### Fase 3 — Capa de Integración: Corrección

#### 3.1 — `app/integrations/n8n_client.py` — `trigger_correction_pdf()`

Agregar nuevo método al final de la clase `N8NClient`, siguiendo exactamente el mismo patrón de `trigger_correction()`:

```python
async def trigger_correction_pdf(self, payload: dict) -> dict[str, Any]:
    """
    Trigger the PDF correction workflow in N8N.

    Args:
        payload: Dictionary containing:
            - pdf_base64: PDF content encoded in Base64
            - rubrica: Rubric with evaluation criteria
            - api_key: User's Gemini API key
            - contexto: Additional context (materia, alumno)

    Returns:
        Dictionary with correction results:
            - success: bool
            - correccion: Correction data (if successful)
            - error: Error details (if failed)

    Raises:
        N8NTimeoutError: If the request times out
        N8NError: For other N8N-related errors
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{self.base_url}/webhook/corregir-pdf",
                json=payload,
                timeout=self.correction_timeout,
            )
            response.raise_for_status()
            try:
                return response.json()
            except Exception as json_error:
                raise N8NError(
                    f"Error parseando respuesta JSON de N8N (PDF). "
                    f"Status: {response.status_code}, "
                    f"Body (first 500 chars): {response.text[:500]}"
                )
        except httpx.TimeoutException:
            raise N8NTimeoutError("Timeout esperando respuesta de N8N (corrección PDF)")
        except httpx.HTTPStatusError as e:
            raise N8NError(f"Error HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise N8NError(f"Error de conexión: {str(e)}")
```

El webhook de N8N se configura en la variable de entorno `N8N_BASE_URL` ya existente, usando la ruta `/webhook/corregir-pdf`.

#### 3.2 — `app/services/correccion_service.py` — Bifurcación por tipo

**En `corregir_individual()`**, el cambio clave está en la validación del contenido y en la construcción del payload:

**Validación actual (falla para PDF):**
```python
if not entrega.contenido_preview:
    raise HTTPException(400, "La entrega no tiene contenido consolidado")
```

**Nueva validación:**
```python
if entrega.archivo_tipo == "pdf":
    if not entrega.pdf_contenido_b64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La entrega PDF no tiene contenido disponible para corrección",
        )
else:
    if not entrega.contenido_preview:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La entrega no tiene contenido consolidado",
        )
```

**Construcción del payload y llamada a N8N:**

Extraer en un método privado `_build_pdf_correction_payload()` siguiendo el mismo patrón que `_build_correction_payload()`:

```python
def _build_pdf_correction_payload(
    self, entrega: Any, rubrica: Any, api_key: str
) -> dict[str, Any]:
    """
    Build payload for N8N PDF correction webhook.

    Args:
        entrega: Entrega object with pdf_contenido_b64.
        rubrica: Rubrica object.
        api_key: Decrypted Gemini API key.

    Returns:
        Payload dictionary for N8N PDF correction.
    """
    return {
        "pdf_base64": entrega.pdf_contenido_b64,
        "rubrica": {
            "titulo": rubrica.titulo,
            "descripcion": rubrica.descripcion or "",
            "tipo": rubrica.tipo.value,
            "puntaje_maximo": rubrica.puntaje_maximo,
            "metadata": rubrica.metadata_json or {},
            "criterios": rubrica.criterios_json or [],
            "penalizaciones": rubrica.penalizaciones_json or [],
            "condiciones_desaprobacion": rubrica.condiciones_desaprobacion_json or [],
        },
        "api_key": api_key,
        "contexto": {
            "materia": entrega.comision.materia.nombre,
            "alumno": entrega.alumno_nombre,
        },
    }
```

**Bifurcación en `corregir_individual()`:**
```python
# Build payload and call N8N based on entrega type
if entrega.archivo_tipo == "pdf":
    payload = self._build_pdf_correction_payload(entrega, rubrica, api_key)
    result = await self._call_n8n_pdf_with_retry(payload)
else:
    payload = self._build_correction_payload(entrega, rubrica, api_key)
    result = await self._call_n8n_with_retry(payload)
```

Agregar `_call_n8n_pdf_with_retry()` con la misma lógica de reintentos que `_call_n8n_with_retry()` pero llamando a `self.n8n_client.trigger_correction_pdf(payload)`.

> ℹ️ La respuesta de N8N para PDFs debe tener **exactamente la misma estructura** que para código: `{ "success": bool, "correccion": { ... } }`. El parseo con `_parse_gemini_response()` se reutiliza sin cambios. El flujo de n8n para PDFs debe respetar el mismo contrato de respuesta.

#### 3.3 — Tests nuevos (`correccion_service` o nuevo archivo)

- `test_corregir_entrega_pdf_llama_webhook_pdf` — mock de `n8n_client.trigger_correction_pdf`, verifica que se llama con `pdf_base64` y no con `codigo`
- `test_corregir_entrega_codigo_sigue_usando_webhook_texto` — verifica que entregas ZIP/TXT siguen llamando al webhook original

---

### Fase 4 — Casos Borde y Robustez

Estos casos deben funcionar **sin errores** después del cambio. Algunos ya funcionan por herencia del flujo, pero deben verificarse explícitamente:

#### 4.1 — Re-corrección de PDF (`recorregir`)

`recorregir()` llama directamente a `corregir_individual()`. Si `corregir_individual()` ya bifurca correctamente, la re-corrección de PDF funciona sin cambios adicionales. **Verificar en test.**

#### 4.2 — Sobrescribir entrega PDF

En `crear_entrega_individual()`, la lógica de sobrescritura copia todos los campos. Asegurarse de que `pdf_contenido_b64` también se actualiza al sobrescribir:

```python
entrega_existente.pdf_contenido_b64 = nuevo_pdf_b64  # ← agregar
entrega_existente.contenido_consolidado = None         # ← limpiar si cambia de tipo
```

#### 4.3 — Corrección en lote con mezcla TXT + PDF

`corregir_lote()` llama a `corregir_individual()` por cada ID. Si ese método bifurca, el lote funciona transparentemente. **No hay cambios adicionales aquí.**

#### 4.4 — Historial de entregas PDF

`HistorialService.guardar_version_anterior()` guarda `contenido_preview` de la versión anterior. Para PDFs el preview es `"[Entrega en formato PDF]"`. El binario del PDF **no se guarda en historial** (decisión de diseño: evitar duplicar datos pesados). Verificar que el historial no intenta acceder a `contenido_consolidado` ni falla.

#### 4.5 — Endpoint `GET /entregas/{id}/contenido` para PDFs

El endpoint `obtener_contenido` actualmente siempre devuelve texto. Para PDFs se debe devolver una respuesta significativa en lugar de error. Dos opciones:

**Opción A (recomendada):** Agregar campo `es_pdf: bool` y `pdf_contenido_b64: str | None` al schema `ContenidoEntrega`:

```python
class ContenidoEntrega(BaseModel):
    entrega_id: int
    alumno_nombre: str
    es_pdf: bool = Field(default=False, description="Indica si la entrega es un PDF")
    contenido_consolidado: str | None = Field(
        default=None,
        description="Código consolidado (None para entregas PDF)",
    )
    pdf_contenido_b64: str | None = Field(
        default=None,
        description="Contenido del PDF en Base64 (solo para entregas PDF)",
    )
    archivos_incluidos: list[str]
    total_lineas: int
    total_caracteres: int
```

El servicio `obtener_contenido()` se adapta:

```python
if entrega.archivo_tipo == "pdf":
    return ContenidoEntrega(
        entrega_id=entrega.id,
        alumno_nombre=entrega.alumno_nombre,
        es_pdf=True,
        contenido_consolidado=None,
        pdf_contenido_b64=entrega.pdf_contenido_b64,
        archivos_incluidos=entrega.archivos_incluidos or [entrega.archivo_nombre],
        total_lineas=0,
        total_caracteres=0,
    )
```

---

### Fase 5 — Frontend

#### 5.1 — `CargaEntregaModal.tsx`

**Cambios en el formulario individual:**

1. El hint de texto en el dropzone ya dice `'Cualquier formato: .zip, .txt, .py, .java, etc.'` — agregar `.pdf` al texto.

2. Detectar si el archivo seleccionado es PDF:
   ```typescript
   const isPdfFile = selectedFile?.name.toLowerCase().endsWith('.pdf');
   ```

3. Ocultar la sección "Modo de Procesamiento" cuando el archivo es PDF (no tiene sentido para PDFs):
   ```typescript
   const shouldShowModoProcessing =
     mode === 'masivo' ||
     (mode === 'individual' && isZipFile) ||
     (mode === 'individual' && !isPdfFile && !isAlreadyConsolidated);
   ```

4. Mostrar un mensaje informativo cuando se selecciona un PDF (similar al mensaje de "Archivo ya procesado" para TXT):
   ```tsx
   {isPdfFile && (
     <div className="flex items-start gap-2 bg-blue-50 border border-blue-200 rounded-lg p-3">
       <FileText className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
       <div>
         <p className="text-sm font-medium text-blue-800">Entrega en PDF</p>
         <p className="text-xs text-blue-600 mt-0.5">
           Este PDF se enviará directamente al flujo de corrección especializado.
         </p>
       </div>
     </div>
   )}
   ```

5. El modo masivo (`'masivo'`) no requiere cambios en el formulario — el ZIP puede contener PDFs internamente y el backend los maneja.

#### 5.2 — `EntregaViewModal.tsx`

El modal de visualización de una entrega hoy muestra el `contenido_consolidado` como texto. Para PDFs, debe mostrar un visor PDF embebido.

Condición sobre `archivo_tipo === 'pdf'` (disponible en el tipo `EntregaDetailResponse`):

```tsx
{entrega.archivo_tipo === 'pdf' ? (
  <PDFViewer pdfBase64={contenidoEntrega?.pdf_contenido_b64} />
) : (
  <CodeViewer contenido={contenidoEntrega?.contenido_consolidado} />
)}
```

El componente `PDFViewer` se implementa como un `<iframe>` con `src` construido desde el base64:
```tsx
const pdfUrl = `data:application/pdf;base64,${pdfBase64}`;
// <iframe src={pdfUrl} width="100%" height="600px" />
```

> ⚠️ Los PDFs grandes pueden ser lentos de renderizar en el navegador. El modal debe mostrar un spinner mientras carga y manejar el caso donde `pdf_contenido_b64` no está disponible.

---

## 6. Plan de Verificación

### 6.1 — Tests Unitarios Automáticos

```bash
# Desde la raíz del proyecto, con el backend corriendo:
cd backend
pytest tests/unit/services/test_entrega_service.py -v
pytest tests/unit/services/test_consolidacion_service.py -v
pytest tests/unit/ -v
```

Los tests esperados nuevos (a crear en la Fase 2 y 3):
- `test_crear_entrega_individual_pdf_success`
- `test_crear_entrega_individual_pdf_guarda_preview_placeholder`
- `test_crear_entrega_masiva_pdf_en_carpeta_alumno`
- `test_crear_entrega_masiva_otros_binarios_siguen_rechazados`
- `test_corregir_entrega_pdf_llama_webhook_pdf`
- `test_corregir_entrega_codigo_sigue_usando_webhook_texto`

### 6.2 — Prueba Manual: Subida Individual PDF

1. Ingresar como tutor.
2. Ir a una comisión con una rúbrica activa.
3. Clickear "Subir Entregas" → modo "Entrega Individual".
4. Ingresar nombre de alumno.
5. Seleccionar un archivo `.pdf` cualquiera.
6. Verificar que **no aparece** la sección "Modo de Procesamiento".
7. Verificar que **sí aparece** el mensaje informativo de "Entrega en PDF".
8. Hacer click en "Subir Entrega".
9. **Resultado esperado:** La entrega aparece en la tabla con `archivo_tipo = pdf` y estado `SUBIDA`.

### 6.3 — Prueba Manual: Subida Masiva con PDFs

1. Crear un ZIP con la siguiente estructura:
   ```
   lote_test.zip
   ├── garcia_maria/
   │   └── ejercicios.pdf
   ├── perez_juan/
   │   └── tp1.zip  (ZIP de código de Python)
   └── rodriguez_carlos/
       └── solucion.pdf
   ```
2. Subir el ZIP en modo "Subir Lote".
3. **Resultado esperado:** 3 entregas procesadas exitosamente. garcia_maria y rodriguez_carlos con `archivo_tipo = pdf`, perez_juan con `archivo_tipo = zip`.

### 6.4 — Prueba Manual: Corregir Entrega PDF (individual)

1. Seleccionar una entrega con `archivo_tipo = pdf` y hacer click en "Corregir".
2. **Resultado esperado:** El sistema llama al webhook `/webhook/corregir-pdf` de N8N (verificable en los logs de N8N). La corrección se guarda normalmente con nota y criterios.

### 6.5 — Prueba Manual: Re-corregir Entrega PDF

1. Sobre una entrega PDF ya corregida, hacer click en "Re-corregir".
2. **Resultado esperado:** Se elimina la corrección anterior, se genera una nueva. No debe aparecer ningún error 400 por "contenido no disponible".

### 6.6 — Prueba Manual: Lote de corrección mixto (PDF + TXT)

1. Seleccionar en la tabla 3 entregas: 2 de tipo `zip`/`txt` y 1 de tipo `pdf`.
2. Hacer click en "Corregir seleccionadas".
3. **Resultado esperado:** Las 2 entregas de código llaman a `/webhook/corregir`. La entrega PDF llama a `/webhook/corregir-pdf`. Las 3 finalizan con estado `CORREGIDA`.

### 6.7 — Prueba Manual: Vista de entrega PDF

1. Hacer click en el botón "Ver" de una entrega PDF.
2. **Resultado esperado:** El modal muestra el PDF renderizado (no un bloque de código vacío o un error).

---

## 7. Fase 7 — Configuración en N8N (Tarea Manual del Usuario)

Para que el nuevo flujo funcione extremo a extremo, **el usuario o administrador debe realizar las siguientes configuraciones en su instancia de N8N**:

1. **Crear nodo de Webhook:** Escuchar peticiones `POST` en la ruta `/webhook/corregir-pdf`.
2. **Extraer Payload:** El payload recibido traerá la siguiente estructura:
   ```json
   {
     "pdf_base64": "JVBERi0xLjQK...",
     "rubrica": { ... },
     "api_key": "AIzaSy...",
     "contexto": { "materia": "...", "alumno": "..." }
   }
   ```
3. **Conexión Multimodal:** Utilizar el nodo de **Google Gemini** (idealmente configurando un modelo como `gemini-1.5-flash` o `gemini-1.5-pro` que soporte documentos/imágenes). Transformar el `pdf_base64` a un archivo binario dentro de N8N si el nodo así lo requiere, o pasarlo como *inline data* en el prompt.
4. **Construir Respuesta:** Es **crítico** que el webhook final responda al backend con un JSON que tenga el mismo formato esperado por el servicio existente:
   ```json
   {
     "success": true,
     "correccion": {
       "nota": 85,
       "estado_aprobacion": "APROBADO",
       "fortalezas": ["..."],
       "debilidades": ["..."],
       "criterios": [
           { "id_criterio": "c1", "puntaje_obtenido": 100, "justificacion": "..." }
       ]
     }
   }
   ```

---

## 7. Apéndice: Estado de Archivos por Fase

### Archivos que cambian (Backend)

| Archivo | Fase | Tipo de Cambio |
|---|---|---|
| `app/models/entrega.py` | 1 | Agregar campo `pdf_contenido_b64` |
| `alembic/versions/xxx_add_pdf.py` | 1 | Nueva migración (autogenerada) |
| `app/services/consolidacion_service.py` | 2.1 | Remover `.pdf` de `BINARY_EXTENSIONS` |
| `app/services/entrega_service.py` | 2.2–2.4 | Lógica de carga individual y masiva para PDF |
| `app/integrations/n8n_client.py` | 3.1 | Agregar `trigger_correction_pdf()` |
| `app/services/correccion_service.py` | 3.2 | Bifurcación por tipo, nuevo payload builder |
| `app/schemas/entrega.py` | 4.5 | Actualizar `ContenidoEntrega` con campos PDF |
| `tests/unit/services/test_entrega_service.py` | 2.5 | Tests nuevos de PDF |
| `tests/unit/services/test_correccion_service.py` | 3.3 | Tests nuevos de bifurcación |

### Archivos que cambian (Frontend)

| Archivo | Fase | Tipo de Cambio |
|---|---|---|
| `features/entregas/components/CargaEntregaModal.tsx` | 5.1 | Soporte PDF en carga individual |
| `features/entregas/components/EntregaViewModal.tsx` | 5.2 | Visor PDF embebido |
| `features/entregas/types/index.ts` | 5.2 | Agregar `pdf_contenido_b64` al tipo de `ContenidoEntrega` |

### Archivos que NO cambian

- `app/routers/entregas.py` — La firma del endpoint no varía
- `app/routers/correcciones.py` — La firma no varía
- `app/models/correccion.py` — El modelo de corrección no cambia (la corrección de PDF produce la misma estructura de nota + criterios)
- `app/repositories/` — Ningún repositorio requiere cambios
- `app/schemas/correccion.py` — El schema de corrección no varía

---

## 8. Notas y Decisiones de Diseño

1. **PDF en base64 en la BD:** Se eligió guardar el base64 en la base de datos (campo `Text`) para mantener la simplicidad del sistema actual, que no tiene un servicio de almacenamiento de archivos externo. Para PDFs muy grandes (> 10 MB) esto puede ser un problema. Si en el futuro se añade un servicio de storage (S3, MinIO), se puede migrar a guardar solo la URL.

2. **Historial sin binario PDF:** El `EntregaHistorial` no guarda el PDF en sí, solo el `contenido_preview = "[Entrega en formato PDF]"`. Esto es intencional para evitar duplicar datos pesados.

3. **Mezcla de archivos en carpeta masiva:** Si la carpeta de un alumno dentro del ZIP masivo contiene tanto archivos `.pdf` como archivos de código, el comportamiento conservador es procesar solo el código (ignorar el PDF). Esto puede revisarse como mejora futura.

4. **Contrato de respuesta N8N PDF:** El flujo de N8N para PDFs **debe** devolver exactamente la misma estructura JSON de respuesta que el flujo de código: `{ "success": true, "correccion": { "nota": ..., "criterios": [...], "fortalezas": [...], ... } }`. Si no, `_parse_gemini_response()` fallará.

5. **Webhook URL:** El endpoint de N8N para PDFs es `/webhook/corregir-pdf` (convención del proyecto). Se configura junto con el `N8N_BASE_URL` existente — no requiere nueva variable de entorno.
