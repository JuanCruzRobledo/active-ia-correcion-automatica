# Proposal

## Why

Los bundles de `dist/` pueden ocupar el inicio del consolidado y desplazar el código fuente cuando se recorta el texto para la IA. El sistema debe evaluar el código completo disponible y distinguir el incumplimiento de presentación de la calidad académica del trabajo.

## What Changes

- Analizar el ZIP antes de excluir entradas, registrar una política versionada y distinguir archivos penalizables, ignorados sin penalización y evaluables.
- Excluir dependencias y compilados del consolidado; aplicar un máximo de 50/100 después de obtener la nota académica cuando la versión entregada contiene carpetas penalizables.
- Conservar configuración útil, como `.properties`, y permitir excepciones explícitas por rúbrica.
- Mostrar nota académica, nota final, motivos y cómo subsanar la entrega en detalle y devolución.
- Reanalizar las reentregas y levantar el tope sólo para una versión limpia, que debe evaluarse nuevamente, conservando el historial.
- Mantener idempotencia de Moodle para versiones sin cambios y admitir versiones nuevas.
- Impedir una corrección definitiva cuando el contenido evaluable supera el límite, en lugar de enviar un prefijo incompleto.
- No recalcular automáticamente calificaciones históricas ni reprocesar entregas existentes.

## Capabilities

### New Capabilities

- `politica-archivos-entrega`: clasificación de archivos, evidencia de presentación por versión, tope posterior a la evaluación e integridad del contenido corregido.

### Modified Capabilities

Ninguna. Se preservan los contratos vigentes de límites de subida e historial de correcciones; la nueva política agrega información de presentación y nota académica.

## Impact

Backend: consolidación, entrega/importación Moodle, corrección automática/externa/manual, modelos y repositorios de entrega/corrección/historial, schemas y devolución PDF/Excel. Frontend: detalle de entrega y corrección e información necesaria para excepciones por rúbrica. Puede requerir migración aditiva; no se aplicará a producción durante el desarrollo. No se modifican autenticación, pertenencia ni credenciales.
