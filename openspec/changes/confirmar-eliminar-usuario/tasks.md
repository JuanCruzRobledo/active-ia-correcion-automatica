## 1. Infraestructura de testing React (prerequisito)

- [ ] 1.1 Instalar devDependencies en `frontend/`: `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` (y `@testing-library/user-event` si se usa `userEvent`)
- [ ] 1.2 Agregar bloque `test` a `frontend/vite.config.ts`: `{ globals: true, environment: 'jsdom', setupFiles: './src/test/setup.ts' }`
- [ ] 1.3 Crear `frontend/src/test/setup.ts` que importe `@testing-library/jest-dom`
- [ ] 1.4 Safety net: correr `npm run test` y confirmar que los 3 tests puros existentes (`erroresResumen`, `novedades`, `modoConsolidacionInicial`) siguen verdes bajo jsdom

## 2. Hook `useDeleteUsuario` — onError + invalidación (TDD)

- [ ] 2.1 RED: crear `frontend/src/features/usuarios/hooks/__tests__/useUsuarios.test.tsx` con `renderHook` + `QueryClientProvider`, mockeando `react-hot-toast` (`vi.mock`) y el `usuariosService`. Test: cuando `delete` rechaza, `useDeleteUsuario().mutate(id)` dispara `toast.error` con el mensaje de `getErrorMessage(error)` (debe fallar: el hook aún no tiene `onError`)
- [ ] 2.2 GREEN: agregar `onError: (error) => toast.error(getErrorMessage(error), { duration: 5000 })` a `useDeleteUsuario` en `useUsuarios.ts` (importar `toast` de `react-hot-toast` y `getErrorMessage` de `@/shared/types`). Correr tests → verde
- [ ] 2.3 TRIANGULATE: segundo caso — cuando `delete` resuelve OK, el `onSuccess` invalida las queries de usuarios y NO se llama `toast.error`. Verificar con spy sobre `queryClient.invalidateQueries` o sobre el service
- [ ] 2.4 REFACTOR: limpiar el helper de wrapper (`createWrapper` con QueryClient de test, `retry: false`), sin cambiar comportamiento; tests siguen verdes

## 3. Flujo confirmar→eliminar en `UsuariosPage` (TDD)

- [ ] 3.1 RED: crear `frontend/src/features/usuarios/pages/__tests__/UsuariosPage.test.tsx` con `render` + `QueryClientProvider`, mockeando el service (lista con 1 usuario activo) y `react-hot-toast`. Test A: al hacer click en "Eliminar" del dropdown, aparece el `ConfirmDialog` y el service `delete` NO fue llamado (debe fallar: hoy borra directo)
- [ ] 3.2 GREEN: en `UsuariosPage.tsx` introducir estado `confirmDialog: ConfirmState | null` + `isConfirmLoading`, `handleConfirmAccept` (await `onConfirm` en try/finally, cierra en finally), y `askEliminar(usuario)` que setea el diálogo con `variant: 'destructive'`. Cambiar el ítem "Eliminar" del dropdown de `onClick: () => deleteMutation.mutate(id)` a `onClick: () => askEliminar(usuario)`. Renderizar `<ConfirmDialog>` al final del JSX. Correr test A → verde
- [ ] 3.3 TRIANGULATE test B (confirmar): al pulsar "Eliminar" dentro del diálogo, `runEliminar` llama `deleteMutation.mutateAsync(id)` con el id correcto, muestra `toast.success` y el diálogo se cierra
- [ ] 3.4 TRIANGULATE test C (cancelar): al cerrar el diálogo sin confirmar, el service `delete` NO se llama y el diálogo desaparece
- [ ] 3.5 REFACTOR: extraer textos del diálogo (título/mensaje/confirmLabel) a constantes locales; alinear `ConfirmState` con el tipo usado en `EntregasPage`; tests verdes tras cada paso

## 4. Verificación final

- [ ] 4.1 Correr `npm run test` completo (los 3 previos + hook + página) → todo verde
- [ ] 4.2 Correr `npm run lint` y `npm run typecheck` → sin errores
- [ ] 4.3 Verificación manual en dev: eliminar un usuario pide confirmación, muestra toast de éxito; simular fallo (p. ej. sin permisos) muestra toast de error
