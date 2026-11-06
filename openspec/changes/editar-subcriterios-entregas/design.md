# Design

## Context

Ver `proposal.md` para la motivación. Hallazgos comprobados:

- `EntregasPage.tsx` abre `CorreccionViewEditModal.tsx`. Su `CriterioCard` ofrece puntaje, estado y comentario del criterio, pero renderiza el arreglo `subcriterios_evaluados` como texto, incluso en modo edición.
- Los tipos `SubcriterioEvaluado` y `CriterioEvaluado` en `features/correcciones/types/index.ts` y sus equivalentes Pydantic ya contienen el desglose: `id`, puntajes, `estado`, `feedback`. La API puede devolver Decimal como texto; el modal solo normaliza actualmente los puntajes del criterio.
- `CorreccionService.editar_correccion` ya serializa el arreglo anidado. El test `test_correccion_service_persistencia_subcriterios.py` comprueba que no se pierde cuando se envía explícitamente, pero permite un padre de 90 con un único subcriterio de 50: no comprueba coherencia ni ediciones reales del desglose.
- La edición reemplaza `criterios_json` y los campos opcionales se serializan con `exclude_unset=True`. Hay que preservar el desglose almacenado si un cliente lo omite y conservar metadatos de política al combinar los criterios.
- La nota académica es un campo editable independiente. `Recalcular nota` suma criterios; al guardar se envían `nota` y `nota_antes_penalizaciones`. El backend aplica después `aplicar_politica_correccion`; una nota académica de 82 puede dar nota final 50. El change existente `politica-entregas-y-tope-nota` documenta esa regla y no debe alterarse.
- `pdf_service.py` ya consume el desglose persistido. `CorreccionDetailModal.tsx` no tiene consumidores encontrados; el alcance funcional es el modal utilizado por Entregas.
- La spec principal `correccion-desglose-subcriterio` exige que el criterio sea suma del desglose para IA v2, pero no define edición manual. Esta ampliación se incorpora como requisitos ADDED en esa misma capacidad.

## Goals / Non-Goals

**Goals:** mantener una única representación persistida y validar la edición en ambos extremos; reutilizar endpoint, hooks de mutación y devolución existentes; separar cálculos puros del renderizado y dejar pruebas de comportamiento.

**Non-Goals:** alterar rúbricas, prompts/proveedores, estados de subcriterios, permisos o auditoría; migrar correcciones históricas; recalcular automáticamente nota académica, penalizaciones o condiciones; publicar cambios en Moodle automáticamente; reformar el modal sin consumidores.

## Decisions

### D1. Reutilizar la edición manual existente

Enviar el arreglo completo de criterios con sus `subcriterios_evaluados` mediante `useUpdateCorreccion` y `PUT /correcciones/{id}`. Se conserva JSONB, respuesta y marcado `editado_manualmente`/usuario editor. No se necesita migración ni dependencia nueva. Un endpoint exclusivo por subcriterio duplicaría validación, autorización y manejo del formulario.

### D2. Editor anidado y copia independiente del formulario

Extraer la tarjeta de criterio y un componente pequeño de subcriterio con puntaje y comentario etiquetados por ID; ambos reciben `isViewMode`. Conservar `estado`, ID y máximo como datos de solo lectura. Normalizar recursivamente puntajes numéricos al inicializar, cancelar y cambiar de corrección. Actualizar inmutablemente por criterio/subcriterio sin tocar props ni arreglos hermanos. Reutilizar el mismo normalizador para restaurar valores. Bloquear Guardar mientras haya errores o una mutación pendiente y conservar el borrador si el guardado falla.

El modal actual excede 500 LOC. Extraer secciones ya existentes a componentes enfocados para que los archivos de producción tocados queden bajo el límite, sin rediseñar la pantalla; componentes nuevos menores a 200 LOC según las reglas de frontend. La lógica de suma/validación vive en utilidades o hook de `features/correcciones/`.

### D3. Puntaje del criterio derivado, nota explícita

Si el criterio contiene desglose, mostrar su puntaje como total no editable independientemente. Una modificación numérica de subcriterio actualiza el total con suma decimal estable; backend repite el cálculo cuando detecta cambio de puntaje comparando con el desglose almacenado, sin confiar en el total enviado. Sin desglose, conservar el selector actual de puntaje de criterio.

