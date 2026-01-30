# Estado del Proyecto - Active-IA

> **IMPORTANTE**: Actualiza este archivo al FINAL de cada sesion de trabajo.

---

## Estado Actual

| Campo                     | Valor                      |
| ------------------------- | -------------------------- |
| **Fase actual**           | Fase 6 - Frontend Features |
| **Tarea actual**          | 6.16 - Crear EntregasPage  |
| **Ultima sesion**         | 2026-01-29                 |
| **Porcentaje completado** | 81%                        |

---

## Progreso por Fase

| #   | Fase                          | Estado       | Progreso     |
| --- | ----------------------------- | ------------ | ------------ |
| 0   | Setup Inicial                 | `COMPLETADA` | 8/8 tareas   |
| 1   | Backend - Auth + Modelos      | `COMPLETADA` | 12/12 tareas |
| 2   | Backend - CRUD Basico         | `COMPLETADA` | 15/15 tareas |
| 3   | Backend - Rubricas + Entregas | `COMPLETADA` | 14/14 tareas |
| 4   | Backend - Correccion IA       | `COMPLETADA` | 10/10 tareas |
| 5   | Frontend - Setup + Auth       | `COMPLETADA` | 10/10 tareas |
| 6   | Frontend - Features           | `EN CURSO`   | 15/20 tareas |
| 7   | Testing + Integracion         | `PENDIENTE`  | 0/8 tareas   |
| 8   | Docker + Deploy               | `PENDIENTE`  | 0/6 tareas   |

**Total**: 84/103 tareas completadas

---

## Ultima Sesion

### Fecha: 2026-01-29 (Sesión 21)

### Duracion: ~45 min

### Que se hizo:

- ✅ **Tarea 6.14: Crear RubricaEditor**
  - Instalación de @dnd-kit para drag-and-drop de criterios
    - `npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`
  - Creación de `frontend/src/features/rubricas/components/RubricaEditor.tsx`
    - Componente modal completo con 500+ líneas de código
    - Dos modos: crear y editar rúbricas
    - Formulario con validación React Hook Form + Zod
    - Campos implementados:
      - Tipo (enum: TP, PARCIAL_1, PARCIAL_2, RECUPERATORIO_1, RECUPERATORIO_2, FINAL, GLOBAL)
      - Número (1-999, deshabilitado en edición)
      - Año (2020-2100, deshabilitado en edición)
      - Nombre (texto libre, editable)
    - Editor de criterios con drag-and-drop:
      - Lista sortable de criterios con @dnd-kit
      - Componente CriterioItem para cada criterio
      - Campos por criterio: nombre, descripción, puntaje_maximo
      - Drag handle con icono GripVertical
      - Botón eliminar por criterio
      - Máximo 20 criterios
    - Validación en tiempo real:
      - Suma de puntajes debe ser exactamente 100
      - Indicador visual de puntaje total (verde=100, rojo>100, amarillo<100)
      - Mensaje dinámico "faltan X" o "sobran X"
      - Botón submit deshabilitado si suma ≠ 100
    - Botón "Agregar Criterio" al final de la lista
    - Integración con hooks:
      - useCreateRubrica para crear nueva rúbrica
      - useUpdateRubrica para editar existente
      - Invalidación automática de cache al guardar
    - Estados de loading:
      - Spinner en botón submit durante guardado
      - Deshabilitado durante loading
    - Estructura de datos:
      - criterios_json con CriteriosStructure (puntaje_maximo + criterios[])
      - IDs únicos con crypto.randomUUID() para cada criterio
    - Responsive design con grid adaptativo
  - Creación de `frontend/src/features/rubricas/components/index.ts`
    - Barrel export de RubricaEditor
  - Actualización de `frontend/src/features/rubricas/index.ts`
    - Agregado export de components
  - Integración en RubricasPage:
    - Import de RubricaEditor
    - Reemplazo del placeholder modal con componente real
    - Paso de props: isOpen, onClose, materiaId, rubrica
    - Uso de useRubrica para obtener datos en modo edición
  - Corrección de errores TypeScript:
    - DragEndEvent como type import
    - Eliminado import no usado (arrayMove, X)
    - Ajuste de schema Zod (sin required_error, usar invalid_type_error)
    - Alineación con tipos backend (anio en lugar de anio_academico)
    - Eliminado campo descripcion que no existe en backend
    - Agregado campo numero que faltaba
    - Ajuste de criterios_json.criterios en lugar de solo criterios
  - Build exitoso: 629.19 kB bundle (gzip: 197.35 kB) - Sin errores TypeScript
  - Actualización de ROADMAP.md marcando tarea 6.14 como completada

