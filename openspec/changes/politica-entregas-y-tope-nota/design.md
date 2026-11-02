# Design

## Context

Ver `proposal.md` para el problema. La consolidación actual filtra por directorio/extensión y ordena por ruta; `dist` pasa el filtro. El payload de corrección conserva sólo un prefijo de 200.000 caracteres por defecto. Moodle importa con el modo de la rúbrica y la reimportación actual es idempotente. Las pruebas deben aislar toda base de datos y servicio externo; los entornos locales pueden apuntar a producción.

## Goals / Non-Goals

**Goals:** clasificar antes de filtrar, preservar evidencia por versión, aplicar el máximo después de recibir la evaluación y evitar correcciones incompletas. Mantener permisos existentes, Clean Architecture y compatibilidad con entregas históricas.

**Non-Goals:** evaluar dependencias o código generado, modificar automáticamente notas anteriores, desplegar, aplicar migraciones a producción, cambiar proveedor/modelo de IA o rediseñar el producto.

## Decisions

1. **Clasificador puro y política explícita.** Usar segmentos completos de ruta normalizados, con comparación sin diferencias de mayúsculas, para detectar `node_modules`, `dist`, `target`, `build`, `out` y `bin`. Carpetas vacías no demuestran contenido no evaluable y no activan el tope por sí solas. Permitir excepciones expresas por rúbrica; no inferirlas de un nombre parecido o de cualquier extensión admitida. Separar la evidencia penalizable del contenido leído, para no descomprimir dependencias ignoradas. Alternativa descartada: filtrar primero y perder evidencia.
2. **Residuos sin castigo.** Ignorar cachés Python, metadatos de sistema, Git y editores, y lockfiles por nombre exacto, sin activar el tope. Mantener archivos de código/configuración relevantes, incluyendo `.properties`. No incorporar archivos desconocidos o secretos indiscriminadamente. Alternativa descartada: penalizar todo archivo excluido.
3. **Persistencia por versión.** Guardar el análisis con versión de política, entradas incluidas/ignoradas, motivos y rutas penalizables. Una entrega histórica sin análisis conserva su comportamiento anterior hasta que se aporte y analice su archivo. Preservar los datos anteriores al sustituir una entrega/corrección. La reentrega limpia elimina la restricción vigente y requiere una nueva evaluación.
4. **Tope central posterior a evaluación.** Guardar por separado nota académica y final. Para una infracción activa, aplicar `min(nota_academica, 50)` en corrección automática, carga externa y edición manual. La devolución identifica causa y forma de subsanar; los criterios académicos no se alteran artificialmente. Alternativa descartada: pedir a la IA que recuerde aplicar el máximo.
5. **Integridad antes del proveedor.** Tras filtrar, si el consolidado supera el límite configurable, bloquear la corrección con mensaje accionable y sin consumir el proveedor ni guardar una nota definitiva. Mantener el contenido completo almacenado para diagnóstico. Alternativa descartada: aumentar únicamente el límite o mover `src` al principio y seguir cortando.
6. **Moodle versionado e idempotente.** Actualizar sólo una versión nueva del adjunto/submission; un reintento idéntico no reemplaza correcciones ni crea historia redundante. El cambio de contenido limpio debe pasar por el mismo analizador que la carga manual y masiva.

## Risks / Trade-offs

- Nombres genéricos legítimos (`build`, `bin`) → excepciones explícitas por rúbrica y pruebas de coincidencias completas.
- Proyectos válidos todavía grandes → mensaje de bloqueo y revisión del tutor; evaluación por bloques queda fuera de este cambio.
- Entregas pasadas sin ZIP → no inventar evidencia ni aplicar sanciones retroactivas; reconsolidar sólo al aportar el archivo.
- Modelo de datos compartido con producción → migración aditiva revisable y pruebas locales sin conexión a producción.
- UI con política visual `off` → conservar el estilo existente y verificar los cambios implementados sin sistema visual ni mockups por cambio.

## Migration Plan

Migración aditiva preparada: `b219adce5108`, padre `f8b4d2e6c901`, único head Alembic. Validada el 2026-11-02 mediante SQL PostgreSQL offline (dos JSONB nullable y downgrade) y SQLite en memoria (filas históricas conservadas, JSON de ida/vuelta y downgrade), sin cargar `.env` ni conectar a una base real. Los valores nulos significan entrega/corrección histórica sin análisis de esta política; no hay backfill de sanciones. Validar fuera de producción. El despliegue y la ejecución en producción no forman parte de esta tarea.

## UI Mockups

- Design system revision: no aplica (Mode: off).
- Decision: no (project policy), 2026-10-30.
- Approval: skipped.
- Preview: no aplica (sin mockups por política del proyecto).
- Visual verify: passed (2026-10-30), detalle de entrega, detalle de corrección y editor de rúbrica a 390x844 y 1440x900; capturas en `verification/` y alcance en `verification/README.md`.

El usuario eligió explícitamente: "Sin sistema visual ni mockups; conservar el estilo actual". La política del proyecto está registrada en `design-system/README.md` con `Mode: off` y `Approval: skipped`. No se crean mockups; esta decisión no equivale a verificar la interfaz implementada.
