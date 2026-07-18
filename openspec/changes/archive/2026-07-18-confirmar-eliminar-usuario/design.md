## Context

Hallazgo de auditoría **UI-001** (crítico en UX). En `UsuariosPage.tsx:147-149`, el ítem "Eliminar" del dropdown de acciones ejecuta `deleteMutation.mutate(usuario.id)` de forma directa: no hay confirmación previa y el borrado ocurre con un solo click. El hook `useDeleteUsuario` (`useUsuarios.ts:90-100`) solo define `onSuccess` (invalida queries); **carece de `onError`**, por lo que un fallo del borrado es invisible para el usuario, y tampoco hay toast de éxito.

Es el único CRUD de la app sin `ConfirmDialog` en su borrado. El resto (materias, comisiones, rúbricas, cohortes) ya confirma. El patrón más completo y validado del proyecto es el de **entregas**:
- Hook con `onError` → `toast.error(getErrorMessage(error), { duration: 5000 })` — `useEntregas.ts:340-353` (`useDeleteEntregasMasivo`).
- Página con estado `ConfirmDialog` + `mutateAsync` en try/catch + toast de éxito explícito — `EntregasPage.tsx:122-142` (estado y `handleConfirmAccept`), `473-499` (`runEliminarSeleccionados` + `handleEliminarSeleccionados`), `1417-1431` (render).
- Componente reutilizable `ConfirmDialog` — `shared/components/ui/ConfirmDialog.tsx` (props `isOpen/onClose/onConfirm/title/message/confirmLabel/variant/isLoading`; el consumidor decide cuándo cerrar).
- `getErrorMessage` vive en `shared/types/index.ts:278`. `toast` es `react-hot-toast` (default import).

**Restricción crítica de infraestructura descubierta:** el frontend tiene `vitest` (`npm run test` = `vitest run`) pero `vite.config.ts` **no tiene bloque `test`** (sin `environment: 'jsdom'`, sin `setupFiles`) y **no hay `@testing-library/react`** instalado. Los tres tests existentes (`erroresResumen.test.ts`, `novedades.test.ts`, `modoConsolidacionInicial.test.ts`) son de **funciones puras** en entorno node. Testear un hook de React Query y un flujo de componente requiere primero levantar esa infraestructura.

## Goals / Non-Goals

**Goals:**
- Que borrar un usuario desde la UI exija confirmación explícita en un `ConfirmDialog` destructivo antes de disparar la mutación.
- Que el borrado dé feedback: `toast.success` al completar, `toast.error` con mensaje legible (`getErrorMessage`) al fallar.
- Homologar el borrado de Usuarios al patrón `ConfirmDialog` + hook con `onError` ya usado en el resto de la app.
- Dejar instalada la infraestructura mínima de testing de React (jsdom + Testing Library) para poder cubrir con vitest tanto el hook como el flujo de la página.

**Non-Goals:**
- No se toca el backend, el endpoint de borrado, ni el modelo de datos (sigue siendo soft delete).
- No se cambia el flujo de "Restaurar" ni el resto de acciones del dropdown (Editar, Resetear contraseña).
- No se refactoriza `EntregasPage` ni el `ConfirmDialog` compartido: se consumen como están.
- No se agrega `onError` a los otros CRUDs (materias/comisiones/rúbricas/cohortes) en este change; queda fuera de alcance aunque también les falte.

## Decisions

### D1 — Replicar el patrón de estado `ConfirmState` de EntregasPage en UsuariosPage
Se introduce en `UsuariosPage` un estado `confirmDialog: ConfirmState | null` + `isConfirmLoading`, un `handleConfirmAccept` que hace `await confirmDialog.onConfirm()` dentro de try/finally, y el render condicional de `<ConfirmDialog>` al final del JSX. El ítem "Eliminar" del dropdown pasa de `onClick: () => deleteMutation.mutate(id)` a `onClick: () => askEliminar(usuario)`, donde `askEliminar` setea el `confirmDialog` con `variant: 'destructive'` y `onConfirm: () => runEliminar(usuario.id)`.
- **Por qué:** es el patrón exacto ya validado en producción; minimiza superficie de decisión y mantiene consistencia de UX (mismo look, dark mode, touch targets).
- **Alternativa descartada:** `window.confirm` — no accesible, no respeta tokens/dark mode, ya fue retirado del resto de la app.

