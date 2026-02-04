# Estado del Proyecto - Active-IA

> **IMPORTANTE**: Actualiza este archivo al FINAL de cada sesion de trabajo.

---

## ⚙️ Reglas de Mantenimiento

**Objetivo:** Mantener el archivo en ~100 líneas máximo.

### Qué INCLUIR:
- ✅ Estado actual (fase, tarea, progreso)
- ✅ Progreso por fase (tabla resumen)
- ✅ Última sesión con resumen CONCISO de 2-3 tareas recientes (max 10 líneas por tarea)
- ✅ Bloqueantes actuales (si existen)
- ✅ Decisiones arquitectónicas importantes

### Qué ELIMINAR periódicamente:
- ❌ Detalles de implementación granulares (sub-bullets excesivos)
- ❌ Log de sesiones antiguas (>3 sesiones atrás)
- ❌ Lista de archivos modificados (Git ya lo trackea)
- ❌ Templates o formatos de ejemplo

### Formato de tareas en "Última Sesión":
```
- ✅ **Tarea X.X: Nombre** (COMPLETADA)
  - Archivos principales: ruta1, ruta2
  - Funcionalidades clave: lista breve (3-5 items)
  - Build: exitoso/fallido
  - Notas: solo lo crítico o bloqueante
```

---

## Estado Actual

| Campo                     | Valor                                   |
| ------------------------- | --------------------------------------- |
| **Fase actual**           | Post-deploy - Bugfixes                  |
| **Tarea actual**          | Correcciones ad-hoc post roadmap        |
| **Ultima sesion**         | 2026-02-03                              |
| **Porcentaje completado** | 93%                                     |

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
| 6   | Frontend - Features           | `COMPLETADA` | 20/20 tareas |
| 7   | Testing + Integracion         | `OMITIDA`    | 0/8 tareas   |
| 8   | Docker + Deploy               | `COMPLETADA` | 6/6 tareas   |

**Total**: 95/103 tareas completadas (8 tareas de testing omitidas)

---

## Ultima Sesion

### Fecha: 2026-02-03 (Sesión 26)

### Que se hizo:

- ✅ **Refactorizar RubricasPage.tsx — estilo unificado con UsuariosPage** (ad-hoc)
  - Archivos principales: features/rubricas/pages/RubricasPage.tsx
  - Filtros en card `bg-card border-border` con Input y Select usando props `label`+`options`
  - Estado reemplazado de checkbox a Select (Activas/Todas); texto-resumen de resultados agregado
  - Tabla en card con overflow-hidden; paginación centrada con "Página X de Y"
  - Build: exitoso

- ✅ **Agregar modos PDF y JSON al RubricaEditor + fix de inputs** (ad-hoc)
  - Archivos principales: features/rubricas/components/RubricaEditor.tsx
  - **Bug fix**: `handleUpdateCriterio` usaba copia local sin notificar a RHF. Solucionado con `update()` de useFieldArray
  - Selector de 3 modos (Manual/PDF/JSON) con cards interactivas y iconos
  - Modo PDF: zona de upload con borde punteado, llama a `useGenerarRubricaDesdePDF` (endpoint atómico backend)
  - Modo JSON: textarea + upload de archivo, parsea JSON → `replace()` de useFieldArray → cambia a modo manual para revisión
  - Botones del footer condicionales por modo; campos nombre/numero deshabilitados en modo PDF
  - Build: exitoso

### Problemas encontrados y resueltos:

- RubricaEditor inputs no persistían: useFieldArray.update() es el método correcto para mutar items individuales del array en RHF; la copia local anterior no notificaba al estado
- Modo PDF es operación atómica en backend (POST /rubricas/desde-pdf crea y guarda); modal se cierra al éxito
- Modo JSON es parseo client-side; replace() carga criterios y vuelve a modo manual para editar antes de submit

### Pendiente (no bloqueante):

- RubricaEditor.tsx es 732 LOC (excede guideline de 500); incluye subcomponente CriterioItem + 3 secciones de modo
- MateriaForm.tsx tiene useState no usado (pre-existente)
- ChangePasswordModal.tsx es dead code (pre-existente)

---

## Bloqueantes Actuales

> Ninguno actualmente.

---

## Decisiones Tomadas

| Fecha      | Decision                                    | Contexto                                                                      |
| ---------- | ------------------------------------------- | ----------------------------------------------------------------------------- |
| 2026-01-26 | Copiar docs en lugar de symlink             | Para portabilidad del proyecto                                                |
| 2026-01-26 | Tareas atomicas en ROADMAP                  | Maximo 1-2 archivos por tarea                                                 |
| 2026-01-26 | Usar estructura de 05-ARQUITECTURA-STACK.md | ROADMAP simplificaba, docs/specs tiene estructura completa con api/v1/routers |
| 2026-02-02 | ESTADO.md optimizado a ~100 líneas          | Eliminar detalles granulares, historial de archivos, logs antiguos            |
| 2026-02-02 | Omitir Fase 7 (Testing)                     | Priorizar Docker + Deploy para despliegue rápido, testing opcional            |
| 2026-02-02 | Dos modos de docker-compose                 | docker-compose.yml (BD nube - default), docker-compose.local.yml (BD local)   |
| 2026-02-03 | Dos hooks useChangePassword separados       | auth/ navega a /dashboard (primer login), perfil/ solo toast (modal de perfil). React Query callbacks son aditivos. |
| 2026-02-03 | PDF mode es atómico, JSON mode es client-side | POST /desde-pdf crea+guarda en backend; JSON solo pre-popula form via replace() para revisión manual antes de submit |

---
