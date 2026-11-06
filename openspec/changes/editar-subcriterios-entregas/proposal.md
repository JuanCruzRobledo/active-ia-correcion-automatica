# Proposal

## Why

El tutor puede corregir el puntaje y el comentario de un criterio, pero el desglose por subcriterios queda solo de lectura en el modal de corrección de Entregas. Esto impide ajustar una evaluación de IA en el mismo nivel de detalle con que fue producida y devuelta al alumno.

## What Changes

- Permitir editar `puntaje_obtenido` y `feedback` de los subcriterios evaluados existentes desde el modo edición de la corrección de una entrega.
- Mantener los subcriterios solo de lectura en modo consulta y restaurar sus valores al cancelar.
- Derivar el puntaje del criterio de la suma de sus subcriterios cuando haya desglose, conservando el comentario del criterio como edición independiente.
- Validar puntajes finitos dentro del máximo y comentarios no vacíos en frontend y en la edición manual del backend; conservar identificadores, máximos y estados.
- Guardar mediante el contrato actual de edición de correcciones, conservar el marcado de edición manual y mostrar los cambios al volver a consultar y en la devolución PDF.
- Preservar correcciones sin desglose y el comportamiento explícito de Recalcular nota, edición de nota académica y aplicación posterior del tope por entrega.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `correccion-desglose-subcriterio`: agregar edición manual del puntaje y comentario del desglose, con validación, coherencia del criterio y compatibilidad con correcciones sin subcriterios.

## Impact

- Frontend: `CorreccionViewEditModal.tsx`, componentes de criterio/subcriterio extraídos, utilidades o hook de edición y pruebas Vitest/Testing Library en `features/correcciones/`.
- Backend: edición manual de `CorreccionService`, validación específica de actualización y pruebas pytest; reutilizar `PUT /correcciones/{id}`, schemas y JSONB existentes. Sin migración de base de datos ni nuevo endpoint.
- Reutilizar permisos por pertenencia y universidad, política de nota vigente y PDF que ya consume `subcriterios_evaluados`; no cambiar autenticación, permisos ni formato de respuesta de IA.
- No se edita la definición de la rúbrica, no se crean/eliminan subcriterios y no se agregan controles para cambiar su estado.
- Gobernanza MEDIUM (lógica de evaluación); este change entrega planificación y exige una solicitud posterior para implementar con TDD estricto.
