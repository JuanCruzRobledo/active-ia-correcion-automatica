# 📘 Documentación del modelo de rúbricas para evaluación automática con IA

---

## 🎯 Propósito

Este esquema define la estructura de una **rúbrica de evaluación** que permite a la IA corregir trabajos prácticos, parciales y finales de forma consistente y profesional.

---

## 🆕 Versionado del esquema (`schema_version`)

Toda rúbrica tiene una columna `schema_version` (entero, `NOT NULL`, default `1`) que versiona el contrato de su estructura JSONB:

| `schema_version` | Comportamiento |
| ----------------- | -------------- |
| `1` (default)      | Comportamiento histórico: los subcriterios son un checklist de evidencias, **sin peso propio** — el reparto de puntaje dentro del criterio queda implícito. |
| `2`                | Los subcriterios tienen **peso propio en puntos absolutos** que deben sumar exactamente el `peso` del criterio contenedor. La IA devuelve y persiste el puntaje desglosado por subcriterio. |

- Las rúbricas existentes quedan en `schema_version = 1` sin backfill manual; siguen siendo válidas, editables y corregibles exactamente igual que antes.
- No hay migración automática v1 → v2: el docente decide migrar una rúbrica puntual desde el editor (ver "Migrar al nuevo modelo" más abajo). Mientras no lo haga, la rúbrica sigue viendo/corrigiendo en v1.
- El campo se expone en las respuestas de detalle y de listado de rúbricas para que el frontend pueda mostrar el indicador de "rúbrica desactualizada" cuando corresponda.

---

## 📐 Estructura del Esquema

```jsonc
{
  // ──────────────────────────────────────────────────────────
  // INFORMACIÓN GENERAL
  // ──────────────────────────────────────────────────────────
  "titulo": "string", // Nombre descriptivo del TP/examen
  "descripcion": "string", // Resumen de qué evalúa esta rúbrica
  "puntaje_maximo": 100, // Siempre 100 (fijo)

  // ──────────────────────────────────────────────────────────
  // METADATA (contexto del trabajo). Es completamente flexible, puede tener o no cualquiera de estos campos o alguno nuevo
  // ──────────────────────────────────────────────────────────
  "metadata": {
    "materia": "string", // Ej: "Programación III"
    "carrera": "string", // Ej: "Tecnicatura en Programación"
    "modalidad": "string", // Ej: "A distancia", "Presencial"
    "lenguaje": "string | string[]", // Ej: "Java" o ["Python", "SQL"]
    "framework": "string", // Ej: "Spring Boot", "React"
    "version": "string", // Ej: "Java 17+", "Node 18+"
    "formato_entrega": {
      "tipo": "string", // Ej: "Repositorio GitHub", "Archivo ZIP"
      "extensiones_aceptadas": ["string"],
      "archivo_unico": "boolean | null",
      "publico": "boolean | null",
      "restricciones": ["string"],
    },
    // Mas o menos campos segun sea NECESARIO
  },

  // ──────────────────────────────────────────────────────────
  // CRITERIOS DE EVALUACIÓN (suma peso = 100)
  // ──────────────────────────────────────────────────────────
  "criterios": [
    {
      "id": "string",
      "nombre": "string",
      "descripcion": "string",
      "peso": "number",

      "instrucciones_puntuacion": "string | null",

      "subcriterios": [
        {
          "id": "string",
          "descripcion": "string",
          "evidencias": ["string"],
          "peso": "number | null", // Solo en schema_version = 2 (obligatorio ahí); ausente/null en v1. sum(subcriterios[].peso) == criterios[].peso
        },
      ],
    },
  ],

  // ──────────────────────────────────────────────────────────
  // PENALIZACIONES
  // ──────────────────────────────────────────────────────────
  "penalizaciones": [
    {
      "id": "string",
      "descripcion": "string",
      "descuento_porcentaje": "number",
    },
  ],

  // ──────────────────────────────────────────────────────────
  // CONDICIONES DE DESAPROBACIÓN
  // ──────────────────────────────────────────────────────────
  "condiciones_desaprobacion": [
    {
      "id": "string",
      "condicion": "string",
      "nota_final": "number",
    },
  ],
}
```

