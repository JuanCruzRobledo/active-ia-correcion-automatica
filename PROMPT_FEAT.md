# Prompt para Claude Opus: planificar mejora del flujo Moodle + correcciones en Active-IA

Actua como arquitecto senior full-stack para el proyecto **Active-IA**, una plataforma de correccion automatica de trabajos practicos con IA para la TUD. Tu tarea es **crear un plan tecnico de implementacion**, no escribir codigo todavia.

## Contexto del proyecto

Active-IA usa:

- Backend: FastAPI async, SQLAlchemy async, Alembic, Clean Architecture estricta: `Router -> Service -> Repository`.
- Frontend: React + TypeScript strict + Tailwind + TanStack Query.
- Correccion IA: N8N + Gemini, con API keys cifradas AES-256.
- Roles: `ADMIN`, `COORDINADOR`, `TUTOR`.
- Estados de entrega: `SUBIDA`, `PENDIENTE`, `CORREGIDA`, `ERROR`.
- Tipos de rubrica actuales: `TP`, `PARCIAL_1`, `PARCIAL_2`, `RECUPERATORIO_1`, `RECUPERATORIO_2`, `FINAL`, `GLOBAL`.

Convenciones obligatorias del repo:

- No poner logica de negocio en routers.
- No acceder a DB desde services sin repository cuando ya existe un repository aplicable.
- Validar permisos en cada endpoint.
- No guardar ni loguear secretos en texto plano.
- Usar AES-256 para credenciales/API keys.
- Mantener archivos por debajo de 500 LOC cuando sea razonable.
- Usar migraciones Alembic si se agregan campos/tablas.
- Seguir patrones existentes del proyecto antes de proponer abstracciones nuevas.

## Estado actual relevante

Ya existe una integracion inicial con Moodle para mostrar pendientes:

- `backend/app/services/moodle_service.py`
  - Obtiene token con `/login/token.php`.
  - Cachea token por usuario con TTL.
  - Usa `mod_assign_get_assignments` para resolver `cmid -> assignment instance id`.
  - Usa `core_enrol_get_enrolled_users` para obtener alumnos de un grupo.
  - Usa `mod_assign_get_submissions` y `mod_assign_get_grades` para contar pendientes.
  - Devuelve pendientes agrupados por `Materia -> Rubrica/Unidad -> Comision`.
- `backend/app/routers/pendientes.py`
  - Expone `GET /api/pendientes/moodle`.
- `backend/app/schemas/pendientes.py`
  - Define `MateriaPendiente`, `UnidadPendiente`, `ComisionPendiente`.
- `frontend/src/features/pendientes/`
  - Pagina `/pendientes`.
  - Muestra stat cards, filtros, acordeones por materia/unidad/comision y boton "Ver en Moodle".
- Campos Moodle existentes:
  - `Usuario`: `moodle_username`, `moodle_password_encrypted`, `moodle_host`.
  - `Materia`: `moodle_course_id`.
  - `Rubrica`: `moodle_assign_id` (actualmente es el `cmid` visible en URL Moodle).
  - `Comision`: `moodle_group_id`, `moodle_group_code`.
- Entregas:
  - `backend/app/services/entrega_service.py` ya soporta carga individual y masiva, consolidacion de ZIP/TXT/codigo individual y PDF en base64.
  - El indice unico es `rubrica_id + alumno_nombre`.
  - Si se sobrescribe una entrega, existe historial, pero no se debe sobrescribir una entrega que ya tiene correccion.
- Correcciones:
  - `backend/app/services/correccion_service.py` corrige individualmente y en lote.
  - `POST /api/correcciones/lote` encola lote con background task.
  - `frontend/src/features/entregas/pages/EntregasPage.tsx` ya concentra acciones como corregir, descargar PDF, archivar y eliminar.
- Perfil:
  - `backend/app/routers/perfil.py` valida API key Gemini con un modelo flash y guarda `gemini_api_key_valid`.
  - Falta clasificar si la API key es paga, gratuita o error.

Lee tambien:

- `AGENTS.md`
- `CLAUDE.md`
- `openspec/changes/moodle-live-pendientes/`
- `skills/python-fastapi/SKILL.md`
- `skills/react-typescript/SKILL.md`
- `skills/correccion-ia/SKILL.md`
- `skills/rubricas/SKILL.md`

## Problema actual

El flujo actual de "Pendientes" simplifico la visibilidad, pero todavia es incomodo para tutores:

