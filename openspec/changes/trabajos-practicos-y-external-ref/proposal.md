## Why

AI-Native (`tutor.active-ia.com`) quiere que el docente corrija con Active-IA un TP compuesto por N ejercicios, **ejercicio por ejercicio**. Hoy no se puede, por dos razones verificadas contra la API en vivo el 2026-08-17:

**1. No existe el nivel de ejercicio.** En Active-IA la unidad de corrección es la `Rubrica`: una entrega se corrige contra una rúbrica y produce una corrección. Un TP de cuatro ejercicios tendría que compartir una sola rúbrica, o inventar cuatro unidades artificiales que no representan nada real.

Y no es una molestia de modelado: juntar los cuatro ejercicios en un solo envío **activa un modo de fallo ya medido en el motor** — distingue presencia, no vínculo (bug 4). Con cuatro ejercicios en el mismo archivo consolidado, una pieza del ejercicio 3 puede contar como cumplimiento de un criterio del ejercicio 1. Corrigiendo de a uno, eso desaparece por construcción.

**2. El cruce depende de `cmid`, y AI-Native no es Moodle.** El vínculo entre una actividad externa y una rúbrica vive en una sola columna, `rubricas.moodle_assign_id` (`app/models/rubrica.py:116`), que es el `cmid` de Moodle. AI-Native no tiene `cmid` en ninguna parte de su monorepo. Hoy eso deja el 100% del mapeo en un archivo manual del tutor (`~/.moodle-skill/activeia_rubricas.json`), que no escala cuando los ejercicios los crea el docente desde la plataforma y pueden ser decenas.

Ninguno de los dos problemas se resuelve con un endpoint. Son el modelo de datos, y por eso este change va primero: es el prerrequisito de todo lo demás de la integración.

## What Changes

- **Nueva entidad `TrabajoPractico`**: agrupa N ejercicios bajo una materia. Es lo que AI-Native llama "TP" y lo que en Moodle sería una unidad.
- **Nueva entidad `Ejercicio`**: pertenece a un TP, tiene `orden`, `titulo`, `enunciado_md`, `peso` relativo dentro del TP, y sus `test_cases`.
- **Un ejercicio es dueño de exactamente una `Rubrica`.** No se crea un modelo de rúbrica paralelo: la `Rubrica` existente ya tiene criterios jerárquicos, subcriterios con peso, penalizaciones y condiciones de desaprobación. El motor de corrección, el PDF, el historial y el frontend de correcciones **no se tocan**.
- **`external_ref` en `Materia`, `TrabajoPractico` y `Ejercicio`**: identificador externo propio del cliente, único por materia (por universidad en el caso de `Materia`). Toda la integración cruza por ahí. `cmid` sigue funcionando para el flujo de Moodle, sin cambios.
- **El `UniqueConstraint` de rúbricas pasa a ser un índice parcial.** `uq_rubrica_materia_tipo_numero_anio` hoy impide que cuatro ejercicios del mismo TP tengan cuatro rúbricas (mismo `materia_id`, `tipo`, `numero`, `anio`). Pasa a aplicar solo a las rúbricas que **no** pertenecen a un ejercicio, replicando el patrón de índice parcial ya usado en `uq_entrega_rubrica_alumno`.
- **`test_cases` como parte del enunciado, no como algo a ejecutar.** Active-IA **no** ejecuta código. Los casos viajan porque le dicen al motor cuál es la regla de negocio que se pidió. Los casos ocultos (`es_publico: false`) SHALL almacenarse **sin** salida esperada ni aserción: lo que el motor nunca recibe no lo puede citar en una devolución que el alumno lee.
- **Resolución por `external_ref`** en el repositorio, para que los endpoints del change siguiente crucen por ahí sin duplicar lógica.

## Capabilities

### New Capabilities

- `trabajo-practico-ejercicio`: entidades `TrabajoPractico` y `Ejercicio`, con la relación 1:1 entre ejercicio y rúbrica, el peso relativo, el enunciado y el orden dentro del TP.
- `external-ref-identificacion`: identificador externo opcional y único por materia en `Materia`, `TrabajoPractico` y `Ejercicio`, con resolución por ese identificador y convivencia con `cmid`.
- `ejercicio-test-cases`: almacenamiento de los casos de prueba como parte del enunciado, con la regla de que los casos ocultos no conservan salida esperada ni aserción.

### Modified Capabilities

- `rubrica-peso-subcriterio`: la unicidad de `(materia, tipo, numero, anio)` pasa a ser parcial, aplicable solo a rúbricas no pertenecientes a un ejercicio.
- `aislamiento-datos-por-universidad`: las dos entidades nuevas se incorporan al scoping multi-tenant con `universidad_id` denormalizado.
- `autorizacion-por-pertenencia`: verificación de acceso a un TP y a un ejercicio por la materia que los contiene.

## Impact

**Backend**
- `app/models/trabajo_practico.py` — nuevo.
- `app/models/ejercicio.py` — nuevo.
- `app/models/materia.py` — columna `external_ref`.
- `app/models/rubrica.py` — columna `ejercicio_id` (nullable, única) y el `UniqueConstraint` convertido en índice parcial.
- `app/schemas/trabajo_practico.py`, `app/schemas/ejercicio.py` — nuevos, con validación de `test_cases` y de la suma de pesos.
- `app/repositories/trabajo_practico_repository.py`, `app/repositories/ejercicio_repository.py` — nuevos, con búsqueda por `external_ref`.
- `app/services/trabajo_practico_service.py` — nuevo.
- `app/core/permissions.py` — `verificar_acceso_trabajo_practico` y `verificar_acceso_ejercicio`.
- `alembic/versions/` — migración: dos tablas nuevas, tres columnas `external_ref`, `rubricas.ejercicio_id`, y el reemplazo del constraint por el índice parcial.

**Sin cambios en**: el motor de corrección, `pdf_service`, el historial de correcciones, el flujo de Moodle, el frontend de correcciones.

**No incluye**: los endpoints públicos de escritura (change `api-escritura-trabajos-practicos`) ni la corrección por ejercicio (change `correccion-por-ejercicio-con-tests`).