### Proxima tarea:

- **6.16**: Crear EntregasPage

### Problemas encontrados:

- Ninguno

### Notas:

- ✅ **Tarea 6.15 COMPLETADA** - Service layer completo para entregas
- Implementado siguiendo patrones de React Query y Clean Architecture
- Service con 6 métodos: getAll, getById, create, createMasiva, delete, getContenido
- Hooks con query key factory para cache management eficiente
- Soporte para file uploads con FormData (multipart/form-data)
- Todos los endpoints del backend cubiertos:
  - Individual upload (create)
  - Bulk upload (createMasiva)
  - List with filters (getAll)
  - Detail view (getById)
  - Code viewer (getContenido)
  - Soft delete (delete)
- Filtros implementados: comision_id, rubrica_id, estado, search, include_inactive, paginación
- 6 hooks React Query con invalidación inteligente de cache
- staleTime de 5 minutos para queries optimizadas
- Build exitoso: 629.19 kB bundle (gzip: 197.35 kB) - Sin errores TypeScript
- Ready para siguiente tarea (EntregasPage UI)
- Progreso Fase 6: 15/20 tareas (75%)

---

## Log de Sesiones

| Fecha      | Duracion | Fase   | Tareas completadas     | Notas                 |
| ---------- | -------- | ------ | ---------------------- | --------------------- |
| 2026-01-26 | 30 min   | Setup  | Sistema de continuidad | Configuracion inicial |
| 2026-01-28 | 15 min   | Fase 5 | 5.9 - LoginPage        | Build exitoso         |

---

## Bloqueantes Actuales

> Nada bloqueante actualmente.

---

## Decisiones Tomadas

| Fecha      | Decision                                    | Contexto                                                                      |
| ---------- | ------------------------------------------- | ----------------------------------------------------------------------------- |
| 2026-01-26 | Copiar docs en lugar de symlink             | Para portabilidad del proyecto                                                |
| 2026-01-26 | Tareas atomicas en ROADMAP                  | Maximo 1-2 archivos por tarea                                                 |
| 2026-01-26 | Usar estructura de 05-ARQUITECTURA-STACK.md | ROADMAP simplificaba, docs/specs tiene estructura completa con api/v1/routers |

---

## Archivos Modificados Recientemente