1. El tutor entra a `/pendientes`.
2. Ve trabajos pendientes por corregir.
3. Solo tiene un boton "Ver en Moodle" que abre el grader de Moodle.
4. El tutor descarga manualmente las entregas desde Moodle.
5. Luego vuelve a Active-IA, entra en la rubrica correspondiente con "Ver entregas" y sube manualmente el ZIP con las entregas.
6. Despues de corregir en Active-IA, debe descargar PDFs y volver a Moodle para publicar nota/comentario manualmente.

Queremos que Active-IA reduzca ese trabajo repetitivo usando las credenciales Moodle de cada tutor.

## Funcionalidad 1: importar pendientes Moodle a Active-IA

Agregar la posibilidad de descargar desde Moodle las entregas pendientes de correccion y cargarlas automaticamente en la rubrica/comision correcta de Active-IA.

Ejemplo: si un tutor tiene 56 entregas pendientes distribuidas asi:

- 4 de Evaluacion 1 - Programacion 3
- 6 de Evaluacion 2 - Programacion 3
- 2 de TP 3 JavaScript - Programacion 3
- 10 de Parcial 1 - Programacion 1
- 14 de TP 3 Repetitivas - Programacion 1
- 10 de TP 6 Funciones - Programacion 1
- 10 de TP 8 Manejo de errores - Programacion 1

Entonces Active-IA deberia poder:

- Detectar a que `Materia`, `Rubrica` y `Comision` pertenece cada entrega usando la configuracion Moodle existente.
- Descargar los archivos de cada alumno pendiente desde Moodle.
- Crear las `Entrega` correspondientes en estado `SUBIDA`, asociadas a su `rubrica_id` y `comision_id`.
- Reutilizar la logica existente de `EntregaService` para validacion, consolidacion, PDF/base64, historial e idempotencia.
- Evitar duplicados por `rubrica_id + alumno_nombre`.
- No sobrescribir entregas ya corregidas.
- Manejar re-entregas de Moodle como caso explicito.
- Devolver un resumen claro: descargadas/cargadas, omitidas, duplicadas, con error.

El plan debe decidir si conviene exponer acciones por nivel:

- Importar una comision/unidad puntual.
- Importar todas las pendientes de una materia.
- Importar todas las pendientes del tutor.

El boton "Ver en Moodle" debe mantenerse.

## Funcionalidad 2: subir correccion y devolucion a Moodle

Una vez que una entrega este en `CORREGIDA`, desde el mismo apartado donde hoy estan acciones como "Corregir", "Descargar PDF", "Archivar" y "Eliminar", debe aparecer una accion:

**"Subir correccion a Moodle"**

Al hacer click:

- Abrir un modal.
- Mostrar la nota final que se va a enviar.
- Mostrar/editar el comentario que se va a publicar en Moodle.
- Incluir un enlace de texto `devolucion` apuntando al PDF de devolucion generado por Active-IA.
- El usuario debe poder editar el comentario antes de enviar.
- Al confirmar con "Enviar correccion", Active-IA debe usar la API de Moodle para publicar nota y feedback.

Punto tecnico importante: el link al PDF debe ser realmente accesible por el alumno desde Moodle. El plan debe resolver si se necesita un endpoint publico con token firmado, expiracion controlada, adjunto de feedback en Moodle, o alguna alternativa segura. No asumir que el endpoint actual de descarga PDF sirve para alumnos si requiere JWT de Active-IA.

### Plantillas de comentario para trabajos practicos (`TP`)

Corregir y normalizar estas reglas antes de planificar, porque el texto original tenia operadores ambiguos. La intencion probable es una escala 0-100 donde `>= 60` aprueba y `< 60` desaprueba.

Proponer en el plan una forma configurable para estas plantillas. Como base, usar:

- Nota `>= 90`:
  - `Excelente {nombre_alumno}!`
  - `Te dejo tu devolucion: {link_devolucion}`
- Nota `81-89`:
  - `Muy bien {nombre_alumno}!`
  - `Te dejo tu devolucion: {link_devolucion}`
- Nota `71-80`:
  - `Bien {nombre_alumno}!`
  - `Te dejo tu devolucion: {link_devolucion}`
- Nota `60-70`:
  - `Bien {nombre_alumno}! Revisa con detalle tu entrega PDF.`
  - `Te dejo tu devolucion: {link_devolucion}`
- Nota `< 60`:
  - `Hola {nombre_alumno}, revisa tu entrega PDF para poder realizar la reentrega del TP.`
  - `Te dejo tu devolucion: {link_devolucion}`

### Plantillas para rubricas que no son `TP`

Para `PARCIAL_1`, `PARCIAL_2`, `RECUPERATORIO_1`, `RECUPERATORIO_2`, `FINAL`, `GLOBAL` o cualquier tipo distinto de `TP`:

