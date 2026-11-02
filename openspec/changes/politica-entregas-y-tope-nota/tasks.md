# Tasks

## 1. Política y consolidación

- [x] 1.1 Implementar clasificador puro versionado con detección previa al filtro, normalización de rutas, categorías penalizables/ignoradas/evaluables y pruebas RED→GREEN de dependencias, bundles, residuos y coincidencias parciales.
- [x] 1.2 Integrar la selección de configuración útil y excepciones por rúbrica, documentar política predeterminada y verificar `.properties`, lockfiles y excepciones mediante pruebas.
- [x] 1.3 Integrar el análisis en carga individual, masiva e importación Moodle sin leer dependencias excluidas; verificar que `src/api` llega al consolidado pese a bundles grandes.

## 2. Persistencia y versiones

- [x] 2.1 Persistir análisis y versión de política por entrega y en su historial, con migración aditiva si corresponde; verificar serialización, compatibilidad histórica y conservación de evidencia.
- [x] 2.2 Actualizar nuevas versiones Moodle sin romper idempotencia; verificar importación idéntica, reentrega limpia e incumplimiento persistente.
- [x] 2.3 Al reemplazar la entrega, conservar historial y exigir nueva evaluación; verificar que una versión limpia retira el máximo sin heredar una corrección vigente anterior.

## 3. Nota y cobertura

- [x] 3.1 Aplicar centralmente `min(nota_academica, 50)` después de evaluación automática/externa/manual y conservar ambas notas; verificar casos mayores, iguales y menores a 50 y entrega sin infracción.
- [x] 3.2 Bloquear correcciones con contenido evaluable excesivo sin invocar proveedor ni guardar nota definitiva; verificar exceso y límite exacto.
- [x] 3.3 Incorporar la explicación del máximo y la subsanación en devolución/exportaciones; verificar ambas notas, rutas y ausencia de sanción en residuos inocuos.

## 4. Interfaz

- [x] 4.1 Resolver y registrar la política visual exigida por el proyecto antes de cambios visuales; verificado: elección explícita del usuario "Sin sistema visual ni mockups; conservar el estilo actual", registrada en `design-system/README.md` (Mode: off, Approval: skipped).
- [x] 4.2 Mostrar análisis, motivo del máximo y ambas notas en el detalle con el estilo autorizado; verificados estados restringido, limpio e histórico mediante pruebas de componentes y capturas móvil/escritorio en `verification/`.
- [x] 4.3 Exponer excepciones por rúbrica cuando corresponda al contrato implementado; verificados editor de directorios permitidos, preservación de metadata y representación accesible mediante pruebas y captura real del editor en `verification/`.

## 5. Verificación integrada

- [x] 5.1 Ejecutar pruebas backend/frontend con entorno aislado, lint y verificaciones de tipos pertinentes, y documentar resultado y fallos preexistentes sin tocar producción.
- [x] 5.2 Verificar el flujo completo de importación sucia → corrección restringida → reentrega limpia → nueva corrección libre, incluida devolución, con pruebas integradas reproducibles.
- [x] 5.3 Registrar evidencia TDD por tarea y verificación visual disponible, limitaciones y pasos de despliegue/migración sin ejecutarlos en producción.

## Workflow follow-up

- Revisar el resultado antes de desplegar o aplicar migraciones a producción.
- Archivar el change sólo cuando las tareas y revisiones estén completas.