---

## 📝 Ejemplo Práctico

### Trabajo Práctico: API REST en Node.js

```json
{
  "titulo": "TP2 - API REST de Productos",
  "descripcion": "Desarrollo de una API REST con Express.js que implemente CRUD completo de productos con validaciones y manejo de errores.",
  "puntaje_maximo": 100,

  "metadata": {
    "materia": "Programación Backend",
    "carrera": "Tecnicatura en Programación",
    "modalidad": "Virtual",
    "lenguaje": "JavaScript",
    "framework": "Express.js",
    "version": "Node 18+",
    "formato_entrega": {
      "tipo": "Repositorio GitHub",
      "extensiones_aceptadas": [".js", ".json"],
      "archivo_unico": false,
      "publico": true,
      "restricciones": [
        "Incluir package.json",
        "Incluir README con instrucciones",
        "Estructura: src/routes, src/controllers, src/models"
      ]
    }
  },

  "criterios": [
    {
      "id": "C1",
      "nombre": "Estructura del proyecto",
      "descripcion": "Organización correcta de archivos y configuración inicial.",
      "peso": 15,
      "instrucciones_puntuacion": "Dividir proporcionalmente. Cada subcriterio vale aproximadamente 5 puntos.",
      "subcriterios": [
        {
          "id": "C1.1",
          "descripcion": "package.json con dependencias correctas (express, cors, dotenv).",
          "evidencias": [
            "Archivo package.json existe",
            "Dependencia express presente",
            "Dependencia cors presente",
            "Scripts de inicio configurados"
          ]
        },
        {
          "id": "C1.2",
          "descripcion": "Estructura de carpetas profesional (src/routes, src/controllers, src/models).",
          "evidencias": [
            "Carpeta src/ existe",
            "Subcarpetas routes/, controllers/, models/ presentes",
            "Archivos organizados correctamente"
          ]
        },
        {
          "id": "C1.3",
          "descripcion": "Servidor Express configurado y ejecutable.",
          "evidencias": [
            "Archivo server.js o app.js presente",
            "Express inicializado correctamente",
            "Puerto configurable por variable de entorno",
            "Servidor inicia sin errores"
          ]
        }
      ]
    },
    {
      "id": "C2",
      "nombre": "Endpoints CRUD",
      "descripcion": "Implementación completa de Create, Read, Update y Delete.",
      "peso": 40,
      "instrucciones_puntuacion": "Cada operación vale 10 puntos. Descontar si faltan validaciones o manejo de errores.",
      "subcriterios": [
        {
          "id": "C2.1",
          "descripcion": "POST /productos - Crear producto",
          "evidencias": [
            "Endpoint POST /productos existe",
            "Valida campos requeridos",
            "Genera ID automático",
            "Retorna código 201"
          ]
        },
        {
          "id": "C2.2",
          "descripcion": "GET /productos - Listar todos",
          "evidencias": [
            "Endpoint GET /productos existe",
            "Retorna array de productos",
            "Código 200 en respuesta exitosa"
          ]
        },
        {
          "id": "C2.3",
          "descripcion": "GET /productos/:id - Obtener uno",
          "evidencias": [
            "Endpoint GET /productos/:id existe",
            "Busca producto por ID",
            "Retorna 404 si no existe",
            "Retorna 200 si existe"
          ]
        },
        {
          "id": "C2.4",
          "descripcion": "PUT /productos/:id - Actualizar",
          "evidencias": [
            "Endpoint PUT /productos/:id existe",
            "Actualiza campos del producto",
            "Retorna 404 si no existe",
            "Retorna 200 con producto actualizado"
          ]
        },
        {
          "id": "C2.5",
          "descripcion": "DELETE /productos/:id - Eliminar",
          "evidencias": [
            "Endpoint DELETE /productos/:id existe",
            "Elimina producto correctamente",
            "Retorna 404 si no existe",
            "Retorna 200 o 204 al eliminar"
          ]
        }
      ]
    },
    {
      "id": "C3",
      "nombre": "Validaciones y manejo de errores",
      "descripcion": "Validación de datos y respuestas adecuadas ante errores.",
      "peso": 25,
      "instrucciones_puntuacion": "C3.1 vale 10 pts, C3.2 vale 10 pts, C3.3 vale 5 pts.",
      "subcriterios": [
        {
          "id": "C3.1",
          "descripcion": "Validaciones de campos y tipos de datos.",
          "evidencias": [
            "Nombre no vacío",
            "Precio positivo",
            "Stock entero mayor o igual a 0",
            "Retorna 400 con mensaje claro"
          ]
        },
        {
          "id": "C3.2",
          "descripcion": "Errores 404 correctamente manejados.",
          "evidencias": [
            "Retorna 404 cuando no existe",
            "Mensaje 'Producto no encontrado'",
            "Formato consistente"
          ]
        },
        {
          "id": "C3.3",
          "descripcion": "Middleware global de errores.",
          "evidencias": [
            "Middleware configurado",
            "Captura errores inesperados",
            "Retorna 500 genérico"
          ]
        }
      ]
    },
    {
      "id": "C4",
      "nombre": "Documentación y entrega",
      "descripcion": "Repositorio accesible y bien documentado.",
      "peso": 20,
      "instrucciones_puntuacion": "Cada subcriterio vale 10 puntos.",
      "subcriterios": [
        {
          "id": "C4.1",
          "descripcion": "README.md completo.",
          "evidencias": [
            "README.md existe",
            "Describe el proyecto",
            "Incluye instalación y ejecución",
            "Documenta endpoints"
          ]
        },
        {
          "id": "C4.2",
          "descripcion": "Repositorio público y código limpio.",
          "evidencias": [
            "Repositorio público",
            "Indentación correcta",
            "Nombres descriptivos",
            "No incluye node_modules/"
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
    },
    {
      "id": "P2",
      "descripcion": "Código no ejecuta o tiene errores fatales",
      "descuento_porcentaje": 50
    },
    {
      "id": "P3",
      "descripcion": "Falta README.md",
      "descuento_porcentaje": 20
    }
  ],

  "condiciones_desaprobacion": [
    {
      "id": "CD1",
      "condicion": "Plagio detectado",
      "nota_final": 0
    },
    {
      "id": "CD2",
      "condicion": "No implementa al menos 3 endpoints CRUD",
      "nota_final": 30
    }
  ]
}
```

