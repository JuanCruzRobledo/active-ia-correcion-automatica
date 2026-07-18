# 📋 Plan de Migración: Esquema de Rúbricas V2

> 📜 **HISTÓRICO / OBSOLETO — N8N fue removido.** Este documento pertenece a la etapa en que la corrección pasaba por N8N. Hoy la corrección/generación con IA es nativa en el backend (`backend/app/integrations/`: `ia_provider.py` → `gemini_correction_client.py` / `openrouter_client.py`, llamada HTTP directa). Se conserva solo como registro; NO refleja la arquitectura actual y sus pasos/pendientes de N8N ya no aplican.

**Proyecto:** Active-IA
**Fecha:** Febrero 2026

---

## 🎯 Contexto

Se modificó el esquema que debe tener la rúbrica (ver `docs/specs/Rubrica.md`) desde una estructura simple a una jerárquica con metadata flexible y reglas de evaluación más ricas.

**Motivo del cambio:**
- Evaluación más granular mediante checklist de evidencias (mejor para IA)
- Contexto flexible (metadata) para personalizar evaluaciones
- Reglas de negocio explícitas (penalizaciones, condiciones de desaprobación)

---

## 📊 Estado Actual vs Nuevo Esquema

### Estado Actual (V1)

```json
{
  "criterios": [
    {
      "nombre": "Funcionalidad correcta",
      "descripcion": "El programa realiza todas las operaciones solicitadas",
      "puntaje_maximo": 40
    },
    {
      "nombre": "Uso correcto de estructuras",
      "descripcion": "Implementa las estructuras de datos requeridas",
      "puntaje_maximo": 30
    }
  ]
}
```

### Nuevo Esquema (V2)

```json
{
  "titulo": "TP2 - API REST de Productos",
  "descripcion": "Desarrollo de una API REST con Express.js...",
  "puntaje_maximo": 100,

  "metadata": {
    // ⚠️ METADATA ES FLEXIBLE - puede tener cualquier campo
    // Los siguientes son campos comunes sugeridos:
    "materia": "Programación Backend",
    "carrera": "Tecnicatura en Programación",
    "lenguaje": "JavaScript",
    "framework": "Express.js"
    // ... cualquier otro campo
  },

  "criterios": [
    {
      "id": "C1",
      "nombre": "Estructura del proyecto",
      "descripcion": "Organización correcta de archivos...",
      "peso": 15,  // ⚠️ PESO en % (no puntaje_maximo absoluto)
      "instrucciones_puntuacion": "Dividir proporcionalmente...",
      "subcriterios": [
        {
          "id": "C1.1",
          "descripcion": "package.json con dependencias correctas",
          "evidencias": [
            "Archivo package.json existe",
            "Dependencia express presente"
          ]
        }
      ]
    }
  ],

  "penalizaciones": [
    {
      "id": "P1",
      "descripcion": "Repositorio privado o inaccesible",
      "descuento_porcentaje": 100
    }
  ],

  "condiciones_desaprobacion": [
    {
      "id": "CD1",
      "condicion": "Plagio detectado",
      "nota_final": 0
    }
  ]
}
```

**Diferencias clave:**
- ❌ **Eliminado:** Array simple de criterios con `puntaje_maximo`
- ✅ **Agregado:** `titulo`, `descripcion`, `metadata` (flexible), `penalizaciones`, `condiciones_desaprobacion`
- ✅ **Modificado:** Criterios ahora tienen `peso` (%), `subcriterios` con `evidencias`

---

## 📊 Resumen de Impacto

| Componente | Cambio | Complejidad |
|------------|--------|-------------|
| **Backend schemas** | Reescribir `CriteriosStructure` completo | 🟡 Media |
| **Backend validaciones** | Agregar validaciones: suma pesos=100, IDs únicos | 🟡 Media |
| **Frontend tipos** | Reescribir interfaces TypeScript | 🟡 Media |
| **RubricaEditor.tsx** | Reestructurar UI completa (accordion + 3 niveles anidados) | 🔴 Alta |
| **Validación Zod** | Crear schema V2 con validaciones custom | 🟡 Media |
| **Workflow N8N/Gemini** | Actualizar prompt para generar estructura V2 | 🟡 Media |
| **Tab "Desde JSON"** | Actualizar ejemplo y validación | 🟢 Baja |

---

## 🔧 Cambios Necesarios por Componente

### 1. Backend (`backend/app/schemas/rubrica.py`)

**Crear schemas nuevos:**

