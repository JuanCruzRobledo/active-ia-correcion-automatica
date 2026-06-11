# Propuesta de fix — workflow de corrección de código

> Estado: **APLICADO AL ARCHIVO VERSIONADO** (junio 2026). El fix (evidencias +
> `instrucciones_puntuacion` + metadata) ya está en
> `n8n/workflows/correccion-workflow.json`. **FALTA re-importar a la instancia de
> n8n** (paso manual — ver abajo). Producción NO cambia hasta que se re-importe.
>
> ⚠️ **El MCP de N8N_ACTIVIA NO puede importar/actualizar workflows** (solo
> `search_workflows`, `get_workflow_details`, `execute_workflow`). La re-importación
> es manual desde la UI de n8n.
>
> ⚠️ **La instancia viva está MÁS atrasada que el archivo versionado.** El nodo
> "Construir Body Gemini" en producción (workflow "Correcion Automatica",
> id `ayK3hQN2YwoVK2UO`) ni siquiera tiene penalizaciones ni condiciones de
> desaprobación en el prompt, y su `responseSchema` no incluye
> `nota_antes_penalizaciones`. Re-importar trae TODO eso de una.
>
> ⚠️ **Modelos Gemini desalineados:** producción usa `gemini-3.5-flash`, el archivo
> versionado `gemini-3.1-flash-lite-preview`, el nodo de rúbrica `gemini-2.5-flash`
> y el health-check `gemini-2.0-flash`. Conviene unificar (decisión pendiente).

## El problema

El nodo **"Construir Body Gemini"** de `correccion-workflow.json` arma el texto de
criterios SOLO con `id`, `nombre`, `peso` y `descripcion`. No le manda al modelo:
- subcriterios + **evidencias** (el checklist verificable),
- `instrucciones_puntuacion` del criterio,
- la `metadata` de la rúbrica (lenguaje, framework, formato, etc.).

El workflow de PDF (`correccion-pdf-workflow.json`) ya manda evidencias: es el patrón.

## El fix (JavaScript del nodo "Construir Body Gemini")

Reemplazar el armado de `criteriosTexto` por esta versión:

```javascript
// Criterios CON subcriterios + evidencias + instrucciones de puntuación
let criteriosTexto = '';
for (const criterio of rubrica.criterios) {
  criteriosTexto += `- ID: ${criterio.id}\n  Nombre: ${criterio.nombre}\n  Peso: ${criterio.peso} pts\n  Descripción: ${criterio.descripcion}\n`;
  if (criterio.instrucciones_puntuacion) {
    criteriosTexto += `  Instrucciones de puntuación: ${criterio.instrucciones_puntuacion}\n`;
  }
  if (criterio.subcriterios && criterio.subcriterios.length > 0) {
    criteriosTexto += `  Evidencias esperadas (checklist verificable en la entrega):\n`;
    for (const sub of criterio.subcriterios) {
      if (sub.descripcion) criteriosTexto += `  - ${sub.descripcion}\n`;
      if (Array.isArray(sub.evidencias)) {
        for (const ev of sub.evidencias) {
          criteriosTexto += `    * ${ev}\n`;
        }
      }
    }
  }
  criteriosTexto += `\n`;
}
```

Y agregar el contexto de metadata (antes de armar el `prompt`):

```javascript
let metadataTexto = '';
if (rubrica.metadata && typeof rubrica.metadata === 'object') {
  for (const [k, v] of Object.entries(rubrica.metadata)) {
    metadataTexto += `- ${k}: ${v}\n`;
  }
}
```

Insertar en el `prompt`, después del bloque "## RÚBRICA DE EVALUACIÓN":

```
## CONTEXTO ADICIONAL

${metadataTexto || 'Sin metadata adicional.'}
```

La instrucción 1 de evaluación conviene que diga "verificando las evidencias
esperadas de cada criterio contra el código" para que el modelo use el checklist.

> Las `penalizaciones` y `condiciones_desaprobacion` ya están contempladas en la
> versión del archivo versionado; el fix es SOLO lo de arriba (evidencias,
> instrucciones_puntuación, metadata).

## Referencia viva

`scripts/simular_correccion.py` (función `build_prompt`) implementa exactamente
este prompt corregido en Python. Sirve como espejo de cómo quedó el nodo y para
testear antes de re-importar. Self-contained (solo stdlib).

```bash
# Ver el prompt que produce el nodo arreglado (sin llamar a Gemini):
python scripts/simular_correccion.py --ejemplo --print-prompt

# Correr la corrección de verdad y compararla con la de n8n:
python scripts/simular_correccion.py --rubrica rub.json --codigo entrega.txt \
    --materia "Programación 1" --alumno "Juan Pérez" --api-key <GEMINI_KEY>
```

## Para aplicar

1. ✅ **HECHO** — Nodo "Construir Body Gemini" editado en `correccion-workflow.json`
   (evidencias + `instrucciones_puntuacion` + metadata + instrucción 1). JSON y JS
   validados (`node --check`).
2. ⬜ (Opcional) Unificar la URL del modelo Gemini entre los nodos (ver header).
3. ⬜ **Re-importar manualmente** el workflow en la instancia de n8n (el MCP no puede
   hacerlo). El fix NO surte efecto en producción hasta importar. OJO: en la instancia
   todos los flujos están en UN workflow ("Correcion Automatica"); reemplazar solo el
   nodo "Construir Body Gemini", no pisar los demás.
4. ⬜ Probar con `scripts/simular_correccion.py` sobre una entrega de referencia y
   comparar contra la corrección real de n8n.
