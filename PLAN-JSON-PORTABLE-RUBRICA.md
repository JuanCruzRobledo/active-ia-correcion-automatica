# 📋 Handoff: JSON portable de rúbrica (exportar + importar con autocompletado)

**Proyecto:** Active-IA
**Fecha:** 2026-07-21
**Para:** implementación (feature)
**Precedente:** el "Modo JSON" ya existe en `RubricaEditor.tsx` / `RubricaJSONMode.tsx`, esto es completarlo, no crearlo de cero.

---

## 🎯 Problema a resolver

Hoy ya se puede pegar/subir un `.json` al crear o editar una rúbrica (Modo JSON del modal), y ya existe un botón "Copiar JSON actual" cuando se está editando. El problema es que **ese circuito ignora el modo de consolidación**:

- **Al exportar** (`RubricaEditor.tsx`, armado de `currentJSON` ~línea 628-639): el objeto que se serializa para copiar solo trae `titulo`, `descripcion`, `metadata`, `criterios`, `penalizaciones`, `condiciones_desaprobacion`. **Nunca incluye `modo_consolidacion` ni `extensiones_personalizadas`.**
- **Al importar** (`handleLoadJSON`, ~línea 251-277): aunque el JSON pegado SÍ traiga esos dos campos, el código nunca hace `setValue('modo_consolidacion', ...)` ni `setValue('extensiones_personalizadas', ...)`. Se pierden y el form queda en el default `solo_codigo`.

Y en la lista (`RubricasPage.tsx`, dropdown de acciones por fila) **no existe ninguna forma de bajar el JSON de una rúbrica ya guardada** — el dropdown solo tiene Editar / Duplicar / Descargar PDF Completo / Descargar Guía Estudiante / Eliminar-Restaurar.

Resultado: hoy es imposible bajar el JSON completo de una rúbrica (con su modo de consolidación) y usarlo para levantar otra rúbrica nueva "clonada" 1:1 sin tener que volver a tocar a mano el selector de tipo de proyecto.

---

## 🎯 Objetivo de la feature

1. **Exportar**: poder descargar el JSON completo de una rúbrica desde **dos lugares**:
   - El dropdown de acciones de cada fila en `RubricasPage.tsx` (rúbrica ya guardada).
   - Dentro del modal `RubricaEditor.tsx`, en modo edición (para bajar el JSON de lo que se está editando, incluidos cambios sin guardar).
2. Ese JSON tiene que incluir **`modo_consolidacion`** y, si corresponde (`modo_consolidacion === 'personalizado'`), **`extensiones_personalizadas`**.
3. **Importar**: pegar/subir ese JSON en el Modo JSON del modal tiene que autocompletar el form al 100%, incluido el selector de tipo de proyecto — sin que el usuario tenga que volver a elegirlo a mano.
4. **Tolerancia total en la importación**: si el JSON pegado **no trae** `modo_consolidacion` (JSONs viejos, armados a mano, o de otra fuente), **no es un error** — simplemente no se pisa el valor actual/default del form. Si el campo **está presente**, es un atajo que autocompleta. Mismo criterio aplica a cualquier otro campo opcional (`metadata`, `penalizaciones`, `condiciones_desaprobacion`, `extensiones_personalizadas`): ausencia ≠ error, solo se saltea ese autocompletado puntual.

---

## 🧩 Propuesta de solución

### 1. Un único "shape portable" compartido entre exportar e importar

Para que el dropdown de la lista, el botón del modal y el importador hablen exactamente el mismo idioma, conviene extraer una función pura nueva, por ejemplo en `frontend/src/features/rubricas/utils/rubricaPortableJson.ts`:

```typescript
export interface RubricaPortableJSON {
  titulo: string;
  descripcion: string;
  metadata: Record<string, any>;
  criterios: Criterio[];
  penalizaciones: Penalizacion[];
  condiciones_desaprobacion: CondicionDesaprobacion[];
  modo_consolidacion: ModoConsolidacion;
  extensiones_personalizadas: string[] | null;
}

export function buildRubricaPortableJSON(data: {
  titulo: string;
  descripcion: string;
  metadata: Record<string, any>;
  criterios: Criterio[];
  penalizaciones: Penalizacion[];
  condiciones_desaprobacion: CondicionDesaprobacion[];
  modo_consolidacion: ModoConsolidacion;
  extensiones_personalizadas: string[] | null;
}): RubricaPortableJSON {
  return {
    titulo: data.titulo,
    descripcion: data.descripcion,
    metadata: data.metadata ?? {},
    criterios: data.criterios,
    penalizaciones: data.penalizaciones ?? [],
    condiciones_desaprobacion: data.condiciones_desaprobacion ?? [],
    modo_consolidacion: data.modo_consolidacion ?? 'solo_codigo',
    extensiones_personalizadas:
      data.modo_consolidacion === 'personalizado'
        ? (data.extensiones_personalizadas ?? [])
        : null,
  };
}
```

