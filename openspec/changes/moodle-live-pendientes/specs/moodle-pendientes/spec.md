## ADDED Requirements

### Requirement: Endpoint GET /api/pendientes/moodle

El sistema SHALL exponer `GET /api/pendientes/moodle` accesible solo a usuarios autenticados con rol `TUTOR` o superior. El endpoint SHALL consultar el Moodle Mobile App webservice y devolver las submissions pendientes agrupadas por Materia → Unidad (Rúbrica) → Comisión. Solo se incluyen Rúbricas con `moodle_assign_id IS NOT NULL` y Comisiones con `moodle_group_id IS NOT NULL`.

#### Scenario: Tutor con credenciales y materias configuradas
- **WHEN** el tutor llama a `GET /api/pendientes/moodle`
- **THEN** el sistema obtiene las Materias asignadas al tutor con `moodle_course_id` configurado
- **THEN** para cada Materia, obtiene sus Rúbricas con `moodle_assign_id` configurado
- **THEN** para cada Rúbrica, consulta en paralelo el estado de submissions por Comisión con `moodle_group_id` configurado
- **THEN** devuelve HTTP 200 con `MateriasPendientesResponse`

#### Scenario: Estructura del response
- **WHEN** el endpoint devuelve datos exitosamente
- **THEN** el response SHALL tener la forma:
  ```json
  {
    "totalEspera": 5,
    "totalCorregidos": 12,
    "totalSinEntrega": 3,
    "syncedAt": "2026-05-07T14:32:00Z",
    "materias": [
      {
        "id": 1,
        "nombre": "Programación 1",
        "totalEspera": 3,
        "totalCorregidos": 8,
        "totalSinEntrega": 2,
        "unidades": [
          {
            "id": 10,
            "titulo": "TP Integrador: Repetitivas",
            "cmid": 11237,
            "comisiones": [
              {
                "id": 5,
                "nombre": "Comisión 2",
                "codigo": "m26",
                "groupId": 4165,
                "espera": 2,
                "corregidos": 5,
                "sinEntrega": 1
              }
            ]
          }
        ]
      }
    ]
  }
  ```

### Requirement: Conteo de submissions por estado

Para cada combinación (Rúbrica × Comisión) el sistema SHALL consultar `mod_assign_get_submissions` y contar:
- `espera`: submissions donde `gradingstatus = "notgraded"` o `status = "submitted"`
- `corregidos`: submissions donde `gradingstatus = "graded"`
- `sinEntrega`: alumnos del grupo que no tienen ninguna submission (`total_alumnos - submissions_con_entrega`)

#### Scenario: Consulta exitosa a Moodle webservice
- **WHEN** el sistema llama a `mod_assign_get_submissions` con `assignid` y `groupid`
- **THEN** clasifica cada submission según su `gradingstatus` y acumula los conteos

#### Scenario: Moodle no disponible durante la consulta
- **WHEN** la llamada al webservice falla con timeout o error de red
- **THEN** el sistema devuelve HTTP 502 con mensaje `"No se pudo conectar con Moodle. Intentá de nuevo."`
- **THEN** el error es logueado con nivel ERROR incluyendo el user_id y el assign_id

#### Scenario: Rúbricas sin moodle_assign_id configurado
- **WHEN** una Rúbrica asignada al tutor no tiene `moodle_assign_id`
- **THEN** esa Rúbrica es ignorada silenciosamente — no aparece en el response

### Requirement: Construcción del deep link al grader de Moodle

El sistema SHALL construir el deep link al grader de Moodle para cada Comisión con `espera > 0`. El link SHALL apuntar directamente al grader filtrado por estado `requiregrading` y grupo exacto.

#### Scenario: Generación del deep link
- **WHEN** una ComisionPendiente tiene `espera > 0`
- **THEN** el frontend puede construir la URL:
  ```
  {moodle_host}/mod/assign/view.php?id={cmid}&action=grading&status=requiregrading&groupsearchvalue={codigo}&group={groupId}
  ```
- **THEN** el botón "Ver en Moodle" abre esa URL en nueva pestaña

#### Scenario: Comisión sin pendientes
- **WHEN** una ComisionPendiente tiene `espera = 0`
- **THEN** el frontend NO muestra el botón "Ver en Moodle" para esa fila