### D2 — `runEliminar` usa `mutateAsync` en try/catch con catch vacío; el error lo maneja el hook
`runEliminar(id)` hace `await deleteMutation.mutateAsync(id)` y en éxito `toast.success('Usuario eliminado')`; el `catch {}` queda vacío a propósito porque el `onError` del hook ya muestra el toast de error. `mutateAsync` (no `mutate`) para poder await-ear y cerrar el diálogo recién cuando termina.
- **Por qué:** separa responsabilidades igual que en entregas — el hook posee el feedback de error (reutilizable desde cualquier consumidor), la página posee el feedback de éxito contextual.
- **Alternativa descartada:** poner el `toast.error` en el catch de la página → duplicaría el manejo y dejaría al hook sin feedback para otros consumidores.

### D3 — `useDeleteUsuario` gana `onError` + `onSuccess` con toasts, conservando la invalidación
```ts
onSuccess: () => { queryClient.invalidateQueries({ queryKey: usuariosKeys.all }); toast.success('Usuario eliminado'); }
onError: (error) => { toast.error(getErrorMessage(error), { duration: 5000 }); }
```
- **Decisión de dónde toastear el éxito:** el `toast.success` se pone **en la página** (`runEliminar`), no en el hook, para no duplicarlo si el hook se reusa. El hook mantiene SOLO la invalidación en `onSuccess` y el `toast.error` en `onError`. Esto calca exactamente `useDeleteEntregasMasivo` (hook = invalidar + onError; página = success toast).
- **Nota:** `getErrorMessage` en este repo toma solo `(error)` (no acepta fallback como el de entregas, que usa otro helper). Verificado en `shared/types/index.ts:278`.

### D4 — Levantar infraestructura de testing React con jsdom + @testing-library/react
Se agrega al `vite.config.ts` un bloque `test: { globals: true, environment: 'jsdom', setupFiles: './src/test/setup.ts' }`, un `src/test/setup.ts` con `@testing-library/jest-dom`, y las devDependencies `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`. Los tests del hook usan `renderHook` + `QueryClientProvider`; el del flujo usa `render` + `userEvent`/`fireEvent` sobre `UsuariosPage`, mockeando `react-hot-toast` y el service.
- **Por qué:** sin jsdom + Testing Library es imposible testear el hook (necesita render de React) ni el flujo de confirmación. Es un prerequisito del TDD pedido.
- **Trade-off:** agrega dependencias de dev y un pequeño setup, pero es infra reutilizable por todo el frontend a futuro. `environment: 'jsdom'` es por-config global; los tests puros existentes siguen pasando bajo jsdom sin cambios.
- **Alternativa descartada:** testear solo la lógica pura extraída (ej. un builder del objeto ConfirmState) y saltear el render → no cubriría el bug real (el wiring del onClick y el onError del hook), que es justamente lo que la auditoría marca.

## Risks / Trade-offs

- **[La suite de tests puros hoy corre en node; cambiar a jsdom global podría alterar su entorno]** → jsdom es un superset compatible para esos tests (no dependen de APIs exclusivas de node). Mitigación: correr `npm run test` completo tras configurar y confirmar que los 3 tests previos siguen verdes (safety net del ciclo TDD).
- **[Mockear `react-hot-toast` mal → el test del hook no verifica el toast real]** → mockear el módulo con `vi.mock('react-hot-toast')` exponiendo `success`/`error` como `vi.fn()` y asertar que se llamó con el mensaje esperado. Triangular con un caso de error del service.
- **[Instalar devDeps nuevas requiere `npm install`]** → tarea explícita en tasks.md antes del ciclo RED; sin ellas los tests de componente/hook no compilan.
- **[El `ConfirmDialog` no cierra solo tras onConfirm]** → por diseño del componente (el consumidor cierra). Ya contemplado: `handleConfirmAccept` cierra en el `finally`.

## Migration Plan

No hay migración de datos ni de API. Es un cambio puramente de frontend, desplegable con el build normal del front (`npm run build`). Rollback = revertir el commit; no deja estado persistente. Gobernanza BAJA: mergeable sin gates intermedios si `npm run test` pasa.

## Open Questions

- Ninguna bloqueante. El texto exacto del mensaje/título del diálogo y del `toast.success` es cosmético y puede ajustarse en APPLY (propuesta: título "Eliminar usuario", mensaje "¿Seguro que querés eliminar a este usuario? Podés restaurarlo luego desde el filtro de eliminados.", confirmLabel "Eliminar").