Deliberadamente **NO** se incluyen `id`, `materia_id`, `tipo`, `numero`, `anio`, `activa`, `moodle_assign_id`, `created_at`/`updated_at`: son identidad de esa instancia particular de rúbrica (materia, año, asignación de Moodle), no del **contenido reusable**. Meterlos rompería el caso de uso principal ("bajo el JSON de esta rúbrica y lo uso para armar otra en otra materia/año").

Esta función la consumen los tres puntos de la feature (secciones 2, 3 y 4).

### 2. Descargar JSON — dropdown de `RubricasPage.tsx`

`RubricaListItem` (el item de la lista) **no trae** `criterios_json` ni el resto de la estructura — es un DTO liviano para la tabla. Para armar el JSON completo hace falta el detalle: `GET /rubricas/{id}` (`rubricasService.getById`).

Ese endpoint es **`require_coordinador_or_admin`** (`backend/app/routers/rubricas.py` línea ~136) — un TUTOR pegándole recibe 403. Por eso:

- El ítem "Descargar JSON" del dropdown debe estar **gateado a coordinador/admin** (mismo patrón de chequeo de rol que ya usa la página con `useAuth()` para `sinMateriasAsignadas`).
- Al hacer click, disparar un fetch imperativo (`rubricasService.getById(rubrica.id)`, no hace falta un hook declarativo nuevo) → con la respuesta, `buildRubricaPortableJSON(...)` → serializar con `JSON.stringify(portable, null, 2)` → Blob + link de descarga, mismo patrón que ya usa `downloadPDF` en `rubricas-service.ts` (línea ~125), pero con `type: 'application/json'` y sin pegarle a un endpoint de backend (se arma 100% en el cliente a partir del detalle ya obtenido).
- Nombre de archivo sugerido: `Rubrica_{tipo}_{numero}_{titulo}.json` (mismo criterio que ya usan `handleDownloadPDF` / `handleDownloadPDFResumido` en `RubricasPage.tsx` para armar el nombre del PDF).
- Ícono sugerido: `FileJson` de `lucide-react` (ya se importan `Download` y `FileDown` de la misma librería para los PDF).

### 3. Descargar JSON — modal `RubricaEditor.tsx`

Cuando `isEditing`, agregar un botón "Descargar JSON" (puede vivir al lado del botón "Copiar JSON actual" que ya existe en `RubricaJSONMode`, o en el footer del modal). A diferencia del dropdown, acá **no hace falta pegarle a la API**: el modal ya tiene todo en el form vía `watch()`. Simplemente:

```typescript
const portable = buildRubricaPortableJSON({
  titulo: watch('titulo'),
  descripcion: watch('descripcion'),
  metadata: watch('metadata'),
  criterios: watch('criterios'),
  penalizaciones: watch('penalizaciones'),
  condiciones_desaprobacion: watch('condiciones_desaprobacion'),
  modo_consolidacion: watch('modo_consolidacion'),
  extensiones_personalizadas: watch('extensiones_personalizadas'),
});
```

y mismo Blob + descarga que en el punto 2. De paso, el `currentJSON` que ya se pasa a `RubricaJSONMode` (línea ~628-639, hoy usado para "Copiar JSON actual") debería armarse con esta misma función para que copiar y descargar sean consistentes.

### 4. Importar JSON — autocompletar tolerante

En `handleLoadJSON` (`RubricaEditor.tsx` ~línea 251-277), agregar, **después** de la validación mínima existente (`titulo`, `descripcion`, `criterios` como array — esa se mantiene igual):

```typescript
// Atajos opcionales: si vienen, autocompletan; si no vienen, no se toca nada.
if (parsed.modo_consolidacion) {
  setValue('modo_consolidacion', parsed.modo_consolidacion);
}
if (parsed.extensiones_personalizadas) {
  setValue('extensiones_personalizadas', parsed.extensiones_personalizadas);
}
```

