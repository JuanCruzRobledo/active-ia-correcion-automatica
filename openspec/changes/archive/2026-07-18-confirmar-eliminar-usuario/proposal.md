## Why

El botón "Eliminar" del CRUD de Usuarios (`UsuariosPage.tsx`) dispara el borrado del usuario de forma **directa**, sin diálogo de confirmación: un click accidental en el dropdown de acciones elimina (soft delete) al usuario sin vuelta atrás inmediata en la UI. Además, `useDeleteUsuario` **no tiene `onError`**, así que si el borrado falla el usuario no recibe ningún feedback, y tampoco hay toast de éxito. Es el ÚNICO CRUD de la app sin `ConfirmDialog` en su acción de borrado (materias, comisiones, rúbricas y cohortes ya lo usan). Hallazgo de auditoría UI-001, crítico en UX.

## What Changes

- Agregar `onError` a `useDeleteUsuario` que muestre `toast.error` con `getErrorMessage(error)`, y `onSuccess` con un `toast.success` explícito (además de la invalidación de queries que ya existe).
- Reemplazar en `UsuariosPage.tsx` el `onClick: () => deleteMutation.mutate(usuario.id)` directo (ítem "Eliminar" del dropdown) por un flujo que abra un `ConfirmDialog` (`variant="destructive"`) y solo dispare la mutación (`mutateAsync` dentro de try/catch) al confirmar, replicando el patrón validado en `EntregasPage.tsx`.
- Añadir la infraestructura de testing de React que hoy falta en el frontend (entorno `jsdom` + `@testing-library/react` + setup de matchers), necesaria para poder testear hooks y componentes con vitest. Hoy solo corren tests de funciones puras.

## Capabilities

### New Capabilities
- `usuarios-eliminacion-segura`: comportamiento requerido del borrado de un usuario desde la UI de administración: confirmación explícita previa (diálogo destructivo), feedback de éxito, y feedback de error cuando la operación de borrado falla.

### Modified Capabilities
<!-- No hay specs de capabilities existentes en openspec/specs/ que cubran usuarios; se introduce una capability nueva. -->

## Impact

- **Frontend (único afectado):**
  - `frontend/src/features/usuarios/hooks/useUsuarios.ts` — `useDeleteUsuario` gana `onError` + `onSuccess` con toasts.
  - `frontend/src/features/usuarios/pages/UsuariosPage.tsx` — estado de `ConfirmDialog`, handlers de confirmar/cancelar, render del diálogo; el ítem "Eliminar" del dropdown ahora abre el diálogo.
  - `frontend/vite.config.ts` (+ posible `src/test/setup.ts`, `package.json` devDependencies) — infraestructura de testing React (jsdom + Testing Library).
- **Sin cambios de backend, API, base de datos ni contratos.** El endpoint de borrado no cambia.
- **Gobernanza: BAJA.** UI CRUD simple, patrón ya validado en el resto del proyecto. Esfuerzo estimado **S**. En la fase de APPLY el change puede implementarse y mergearse con autonomía completa, sin gates de aprobación intermedios, siempre que el ciclo TDD con vitest (`npm run test`) pase.