| Archivo                                                             | Ultima modificacion | Por                     |
| ------------------------------------------------------------------- | ------------------- | ----------------------- |
| frontend/src/features/dashboard/pages/DashboardPage.tsx             | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/components/DashboardAdmin.tsx       | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/components/DashboardCoordinador.tsx | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/components/DashboardTutor.tsx       | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/components/StatCard.tsx             | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/components/QuickActions.tsx         | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/components/RecentActivity.tsx       | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/components/CorrectionsProgress.tsx  | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/components/ComisionCard.tsx         | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/components/index.ts                 | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/pages/index.ts                      | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/features/dashboard/index.ts                            | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/shared/components/ui/Progress.tsx                      | 2026-01-28          | Tarea 6.1 completada    |
| frontend/src/shared/components/ui/index.ts                          | 2026-01-28          | Tarea 6.1 actualizada   |
| ROADMAP.md                                                          | 2026-01-28          | Tarea 6.1 marcada       |
| ESTADO.md                                                           | 2026-01-28          | Actualizacion sesion    |
| frontend/src/features/auth/components/ChangePasswordModal.tsx       | 2026-01-28          | Tarea 5.10 completada   |
| frontend/src/features/auth/components/index.ts                      | 2026-01-28          | Tarea 5.10 completada   |
| frontend/src/features/auth/hooks/useChangePassword.ts               | 2026-01-28          | Tarea 5.10 completada   |
| frontend/src/features/auth/hooks/index.ts                           | 2026-01-28          | Tarea 5.10 actualizada  |
| ROADMAP.md                                                          | 2026-01-28          | Tarea 5.10 marcada      |
| ESTADO.md                                                           | 2026-01-28          | Actualizacion sesion    |
| frontend/src/features/auth/pages/LoginPage.tsx                      | 2026-01-28          | Tarea 5.9 completada    |
| frontend/src/features/auth/pages/index.ts                           | 2026-01-28          | Tarea 5.9 completada    |
| ROADMAP.md                                                          | 2026-01-28          | Tarea 5.9 marcada       |
| ESTADO.md                                                           | 2026-01-28          | Actualizacion sesion    |
| frontend/src/features/auth/hooks/useAuth.ts                         | 2026-01-27          | Tarea 5.8 completada    |
| frontend/src/features/auth/hooks/useLogin.ts                        | 2026-01-27          | Tarea 5.8 completada    |
| frontend/src/features/auth/hooks/useLogout.ts                       | 2026-01-27          | Tarea 5.8 completada    |
| frontend/src/features/auth/hooks/index.ts                           | 2026-01-27          | Tarea 5.8 completada    |
| ROADMAP.md                                                          | 2026-01-27          | Tareas 5.7-5.8 marcadas |
| ESTADO.md                                                           | 2026-01-27          | Actualizacion sesion    |
| frontend/src/features/auth/services/auth-service.ts                 | 2026-01-27          | Tarea 5.7 completada    |
| frontend/src/shared/components/layout/index.ts                      | 2026-01-27          | Tarea 5.6 completada    |
| frontend/src/shared/components/ui/Button.tsx                        | 2026-01-27          | Tarea 5.5 completada    |
| frontend/src/shared/components/ui/Badge.tsx                         | 2026-01-27          | Tarea 5.5 completada    |
| frontend/src/shared/components/ui/Input.tsx                         | 2026-01-27          | Tarea 5.5 completada    |
| frontend/src/shared/components/ui/Select.tsx                        | 2026-01-27          | Tarea 5.5 completada    |
| frontend/src/shared/components/ui/Spinner.tsx                       | 2026-01-27          | Tarea 5.5 completada    |
| frontend/src/shared/components/ui/Modal.tsx                         | 2026-01-27          | Tarea 5.5 completada    |
| frontend/src/shared/components/ui/index.ts                          | 2026-01-27          | Tarea 5.5 completada    |
| ROADMAP.md                                                          | 2026-01-27          | Tarea 5.5 marcada       |
| ESTADO.md                                                           | 2026-01-27          | Actualizacion sesion    |
| backend/app/routers/rubricas.py                                     | 2026-01-27          | Tarea 4.7 completada    |
| backend/app/services/rubrica_ia_service.py                          | 2026-01-27          | Tarea 4.6 completada    |
| backend/app/routers/**init**.py                                     | 2026-01-27          | Tarea 4.5 completada    |
| backend/app/main.py                                                 | 2026-01-27          | Tarea 4.5 completada    |
| backend/app/services/correccion_service.py                          | 2026-01-27          | Tarea 4.4 completada    |
| backend/app/services/**init**.py                                    | 2026-01-27          | Tarea 4.4 completada    |
| backend/app/repositories/correccion_repository.py                   | 2026-01-27          | Tarea 4.3 completada    |
| backend/app/repositories/**init**.py                                | 2026-01-27          | Tarea 4.3 completada    |
| backend/app/schemas/correccion.py                                   | 2026-01-27          | Tarea 4.2 completada    |
| backend/app/schemas/**init**.py                                     | 2026-01-27          | Tarea 4.2 completada    |
| backend/app/integrations/n8n_client.py                              | 2026-01-27          | Tarea 4.1 completada    |
| backend/app/core/exceptions.py                                      | 2026-01-27          | Tarea 4.1 completada    |
| backend/app/integrations/**init**.py                                | 2026-01-27          | Tarea 4.1 completada    |
| ROADMAP.md                                                          | 2026-01-27          | Tareas 4.1-4.2 marcadas |
| ESTADO.md                                                           | 2026-01-27          | Actualizacion sesion    |

---

_Formato de actualizacion_:

```markdown
### Fecha: YYYY-MM-DD

### Duracion: X min/horas

### Que se hizo:

- Item 1
- Item 2

### Proxima tarea:

- **X.X**: Descripcion

### Problemas encontrados:

- Problema 1 (o "Ninguno")

### Notas:

- Nota relevante
```