- No debe haber comentario predeterminado de evaluacion.
- Si puede aparecer el cierre con el link: `Te dejo tu devolucion: {link_devolucion}`.
- Es obligatorio que el tutor escriba un comentario propio antes de enviar.

### Nota que se envia a Moodle

El plan debe validar esta regla con el estado real de Moodle y la configuracion de calificaciones:

- Para trabajos practicos (`TP`), Moodle deberia recibir escala cualitativa:
  - `Aprobado` si la nota final Active-IA es `>= 60`.
  - `Desaprobado` si la nota final Active-IA es `< 60`.
- Para rubricas no `TP`, Moodle debe recibir la nota numerica final vigente en Active-IA.
  - Ejemplo: si IA corrigio 90 pero el tutor edito a 100, Moodle recibe 100.

No asumir que Moodle usa siempre escala numerica o siempre escala cualitativa. El plan debe incluir verificacion/mapeo de escala por assignment y manejo de error si la escala no coincide con la regla.

## Funcionalidad 3: API key Gemini paga y correccion masiva global

Agregar clasificacion del tipo de API key Gemini en el perfil del usuario:

- Paga
- Gratuita
- Error / invalida

Regla solicitada:

1. Al guardar la API key, probar primero contra un modelo Pro, por ejemplo `gemini-pro-latest`.
2. Si falla con modelo Pro, probar contra un modelo Lite/Flash, por ejemplo `gemini-flash-lite-latest`.
3. Si Pro responde correctamente: API paga.
4. Si Pro falla pero Lite/Flash responde: API gratuita.
5. Si ambos fallan: error/invalida.

El plan debe verificar nombres reales de modelos, manejo de errores y compatibilidad con la API actual de Gemini. Si los nombres `gemini-pro-latest` o `gemini-flash-lite-latest` no son validos para el proyecto, proponer nombres configurables por entorno.

Si el tutor tiene API key paga:

- Debe poder corregir todos sus trabajos en estado `SUBIDA`, aunque sean de distintas materias, comisiones o rubricas.
- La correccion debe encolarse y procesarse respetando la rubrica correcta de cada entrega.
- El resultado debe reflejarse luego en cada apartado/rubrica correspondiente.
- Debe haber feedback de progreso y errores.

Ejemplo de UI deseada:

- En el dashboard del tutor, en el cuadro amarillo de pendientes:
  - `Pendientes: 56 por corregir`
  - Boton: `Corregir todo (API Key paga)`
- Al clickear, se inicia una correccion por lotes de las 56 entregas `SUBIDA`.

El plan debe considerar que el endpoint actual de lote tiene limite de 50 y procesa secuencialmente con sleeps por rate limit. Proponer como adaptar esto para API paga sin romper el flujo actual ni saturar N8N/Gemini.

## Requisitos de seguridad, permisos y auditoria

El plan debe cubrir:

- Solo el tutor asignado a la comision, admin o rol autorizado puede importar/subir correcciones.
- Las credenciales Moodle se descifran solo en memoria y nunca se loguean.
- Las API keys Gemini no se loguean.
- Los links a PDFs no deben exponer datos de otros alumnos.
- Registrar estado de sincronizacion con Moodle: pendiente, enviado, error, fecha, usuario, mensaje de error, intento asociado si aplica.
- Evitar doble envio accidental de la misma correccion a Moodle.
- Manejar Moodle offline, credenciales invalidas, token vencido, permisos insuficientes, assignment sin escala esperada, alumno no encontrado o archivo no descargable.

## Entregable esperado de Claude

Devuelve un **plan tecnico en espanol**, no codigo. La respuesta debe incluir:

1. Supuestos y ambiguedades detectadas que deben confirmarse.
2. Diseno de arquitectura por backend/frontend/datos/integraciones.
3. Cambios de modelo de datos y migraciones necesarias.
4. Endpoints nuevos o modificaciones a endpoints existentes.
5. Servicios/repositories a crear o extender.
6. Flujo de importacion desde Moodle paso a paso.
7. Flujo de subida de correccion a Moodle paso a paso.
8. Flujo de clasificacion de API key Gemini y correccion masiva global.
9. Estados de UI, modales, botones, errores y feedback al tutor.
10. Estrategia de idempotencia, reintentos y manejo de errores.
11. Estrategia de testing backend/frontend.
12. Riesgos principales y mitigaciones.
13. Criterios de aceptacion verificables.
14. Desglose de tareas implementables en orden recomendado.

No propongas una reescritura grande del proyecto. Mantene el alcance centrado en estas tres funcionalidades y apoyate en los patrones existentes.
