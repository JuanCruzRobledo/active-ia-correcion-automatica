## ADDED Requirements

### Requirement: Página /pendientes con acordeón Materia → Unidad → Comisión

La ruta `/pendientes` SHALL renderizar `PendientesPage` accesible solo a usuarios con rol `TUTOR` o `ADMIN`. La página SHALL mostrar las entregas pendientes de Moodle organizadas jerárquicamente: Materia (nivel 1) → Unidad/Rúbrica (nivel 2) → Comisión (nivel 3). Los datos se obtienen desde `GET /api/pendientes/moodle` via el hook `usePendientesMoodle` con `staleTime: 5 * 60 * 1000`.

#### Scenario: Carga inicial de la página
- **WHEN** el tutor navega a `/pendientes`
- **THEN** la página muestra 3 stat cards globales: "En espera", "Corregidos", "Sin entrega"
- **THEN** todos los acordeones de Materia y Unidad están expandidos por defecto
- **THEN** el hook inicia el fetch a `GET /api/pendientes/moodle`

#### Scenario: Estado de loading
- **WHEN** los datos están siendo cargados
- **THEN** la página muestra un estado de carga (skeleton o spinner)

#### Scenario: Tutor sin credenciales Moodle configuradas
- **WHEN** el endpoint devuelve HTTP 424
- **THEN** la página muestra un estado vacío con CTA: "Configurá tus credenciales Moodle en tu perfil" con link a `/perfil`

### Requirement: Stat cards globales

La página SHALL mostrar 3 stat cards en la parte superior usando el componente existente `<StatCard>`:
- **"En espera"**: suma de todos los `espera` — variante `destructive`, ícono `AlertCircle`
- **"Corregidos"**: suma de todos los `corregidos` — variante `success`, ícono `CheckCircle`  
- **"Sin entrega"**: suma de todos los `sinEntrega` — variante `default`, ícono `MinusCircle`

Los valores son la suma de todas las Materias → Unidades → Comisiones.

#### Scenario: Conteo correcto en las stat cards
- **WHEN** la página recibe datos con múltiples materias
- **THEN** las stat cards muestran los totales globales del response (`totalEspera`, `totalCorregidos`, `totalSinEntrega`)

### Requirement: Filtro "Solo con pendientes"

La página SHALL incluir dos chips de filtro rápido:
- **"Todas las unidades"**: muestra todos los bloques de unidad (default)
- **"Solo con pendientes (N)"**: oculta unidades donde todas las comisiones tienen `espera = 0`; N es el count de unidades con pendientes

El filtro es local (no re-fetch). El estado del filtro activo se refleja visualmente en el chip seleccionado.

#### Scenario: Filtro "Solo con pendientes" activo
- **WHEN** el tutor selecciona "Solo con pendientes"
- **THEN** solo se renderizan los `UnidadBlock` con al menos una `ComisionRow` con `espera > 0`
- **THEN** los bloques de unidad sin pendientes desaparecen del DOM

#### Scenario: Volver a "Todas las unidades"
- **WHEN** el tutor selecciona "Todas las unidades"
- **THEN** todos los `UnidadBlock` vuelven a ser visibles

### Requirement: MateriaBlock — acordeón de nivel Materia

El componente `MateriaBlock` SHALL renderizar un acordeón colapsable por Materia. El header SHALL mostrar el nombre de la materia y pills de resumen (espera, corregidos, sin entrega). El estado `open` es local con `useState(true)` (expandido por defecto).

#### Scenario: Toggle del acordeón de Materia
- **WHEN** el tutor hace click en el header del `MateriaBlock`
- **THEN** el body con los `UnidadBlock` se colapsa o expande
- **THEN** el chevron rota 180° cuando está expandido

### Requirement: UnidadBlock — acordeón de nivel Unidad/Rúbrica

El componente `UnidadBlock` SHALL renderizar un acordeón colapsable por Unidad. El header SHALL mostrar badge numérico de unidad, título, subtítulo y pills de resumen. El estado `open` es local con `useState(true)`. Si `showUrgentOnly = true` y la unidad no tiene comisiones con `espera > 0`, el bloque NO se renderiza.

#### Scenario: Toggle del acordeón de Unidad
- **WHEN** el tutor hace click en el header del `UnidadBlock`
- **THEN** la lista de `ComisionRow` se colapsa o expande

#### Scenario: Unidad filtrada por "Solo con pendientes"
- **WHEN** `showUrgentOnly = true` y todas las comisiones tienen `espera = 0`
- **THEN** el `UnidadBlock` no se renderiza en absoluto

### Requirement: ComisionRow — fila por comisión

El componente `ComisionRow` SHALL mostrar el nombre de la comisión, los conteos en línea (espera en rojo, corregidos en verde, sin entrega en gris) y — solo si `espera > 0` — el botón "Ver en Moodle" que abre el deep link en nueva pestaña (`target="_blank"`).

#### Scenario: Fila con pendientes
- **WHEN** `comision.espera > 0`
- **THEN** se muestra el botón "Ver en Moodle" con ícono `ExternalLink`
- **THEN** el click abre `{moodle_host}/mod/assign/view.php?id={cmid}&action=grading&status=requiregrading&groupsearchvalue={codigo}&group={groupId}` en nueva pestaña

#### Scenario: Fila sin pendientes
- **WHEN** `comision.espera === 0`
- **THEN** el botón "Ver en Moodle" NO se renderiza

### Requirement: Botón "Actualizar"

La página SHALL incluir un botón "Actualizar" en el header. Al hacer click, SHALL invalidar la query de Tanstack Query para forzar un re-fetch desde Moodle.

#### Scenario: Click en Actualizar
- **WHEN** el tutor hace click en "Actualizar"
- **THEN** `queryClient.invalidateQueries(['pendientes-moodle'])` se ejecuta
- **THEN** la página muestra el estado de loading mientras re-fetcha

### Requirement: Banner de alerta en DashboardTutor

El componente `DashboardTutor` SHALL mostrar un banner de alerta al final del layout cuando `pendientesData?.totalEspera > 0`. El banner SHALL mostrar el conteo de entregas pendientes y un botón "Ver pendientes" que navega a `/pendientes`.

#### Scenario: Banner visible con pendientes
- **WHEN** `usePendientesMoodle` devuelve `totalEspera > 0`
- **THEN** el banner aparece con el texto `"{N} entregas esperando calificación en Moodle"`
- **THEN** el botón "Ver pendientes" navega a `/pendientes`

#### Scenario: Banner oculto sin pendientes
- **WHEN** `totalEspera === 0` o los datos no están disponibles
- **THEN** el banner NO se renderiza

### Requirement: Ítem "Pendientes" en el Sidebar

El `Sidebar` SHALL incluir un ítem de navegación `{ to: '/pendientes', icon: Clock, label: 'Pendientes', roles: ['TUTOR', 'ADMIN'] }` posicionado después del ítem "Entregas".

#### Scenario: Visibilidad del ítem de Sidebar
- **WHEN** el usuario autenticado tiene rol `TUTOR` o `ADMIN`
- **THEN** el ítem "Pendientes" aparece en el sidebar después de "Entregas"

#### Scenario: Ruta protegida
- **WHEN** un usuario con rol `COORDINADOR` intenta acceder a `/pendientes`
- **THEN** es redirigido o ve un estado de acceso denegado