---

## 🆕 Ejemplo de criterio con peso por subcriterio (`schema_version = 2`)

```json
{
  "id": "C2",
  "nombre": "Endpoints CRUD",
  "descripcion": "Implementación completa de Create, Read, Update y Delete.",
  "peso": 40,
  "subcriterios": [
    { "id": "C2.1", "descripcion": "POST /productos", "evidencias": ["..."], "peso": 10 },
    { "id": "C2.2", "descripcion": "GET /productos", "evidencias": ["..."], "peso": 10 },
    { "id": "C2.3", "descripcion": "GET /productos/:id", "evidencias": ["..."], "peso": 8 },
    { "id": "C2.4", "descripcion": "PUT /productos/:id", "evidencias": ["..."], "peso": 8 },
    { "id": "C2.5", "descripcion": "DELETE /productos/:id", "evidencias": ["..."], "peso": 4 }
  ]
}
```

`10 + 10 + 8 + 8 + 4 = 40 = peso del criterio C2`. Si la suma no cierra, la rúbrica se rechaza con un error que indica el criterio y la discrepancia.

### Migración v1 → v2 (reparto de pesos iguales)

Al migrar un criterio existente al nuevo modelo, el frontend pre-carga un reparto **igual** entre sus subcriterios usando el método del resto mayor (Hamilton), que garantiza que la suma cierre exacto con enteros:

```
base  = floor(peso_criterio / n)
resto = peso_criterio - base * n        // 0 <= resto < n
// los primeros `resto` subcriterios reciben base + 1; el resto, base
```

