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

### Fecha: 2026-02-03 (Sesión 25)

### Que se hizo:

- ✅ **ChangePasswordPage: Página /change-password funcional** (ad-hoc, fuera de ROADMAP)
  - Archivos principales: features/auth/pages/ChangePasswordPage.tsx (nuevo), app/router.tsx, features/auth/pages/index.ts, features/perfil/hooks/usePerfil.ts, features/perfil/pages/PerfilPage.tsx
  - Creada página standalone con guard (redirige a /login si no autenticado, a /dashboard si primer_login=false)
  - Ruta /change-password al mismo nivel que /login (fuera de AppLayout, sin sidebar)
  - Validación client-side: contraseña actual requerida, nueva ≥8 chars + al menos 1 número, confirmación debe coincidir, nueva ≠ actual
  - Build: exitoso (solo error pre-existente en MateriaForm.tsx useState no usado)

- 🔧 **Refactor de hooks useChangePassword**
  - Removido duplicado muerto de useAuth.ts (exports inalterados por barrel index)
  - Dos versiones intencionales: auth/hooks/useChangePassword.ts (navega a /dashboard, para primer login) y perfil/hooks/usePerfil.ts::useChangePassword (solo toast, para modal de perfil)
  - PerfilPage actualizado para importar de usePerfil en lugar de useAuth

### Problemas encontrados y resueltos:

- PerfilPage importaba useChangePassword de useAuth — roto al eliminar duplicado. Solucion: agregar hook sin navegacion a usePerfil.ts
- React Query callbacks aditivos: hook-level onSuccess + inline onSuccess ambos disparan. Motivo de tener dos versiones del hook separadas por contexto.

### Pendiente (no bloqueante):

- MateriaForm.tsx tiene useState no usado (error pre-existente, no relacionado)
- ChangePasswordModal.tsx existe pero no se renderiza en ningún lugar (dead code)

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

---