```python
class Subcriterio(BaseModel):
    id: str
    descripcion: str
    evidencias: list[str]

class Criterio(BaseModel):
    id: str
    nombre: str
    descripcion: str
    peso: int  # % (no puntaje_maximo)
    instrucciones_puntuacion: str | None = None
    subcriterios: list[Subcriterio]

class Penalizacion(BaseModel):
    id: str
    descripcion: str
    descuento_porcentaje: int  # 0-100

class CondicionDesaprobacion(BaseModel):
    id: str
    condicion: str
    nota_final: int  # 0-100

class CriteriosStructure(BaseModel):
    titulo: str
    descripcion: str
    puntaje_maximo: int = 100
    metadata: dict[str, Any]  # ⚠️ FLEXIBLE, sin estructura fija
    criterios: list[Criterio]
    penalizaciones: list[Penalizacion]
    condiciones_desaprobacion: list[CondicionDesaprobacion]

    @field_validator("criterios")
    def validate_suma_pesos(cls, v):
        total = sum(c.peso for c in v)
        if total != 100:
            raise ValueError(f"Suma de pesos debe ser 100, es {total}")
        return v

    # Validar IDs únicos, descuentos 0-100, evidencias no vacío, etc.
```

---

### 2. Frontend Tipos (`frontend/src/features/rubricas/types/`)

**Interfaces nuevas:**

```typescript
interface Subcriterio {
  id: string;
  descripcion: string;
  evidencias: string[];
}

interface Criterio {
  id: string;
  nombre: string;
  descripcion: string;
  peso: number;  // % (no puntaje)
  instrucciones_puntuacion?: string;
  subcriterios: Subcriterio[];
}

interface Penalizacion {
  id: string;
  descripcion: string;
  descuento_porcentaje: number;
}

interface CondicionDesaprobacion {
  id: string;
  condicion: string;
  nota_final: number;
}

interface CriteriosStructure {
  titulo: string;
  descripcion: string;
  puntaje_maximo: 100;
  metadata: Record<string, any>;  // ⚠️ FLEXIBLE
  criterios: Criterio[];
  penalizaciones: Penalizacion[];
  condiciones_desaprobacion: CondicionDesaprobacion[];
}
```

**Schema Zod con validaciones:**
- Suma de pesos = 100
- IDs únicos
- Descuentos 0-100
- Evidencias no vacío

---

### 3. RubricaEditor.tsx

**Cambio estructural:**
De formulario plano → **Accordion con 5 secciones**

**Secciones:**
1. **Información General:** titulo, descripcion, tipo, numero, año
2. **Metadata (flexible):** Componente `KeyValueInput` para agregar/quitar campos dinámicamente
3. **Criterios (3 niveles):**
   - Array de criterios
   - Cada criterio tiene array de subcriterios
   - Cada subcriterio tiene `TagInput` para evidencias
   - Mostrar suma de pesos en tiempo real
4. **Penalizaciones:** Array simple con id, descripcion, descuento_porcentaje
5. **Condiciones:** Array simple con id, condicion, nota_final

**Componentes necesarios:**
- `TagInput`: Input con chips (para evidencias)
- `KeyValueInput`: Objeto dinámico (para metadata)
- Validación en tiempo real de suma pesos

---

### 4. Workflow N8N - Generación desde PDF

**Actualizar prompt de Gemini:**

Cambiar prompt para generar estructura V2 completa:
- Extraer `titulo` y `descripcion` del PDF
- Inferir `metadata` (lenguaje, framework, formato_entrega del PDF)
- Generar criterios con **subcriterios** y **evidencias verificables**
- Asignar pesos % (suma = 100)
- Extraer/generar penalizaciones si se mencionan
- Generar condiciones de desaprobación estándar

**Validación post-generación:**
- Verificar suma pesos = 100
- Si falla, reintentar con corrección

---

### 5. Tab "Desde JSON"

**Actualizar:**
- Placeholder con ejemplo V2
- Validación Zod antes de importar
- Link a `docs/specs/Rubrica.md` para referencia

---

## ⚠️ Puntos Críticos

1. **Metadata es FLEXIBLE**: No tiene estructura fija, es `Record<string, any>` o `dict[str, Any]`
2. **Cambio de puntaje absoluto a peso %**: `puntaje_maximo` → `peso`
3. **Jerarquía de 3 niveles**: Criterio → Subcriterio → Evidencias
4. **Suma de pesos = 100**: Validación crítica en backend y frontend
5. **IDs únicos**: Validar en criterios, subcriterios, penalizaciones, condiciones

---

## 🎓 Referencias

- **Especificación completa:** `docs/specs/Rubrica.md`
- **Código actual:**
  - Backend: `backend/app/schemas/rubrica.py`
  - Frontend: `frontend/src/features/rubricas/`

---

## 📌 Próximos Pasos

1. Leer este plan para entender el contexto
2. Analizar el código actual del proyecto
3. Implementar cambios fase por fase, **consultando antes de avanzar**

---

**Fin del documento**