Ejemplo: criterio de peso 25 con 3 subcriterios → `base = 8`, `resto = 1` → pesos precargados `[9, 8, 8]` (suma 25). El reparto es un punto de partida **editable**: el docente puede reasignar los pesos a mano siempre que la suma final siga cerrando contra el peso del criterio.

Caso borde: si el criterio tiene más subcriterios que puntos (`peso_criterio < n`), no todos pueden recibir al menos 1 punto — el pre-cargado deja algunos en 0 y la validación exige ajustar antes de guardar. No es un error silencioso: guía al docente a repartir manualmente.

---

## 🚀 Guía de Uso

### 1️⃣ Creación Manual

En el editor web, completá:

- Información general (título y descripción)
- Metadata (opcional, pero recomendado)
- Criterios con sus pesos (la suma debe ser 100)
- Subcriterios con evidencias (checklist para la IA)

---

### 2️⃣ Desde JSON

Pegá o importá un JSON que siga este esquema.  
La validación automática verificará:

- Suma de pesos = 100
- IDs únicos
- Estructura correcta

---

### 3️⃣ Desde PDF

La IA extrae automáticamente del PDF de la consigna:

- Título y descripción
- Metadata (lenguaje, formato, modalidad, etc.)
- Criterios y subcriterios
- Penalizaciones y condiciones de desaprobación

---

## ✅ Reglas de Validación

| Campo                                    | Validación                 |
| ---------------------------------------- | -------------------------- |
| `puntaje_maximo`                         | Siempre 100                |
| `criterios[].peso`                       | La suma total debe ser 100 |
| `criterios[].id`                         | Únicos (C1, C2, ..., Cn)   |
| `subcriterios[].id`                      | Únicos dentro del criterio |
| `subcriterios[].evidencias`              | Array no vacío             |
| `subcriterios[].peso` (solo `schema_version = 2`) | Entre 1 y 100; obligatorio en todos los subcriterios del criterio; `sum(subcriterios[].peso) == criterios[].peso` |
| `penalizaciones[].descuento_porcentaje`  | Entre 0 y 100              |
| `condiciones_desaprobacion[].nota_final` | Entre 0 y 100              |

En rúbricas `schema_version = 1` no se exige `peso` en los subcriterios (compatibilidad total con el comportamiento previo).

---

## 💡 Buenas Prácticas

### Para los Criterios

- **Peso**: asignar según importancia  
  (la funcionalidad suele representar entre 30% y 40%)
- **Nombre**: claro y conciso  
  (ej. _Estructura del proyecto_, _Validaciones_)
- **Descripción**: explicar qué aspecto se evalúa

---

### Para los Subcriterios

- **Específicos**: un subcriterio = un aspecto verificable
- **Evidencias**: lista de checks que la IA debe validar
- **Granularidad**: lo ideal es entre 3 y 6 subcriterios por criterio

---

### Para las Evidencias

**✅ Buenas evidencias (verificables):**

- "Archivo package.json existe"
- "Endpoint POST /productos retorna código 201"
- "Valida que precio sea número positivo"

**❌ Malas evidencias (ambiguas):**

- "Código de calidad"
- "Funciona bien"
- "Buen diseño"

---

## 🎓 Casos de Uso

### TP de Programación

```json
{
  "criterios": [
    { "id": "C1", "nombre": "Funcionalidad", "peso": 40 },
    { "id": "C2", "nombre": "Calidad de código", "peso": 30 },
    { "id": "C3", "nombre": "Documentación", "peso": 20 },
    { "id": "C4", "nombre": "Entrega", "peso": 10 }
  ]
}
```

### Parcial Teorico

```json
{
  "criterios": [
    { "id": "C1", "nombre": "Conceptos teóricos", "peso": 50 },
    { "id": "C2", "nombre": "Aplicación práctica", "peso": 30 },
    { "id": "C3", "nombre": "Justificación", "peso": 20 }
  ]
}
```

### Proyecto Final