Puntos a cuidar:
- **No usar `?? 'solo_codigo'`** a secas — eso pisaría con el default lo que el usuario ya hubiera tocado a mano en el selector antes de pegar el JSON. Solo `setValue` si el campo vino presente en el JSON parseado.
- Si `parsed.modo_consolidacion` viene con un valor que no es ninguno de los 4 válidos (`solo_codigo` / `web_completo` / `proyecto_completo` / `personalizado`), no rechazar el JSON entero — simplemente ignorar ese campo puntual (o cae en el default del form, que ya está resuelto por Zod al momento de validar el submit).
- Mismo criterio ya aplica implícitamente a `metadata`, `penalizaciones`, `condiciones_desaprobacion` (usan `|| []`/`|| {}`) — mantener la misma filosofía para los dos campos nuevos, no más estricta.

### 5. Actualizar el ejemplo de referencia

`JSON_EXAMPLE` en `frontend/src/features/rubricas/constants/rubrica-constants.ts` (el placeholder del textarea en Modo JSON) no menciona `modo_consolidacion`. Agregarlo como campo comentado/opcional en el ejemplo para que quien arma el JSON a mano sepa que existe el atajo:

```
"modo_consolidacion": "solo_codigo", // opcional — solo_codigo | web_completo | proyecto_completo | personalizado
"extensiones_personalizadas": null   // opcional — solo si modo_consolidacion es "personalizado", ej: [".ipynb", ".sql"]
```

---

## 🔧 Archivos a tocar (mapeados durante el análisis)

| Archivo | Cambio |
|---|---|
| `frontend/src/features/rubricas/utils/rubricaPortableJson.ts` | **Nuevo** — `buildRubricaPortableJSON()` compartida |
| `frontend/src/features/rubricas/pages/RubricasPage.tsx` | Nuevo ítem "Descargar JSON" en el `Dropdown` de acciones (gateado a coordinador/admin vía `useAuth()`); handler que llama `rubricasService.getById` + arma Blob |
| `frontend/src/features/rubricas/services/rubricas-service.ts` | Nuevo método `downloadJSON` (o el Blob se arma directo en el handler de la page, a definir) |
| `frontend/src/features/rubricas/components/RubricaEditor.tsx` | Botón "Descargar JSON" en modo edición; `currentJSON` (~línea 628) y `handleLoadJSON` (~línea 251) usan/leen `modo_consolidacion` + `extensiones_personalizadas` |
| `frontend/src/features/rubricas/components/RubricaJSONMode.tsx` | (Posible) agregar el botón de descarga real de archivo al lado de "Copiar JSON actual" |
| `frontend/src/features/rubricas/constants/rubrica-constants.ts` | `JSON_EXAMPLE` actualizado con `modo_consolidacion` / `extensiones_personalizadas` |

No hace falta tocar backend: `RubricaDetailResponse` (`backend/app/schemas/rubrica.py` ~línea 497) ya expone `modo_consolidacion` y `extensiones_personalizadas` — el dato ya viaja en `GET /rubricas/{id}`, solo falta que el frontend lo use.

---

## ❓ Decisiones abiertas para quien implemente

1. **¿El botón de descarga en el dropdown de la lista va gateado a coordinador/admin, o preferís mostrarlo siempre y dejar que el 403 lo frene?** Recomendación: gatear en el frontend (mejor UX, evita un toast de error confuso para un tutor) — mismo patrón que ya usa la página para materias/rol.
2. **Nombre del archivo descargado**: `Rubrica_{tipo}_{numero}_{titulo}.json` (propuesto, igual criterio que los PDF) — confirmar si el usuario prefiere otro formato.
3. **¿El botón "Descargar JSON" del modal reemplaza a "Copiar JSON actual" o convive con él?** Recomendación: convivir — copiar al portapapeles y descargar archivo son casos de uso distintos (pegar en otro lado vs. guardar/enviar el archivo).

---

## 🎓 Referencias

- Modo JSON actual: `frontend/src/features/rubricas/components/RubricaEditor.tsx`, `RubricaJSONMode.tsx`
- Modelo de rúbrica (fuente de verdad): `backend/app/schemas/rubrica.py`
- Dropdown de acciones de la lista: `frontend/src/features/rubricas/pages/RubricasPage.tsx`
- Servicio HTTP: `frontend/src/features/rubricas/services/rubricas-service.ts`
- Gotcha de permisos en `GET /rubricas/{id}` (coordinador/admin-only): `backend/app/routers/rubricas.py`

---

**Fin del documento**
