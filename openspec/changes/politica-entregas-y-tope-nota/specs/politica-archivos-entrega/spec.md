# Spec Delta

## Purpose

Garantizar que la corrección evalúe código fuente completo y que los incumplimientos de presentación produzcan un límite explícito y reversible por versión de entrega.

## ADDED Requirements

### Requirement: Clasificación previa al filtrado

El sistema SHALL analizar las entradas de cada entrega antes de excluirlas, distinguir material penalizable, ignorado sin penalización y evaluable, y registrar la versión de política, las rutas y el motivo de cada decisión.

#### Scenario: Dependencias presentes pero no consolidadas
- **WHEN** un ZIP contiene `proyecto/node_modules/lib/index.js` y `proyecto/src/api.js`
- **THEN** el análisis identifica la dependencia como penalizable y el consolidado incluye el código fuente sin el contenido de `node_modules`

#### Scenario: Rutas normalizadas sin coincidencias parciales
- **WHEN** la entrega usa separadores Windows o variaciones de mayúsculas en una carpeta penalizable
- **THEN** la clasificación conserva el mismo resultado
- **AND** un nombre como `src/distribucion` no se clasifica como `dist`

### Requirement: Política de artefactos y excepciones

La política predeterminada SHALL excluir con tope las carpetas `node_modules`, `dist`, `target`, `build`, `out` y `bin` con contenido. SHALL excluir sin tope los residuos de sistema, cachés, metadatos Git/editor y lockfiles. La rúbrica SHALL permitir excepciones explícitas para contenidos que la consigna necesita evaluar.

#### Scenario: Bundle compilado antes del código fuente
- **WHEN** un ZIP contiene un bundle grande en `dist` y código en `src/api`
- **THEN** el bundle no consume espacio del contenido evaluable y se registra el incumplimiento

#### Scenario: Residuos sin penalización
- **WHEN** el ZIP contiene código válido junto a `__pycache__`, `.DS_Store`, `__MACOSX`, `.git`, `.idea`, `.vscode` o lockfiles
- **THEN** esos residuos no forman parte del consolidado ni activan el máximo de nota

#### Scenario: Carpeta requerida por la consigna
- **WHEN** la rúbrica declara una excepción explícita para una carpeta normalmente penalizable
- **THEN** su presencia no activa el tope y su contenido evaluable se procesa según la excepción

#### Scenario: Carpeta vacía
- **WHEN** sólo existe una entrada de directorio vacía con nombre penalizable
- **THEN** no se registra contenido penalizable por esa entrada sola

### Requirement: Configuración relevante evaluable

El sistema SHALL admitir configuración relevante del proyecto, incluyendo `.properties`, mediante una política explícita de selección y extensiones de rúbrica. No SHALL incorporar indiscriminadamente archivos desconocidos ni archivos de credenciales por el mero hecho de ser texto.

#### Scenario: Properties conserva evidencia de configuración
- **WHEN** una entrega contiene código válido y `src/main/resources/application.properties`
- **THEN** el archivo de configuración admitido se conserva en el consolidado

#### Scenario: Desconocidos no se incorporan automáticamente
- **WHEN** una entrega contiene un archivo fuera de la selección admitida
- **THEN** el análisis informa su exclusión sin convertirla automáticamente en una infracción penalizable

### Requirement: Máximo de nota posterior a la evaluación

El sistema SHALL conservar la nota académica y calcular la final como `min(nota_academica, 50)` cuando la versión evaluada contiene una infracción penalizable activa. SHALL aplicar la misma regla después de una evaluación automática, carga externa o modificación manual.

#### Scenario: Nota académica superior al máximo
- **WHEN** una evaluación obtiene 82/100 y la entrega tiene una infracción penalizable activa
- **THEN** la nota académica conserva 82 y la nota final es 50

#### Scenario: Nota académica inferior al máximo
- **WHEN** una evaluación obtiene 35/100 y la entrega tiene una infracción penalizable activa
- **THEN** la nota final conserva 35 y no se transforma en 50

#### Scenario: Edición y evaluación externa respetan la regla
- **WHEN** se registra una nota superior a 50 por edición manual o carga externa para una versión restringida
- **THEN** la nota final no supera 50 y se preserva la nota académica registrada

### Requirement: Devolución explícita de la restricción

El sistema SHALL informar la nota académica, la nota final, el motivo y las rutas que activan el máximo, junto a la indicación de presentar una versión limpia. La devolución y las exportaciones SHALL conservar la nota final y la explicación del límite.

#### Scenario: Tutor y alumno identifican la causa
- **WHEN** se consulta una corrección restringida o se genera su devolución
- **THEN** se informa el máximo de 50/100, la nota académica, la nota final y las rutas penalizables
- **AND** se indica que una entrega limpia requiere una nueva evaluación

### Requirement: Restricción vinculada a la versión entregada

El sistema SHALL reanalizar cada versión nueva, preservar el historial anterior y retirar la restricción vigente cuando la nueva entrega esté limpia. Una versión nueva SHALL requerir evaluación; un reintento de importación Moodle sin cambios SHALL ser idempotente. No SHALL sancionar automáticamente entregas históricas sin análisis.

#### Scenario: Reentrega limpia
- **WHEN** se recibe una versión nueva sin el material que activaba el máximo
- **THEN** la versión vigente no tiene ese máximo y queda pendiente de nueva evaluación
- **AND** el historial conserva la entrega y corrección restringidas anteriores

#### Scenario: Reimportación idéntica
- **WHEN** se repite la importación de la misma versión de Moodle
- **THEN** no se reemplaza su corrección ni se crea un historial redundante

#### Scenario: Reentrega todavía incumplidora
- **WHEN** una nueva versión todavía incluye material penalizable
- **THEN** su análisis activa nuevamente el máximo correspondiente

#### Scenario: Registro histórico sin evidencia
- **WHEN** una corrección anterior no tiene análisis de la política
- **THEN** no se cambia automáticamente su nota ni se inventan rutas penalizables

### Requirement: Integridad del contenido enviado a corrección

El sistema SHALL impedir una corrección definitiva si el contenido evaluable, después del filtrado, supera el límite configurado. SHALL informar la causa al tutor sin enviar un prefijo incompleto a la IA ni guardar una nueva nota definitiva basada en ese prefijo.

#### Scenario: Código legítimo todavía demasiado grande
- **WHEN** el contenido evaluable supera el límite configurado después de excluir artefactos
- **THEN** la corrección se bloquea con mensaje accionable y no se invoca el proveedor

#### Scenario: Contenido dentro del límite
- **WHEN** el contenido evaluable no supera el límite configurado
- **THEN** se envía completo al proveedor y se evalúa normalmente