No normalizar retroactivamente una inconsistencia histórica por abrir la pantalla ni por editar solo feedback: recalcular el padre únicamente cuando cambia un puntaje de subcriterio. Esto evita que una edición textual cambie una calificación antigua y conserva la cobertura de persistencia existente. El comentario y estado del criterio siguen siendo independientes; los estados de subcriterios se conservan sin derivarlos del puntaje.

Mantener la nota académica manual y `Recalcular nota` explícito. Cambiar subcriterios actualiza el total del criterio y la suma enviada como `nota_antes_penalizaciones`, pero no cambia `nota` hasta esa acción o un ajuste manual. Mantener la explicación visible de que Recalcular aplica la suma. No derivar descuentos ni condiciones nuevas. El servidor sigue aplicando el tope de presentación después de recibir la nota académica. La alternativa de cambiar automáticamente la nota modificaría el flujo de edición existente y requiere otro alcance.

### D4. Validación manual contra la corrección persistida

Validar con números finitos, límites inclusivos y comentario no vacío tras trim. Soportar valores decimales ya admitidos por API sin redondearlos silenciosamente. Para datos del servidor que llegan como texto numérico, convertir al entrar al formulario; rechazar NaN/Infinity y entradas vacías durante edición.

Agregar validación de actualización específica (helper de dominio/servicio y, si hace falta, schema de entrada) sin imponer invariantes nuevos a schemas de respuesta o parseo de IA compartidos. Usar `Decimal` para comparación/suma en backend. Identificar criterios/subcriterios por ID, comparar con el snapshot persistido y rechazar modificaciones de estructura, máximos o estados de subcriterios; validar también que la suma no supere el máximo del criterio. Producir error de entrada específico sin llamar a `repository.update` si falla cualquier parte. Las violaciones de dominio responden HTTP 400; conservar validación estructural de FastAPI existente.

Omitir un desglose en el payload preserva el almacenado; si había desglose no vacío, `null` o `[]` explícitos son intentos de borrado y se rechazan. Una actualización que no toca subcriterios no se usa para volver a validar o reparar datos históricos. No se toma la rúbrica mutable actual como autoridad para reescribir el snapshot de evaluación.

### D5. Compatibilidad y permisos sin cambio de modelo

Mantener `verificar_acceso_correccion` y el contexto de universidad del endpoint; solo añadir cobertura de regresión para el payload anidado. No tocar código de auth/permisos ni crear otro registro de auditoría. Las correcciones sin desglose mantienen su flujo. Conservar las claves hermanas de `criterios_json` al actualizar, incluidas las de política, y dejar la aplicación del tope en la posición actual del flujo.

## Risks / Trade-offs

- [Un cambio de puntaje y otro de nota son acciones distintas] → conservar Recalcular explícito y verificar mensajes/escenarios; no ocultar el efecto bajo una conversión automática.
- [Datos históricos inconsistentes o sin desglose] → no migrar ni reparar al leer; aplicar coherencia nueva al modificar puntajes y preservar campos omitidos.
- [Precisión decimal y valores recibidos como texto] → normalizador recursivo, suma estable en cliente y Decimal en backend; casos con 2.5, 0 y máximo.
- [Validadores compartidos rompen parseo IA o historial] → limitar validación nueva al comando de edición manual y mantener pruebas existentes de persistencia/consulta.
- [Metadatos de política se pierden al reemplazar JSONB] → combinar con el documento existente y probar nota académica/final antes y después del guardado.
- [Refactor necesario en archivos ya grandes] → extracciones acotadas con baseline y pruebas del modal; no añadir lógica al service grande, usar helper de menos de 500 LOC y conservar la orquestación.

## Migration Plan

Sin cambios de base de datos ni backfill. Desplegar validación backend y frontend de edición juntos; los clientes que omiten el campo siguen preservando datos. El rollback de código retira controles/validación nueva sin transformar la estructura JSONB: los valores guardados siguen legibles. No se ejecuta envío a Moodle como parte del guardado.

## Open Questions

Ninguna bloqueante. Los nombres finales de helpers y componentes pueden ajustarse al implementar sin alterar el contrato.