```json
{
  "criterios": [
    { "id": "C1", "nombre": "Arquitectura", "peso": 25 },
    { "id": "C2", "nombre": "Implementación", "peso": 35 },
    { "id": "C3", "nombre": "Testing", "peso": 15 },
    { "id": "C4", "nombre": "Documentación", "peso": 15 },
    { "id": "C5", "nombre": "Presentación", "peso": 10 }
  ]
}
```

---

## 🔗 Integración con IA

La IA utiliza este esquema para:

1. Analizar el trabajo del alumno
2. Verificar cada evidencia en los subcriterios
3. Asignar puntaje por criterio según cumplimiento
4. Aplicar penalizaciones si corresponde
5. Verificar condiciones de desaprobación
6. Generar feedback detallado por criterio

**Resultado:** corrección objetiva, consistente y trazable.

### 🆕 Desglose por subcriterio en la corrección (`schema_version = 2`)

Al corregir una entrega de una rúbrica `schema_version = 2` (con Gemini o con OpenRouter — ambos proveedores comparten el mismo constructor de prompt), la IA:

- Recibe cada subcriterio con su identificador y su peso en puntos, ej. `[C2.1] (10 pts) POST /productos - Crear producto`, además de sus evidencias.
- Asigna puntaje **por subcriterio**, y el `puntaje_obtenido` del criterio es la suma de sus subcriterios.
- Devuelve, dentro de cada criterio evaluado, un arreglo `subcriterios_evaluados` con `id`, `puntaje_obtenido`, `puntaje_maximo`, `estado` (`OK`/`WARNING`/`ERROR`) y `feedback`.

```json
{
  "criterios": [
    {
      "id": "C2",
      "nombre": "Endpoints CRUD",
      "puntaje_obtenido": 36,
      "puntaje_maximo": 40,
      "estado": "OK",
      "feedback": "Todos los endpoints implementados correctamente.",
      "subcriterios_evaluados": [
        { "id": "C2.1", "puntaje_obtenido": 10, "puntaje_maximo": 10, "estado": "OK", "feedback": "..." },
        { "id": "C2.2", "puntaje_obtenido": 10, "puntaje_maximo": 10, "estado": "OK", "feedback": "..." },
        { "id": "C2.3", "puntaje_obtenido": 8, "puntaje_maximo": 8, "estado": "OK", "feedback": "..." },
        { "id": "C2.4", "puntaje_obtenido": 8, "puntaje_maximo": 8, "estado": "OK", "feedback": "..." },
        { "id": "C2.5", "puntaje_obtenido": 0, "puntaje_maximo": 4, "estado": "ERROR", "feedback": "No implementa DELETE." }
      ]
    }
  ]
}
```

- `subcriterios_evaluados` se persiste dentro de cada criterio en la columna JSONB `criterios_json` de la corrección — **sin migración de tabla**.
- La nota final **no cambia** por el desglose: sigue calculándose como la suma de `puntaje_obtenido` de los criterios; los subcriterios solo desglosan, no alteran el cálculo.
- Rúbricas `schema_version = 1`, o cualquier respuesta que omita el campo, siguen parseando y mostrándose exactamente igual que antes — `subcriterios_evaluados` es opcional en todo el pipeline (schema de IA, persistencia y frontend) y su ausencia nunca es un error.

---

## 📌 Resumen Rápido

- **Rúbrica** = Título + Metadata + Criterios + Penalizaciones + Condiciones + `schema_version`
- **Criterio** = Nombre + Peso + Subcriterios
- **Subcriterio** = Descripción + Evidencias (checklist para la IA) + Peso opcional (`schema_version = 2`)

✅ Suma de pesos de criterios = 100  
✅ En `schema_version = 2`: suma de pesos de subcriterios = peso del criterio  
✅ Evidencias claras y verificables  
✅ Instrucciones de puntuación opcionales pero recomendadas  
✅ Rúbricas `schema_version = 1` siguen funcionando exactamente igual que antes

---

**Versión:** 2.0  
**Última actualización:** Julio 2026 — peso por subcriterio y `schema_version` (ver `openspec/changes/archive/*-peso-por-subcriterio/`)  
**Proyecto:** Active-IA
