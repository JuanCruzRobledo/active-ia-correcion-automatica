# Auditoría 04 — Fallas de UI/UX

**Sistema:** Active-IA — Corrección automática de trabajos prácticos
**Dimensión:** 🎨 UI-UX
**Fecha:** 2026-07-12
**Alcance:** `frontend/src` completo (features: entregas, correcciones, rubricas, comisiones, usuarios, materias, perfil, notificaciones, pendientes, por-entregar, materia-dashboard, cron-config, cohortes, tutores-nexo, gestion, dashboard-gestor, auth, dashboard, cierre-cursada + shared). Auditoría estática de código: NO se ejecutó la app; lo que requiere verificación en runtime está marcado como "⚠️ A confirmar".

**Qué está bien (para no repetir ruido):** los estados vacíos están resueltos (`Table`/`ResponsiveTable` traen `emptyMessage` por defecto, las páginas usan `EmptyState`), no hay `fetch`/axios fuera de `services/`, los formularios principales usan React Hook Form + Zod con `isSubmitting` deshabilitando el submit, `Button` con `isLoading` se auto-deshabilita (mata el doble submit en la mayoría de los flujos), y TODOS los `style={{...}}` encontrados son valores dinámicos legítimos (anchos de progreso, posiciones calculadas) — no hay violación de "Tailwind only".

---

## Índice

| ID | Título | Severidad | Archivo |
|----|--------|-----------|---------|
| UI-001 | Eliminar usuario: un click, sin confirmación y sin feedback | 🔴 Crítica | `features/usuarios/pages/UsuariosPage.tsx:148` |
| UI-002 | Guardar rúbrica: fallo silencioso o `alert()` con JSON crudo | 🟠 Alta | `features/rubricas/components/RubricaEditor.tsx:421` |
| UI-003 | Disparar corrida de emails sin manejo de error (unhandled rejection) | 🟠 Alta | `features/notificaciones/pages/NotificacionesPage.tsx:56` |
| UI-004 | Queries secundarias con `isError` ignorado en 7+ páginas (fallos silenciosos) | 🟠 Alta | múltiples (ver ficha) |
| UI-005 | ~31 componentes violan la regla de <200 LOC (hasta 1434) | 🟠 Alta | múltiples (ver ficha) |
| UI-006 | ~50 usos de `any` en el frontend pese a la regla "no `any`" | 🟡 Media | múltiples (ver ficha) |
| UI-007 | Modal: sin focus trap, sin restaurar foco, y el swipe-down cierra siempre | 🟡 Media | `shared/components/ui/Modal.tsx:190` |
| UI-008 | Dropdown de acciones: trigger `<div>` no accesible y menú sin navegación por teclado | 🟡 Media | `shared/components/ui/Dropdown.tsx:214` |
| UI-009 | Comisiones de producción hardcodeadas como default en el envío de emails | 🟡 Media | `features/notificaciones/pages/NotificacionesPage.tsx:53` |
| UI-010 | Input: `id` con `Math.random()` por render y tooltip solo-hover inaccesible | 🟡 Media | `shared/components/ui/Input.tsx:78` |
| UI-011 | Inconsistencia de tono: tuteo y voseo mezclados en toda la app | 🟢 Baja | múltiples (ver ficha) |
| UI-012 | Labels sin asociar (`htmlFor`) en PerfilPage y GestionPage | 🟢 Baja | `features/perfil/pages/PerfilPage.tsx:759` |
| UI-013 | Banner "API Key de Gemini inválida" ignora al proveedor OpenRouter | 🟢 Baja | `features/entregas/pages/EntregasPage.tsx:852` |

**Totales:** 🔴 1 · 🟠 4 · 🟡 5 · 🟢 3 — **13 hallazgos**

---

### [CRÍTICA] Eliminar usuario: un click, sin confirmación y sin feedback

- **ID**: UI-001
- **Ubicación**: `frontend/src/features/usuarios/pages/UsuariosPage.tsx:148`
- **Severidad**: 🔴 Crítica
- **Dimensión**: UI-UX
- **Descripción**: La opción "Eliminar" del dropdown de acciones de un usuario ejecuta `deleteMutation.mutate(usuario.id)` directamente, sin ningún diálogo de confirmación. Además el hook `useDeleteUsuario` (`features/usuarios/hooks/useUsuarios.ts:90-100`) no tiene `onError` ni `onSuccess` con toast: si falla, el usuario no se entera; si funciona, tampoco hay feedback más allá del refetch de la tabla.
- **Evidencia**: `UsuariosPage.tsx:147-149`: `{ label: 'Eliminar', onClick: () => deleteMutation.mutate(usuario.id), icon: <Trash2 .../> }`. No hay ningún `ConfirmDialog` en la página (grep de `ConfirmDialog|confirm` sobre el archivo: cero resultados fuera del import de hooks). Contraste: MateriasPage:408, ComisionesPage:504, RubricasPage:100 y CohortesPage:198 SÍ usan `ConfirmDialog` para el mismo gesto.
- **Impacto**: Un misclick en el menú de acciones desactiva un usuario al instante (es soft delete en backend, pero para el operador el usuario "desaparece" sin aviso). Es LA acción destructiva de la app con menos fricción, y es inconsistente con todas las demás páginas CRUD.
- **Reproducción**: Usuarios → dropdown de acciones de cualquier fila → click en "Eliminar". Desaparece sin preguntar.
- **Fix propuesto**: Reusar el `ConfirmDialog` existente (mismo patrón que MateriasPage/ComisionesPage) + toast de éxito/error en el hook.
- **Esfuerzo estimado**: S

---

### [ALTA] Guardar rúbrica: fallo silencioso o `alert()` con JSON crudo

- **ID**: UI-002
- **Ubicación**: `frontend/src/features/rubricas/components/RubricaEditor.tsx:421-428`
- **Severidad**: 🟠 Alta
- **Dimensión**: UI-UX
- **Descripción**: El catch del submit de la rúbrica solo muestra algo al usuario si existe `error.response.data.detail` — y lo que muestra es un `alert()` nativo con `JSON.stringify(detail, null, 2)`. Si el error es de red, timeout o cualquier cosa sin `detail`, el guardado falla EN SILENCIO TOTAL (solo `console.error`): el modal queda abierto y el usuario no sabe si guardó o no. Además hay otros dos `alert()` nativos en los previews de PDF (líneas 338 y 367), rompiendo el sistema de toasts/diálogos del resto de la app.
- **Evidencia**: `RubricaEditor.tsx:421-428`:
  ```
  } catch (error: any) {
    console.error('❌ Error guardando rúbrica:', error);
    ...
    if (error?.response?.data?.detail) {
      alert(`Error: ${JSON.stringify(error.response.data.detail, null, 2)}`);
    }
  }
  ```
  (sin rama `else` → sin feedback). `alert()` también en :338 y :367.
- **Impacto**: El flujo más complejo de la app (editor de rúbricas de 746 LOC) puede perder el trabajo del usuario sin avisar, o mostrarle un volcado JSON de errores de validación Pydantic ilegible para un docente.
- **Reproducción**: Editar una rúbrica con el backend caído → Guardar → no pasa nada visible. Con un error 422 → alert nativo con JSON.
- **Fix propuesto**: Catch único que siempre notifique (toast/`Alert` del design system), traduciendo `detail` a mensajes legibles; eliminar los tres `alert()`.
- **Esfuerzo estimado**: S

---

### [ALTA] Disparar corrida de emails sin manejo de error (unhandled rejection)

- **ID**: UI-003
- **Ubicación**: `frontend/src/features/notificaciones/pages/NotificacionesPage.tsx:56-62`
- **Severidad**: 🟠 Alta
- **Dimensión**: UI-UX
- **Descripción**: `handleDisparar` hace `await disparar.mutateAsync(...)` sin try/catch, y el hook `useDispararCorrida` (`features/notificaciones/hooks/useNotificaciones.ts:37-53`) no define `onError`. El `QueryClient` global (`app/providers.tsx:4-16`) tampoco tiene handler global de errores de mutación. Resultado: si la corrida (que dispara emails REALES a alumnos y tutores) falla, hay una unhandled promise rejection y CERO feedback en pantalla. Lo mismo aplica a `useSetNotifConfig` (:19-28): tiene toast de éxito pero ningún manejo de fallo al guardar la configuración del cron.
- **Evidencia**: `NotificacionesPage.tsx:60`: `const r = await disparar.mutateAsync({ refrescar, incluirAlumnos, incluirNexos, comisiones });` — sin catch. `useNotificaciones.ts`: `useDispararCorrida` y `useSetNotifConfig` solo tienen `onSuccess`.
- **Impacto**: El operador no puede distinguir "la corrida falló" de "la corrida está tardando". Con emails masivos de por medio, el reflejo natural es reintentar → riesgo de doble envío si el fallo fue parcial. La config del cron puede "guardarse" (en apariencia) sin haberse guardado.
- **Reproducción**: ⚠️ A confirmar en runtime — Notificaciones → "Disparar corrida" con el backend devolviendo 500: el botón deja de girar y no aparece nada.
- **Fix propuesto**: `onError` con toast descriptivo en ambas mutaciones (o handler global en el QueryClient para mutaciones sin `onError`).
- **Esfuerzo estimado**: S

---

### [ALTA] Queries secundarias con `isError` ignorado en 7+ páginas (fallos silenciosos)

- **ID**: UI-004
- **Ubicación**: múltiples (detalle en evidencia)
- **Severidad**: 🟠 Alta
- **Dimensión**: UI-UX
- **Descripción**: Las páginas manejan bien el loading/error de SU query principal (patrón `if (isLoading)... if (error)...` presente en Usuarios, Materias, Comisiones, Rubricas, Pendientes, PorEntregar, Cohortes, TutoresNexo), pero las queries secundarias — las que alimentan selects, formularios de config e historiales — descartan el error sistemáticamente: solo se destructura `data` + `isLoading`. Si fallan, la UI degrada a dropdowns vacíos o secciones que directamente desaparecen, sin ningún mensaje.
- **Evidencia** (todas con `isError`/`error` sin consumir):
  - `features/entregas/pages/EntregasPage.tsx:150` (`useComisiones`) y `:154` (`useRubricas`) → si fallan, los selects de comisión/rúbrica quedan vacíos y la página entera es inusable sin explicación.
  - `features/notificaciones/pages/NotificacionesPage.tsx:34-42` (`useNotifConfig`, `useUsuarios`, `useHistorialNotif`) → el form de config se renderiza solo `{config && ...}` (línea 92): si la query falla, la sección de configuración del cron DESAPARECE en silencio.
  - `features/cron-config/pages/CronConfigPage.tsx:24-32` (`useCronConfig`, `useUsuarios`, `useMateriasConfiguradas`).
  - `features/materia-dashboard/pages/MateriaDashboardConfigPage.tsx:33-34` (`useDashboardConfig`, `useUnidades`).
  - `features/dashboard-gestor/pages/DashboardGestorPage.tsx:23` (`useArbol` — si falla, la página renderiza con "Elegí una cohorte" y un select vacío) y `:28` (`useAvance`).
  - `features/gestion/pages/GestionPage.tsx:111` (`cursosQuery` — solo `isLoading`; el error del select de cursos no se muestra, a diferencia de `filtrosQuery` que sí lo maneja en :160).
- **Impacto**: El usuario ve pantallas "vacías pero sanas" cuando en realidad hubo un fallo de red/backend. Es el peor tipo de error UX: indistinguible de "no hay datos". Viola directamente la regla dura del proyecto "SIEMPRE manejar loading y error".
- **Reproducción**: ⚠️ A confirmar en runtime — bloquear `/api/comisiones` y entrar a Entregas: selects vacíos, ningún error.
- **Fix propuesto**: Patrón uniforme para queries secundarias: mínimo un `Alert` inline con retry cuando `isError` (los selects pueden mostrar "No se pudieron cargar las opciones"). Considerar un componente `QueryBoundary` compartido.
- **Esfuerzo estimado**: M

---

### [ALTA] ~31 componentes violan la regla de <200 LOC (hasta 1434)

- **ID**: UI-005
- **Ubicación**: `frontend/src` (lista completa abajo)
- **Severidad**: 🟠 Alta
- **Dimensión**: UI-UX
- **Descripción**: La regla dura del proyecto es "Components < 200 LOC". Hoy 31 archivos `.tsx` la violan, con el caso extremo de `EntregasPage.tsx` en 1434 LOC (7x el límite). Se confirma la lista sospechada y se agregan los restantes. Hallazgo agregado — una sola ficha, como corresponde.
- **Evidencia** (LOC medidas con `wc -l`, orden descendente):
  | LOC | Archivo |
  |-----|---------|
  | 1434 | `features/entregas/pages/EntregasPage.tsx` |
  | 837 | `features/perfil/pages/PerfilPage.tsx` |
  | 828 | `features/correcciones/components/CorreccionViewEditModal.tsx` |
  | 746 | `features/rubricas/components/RubricaEditor.tsx` |
  | 671 | `features/rubricas/pages/RubricasPage.tsx` |
  | 664 | `features/entregas/components/CargaEntregaModal.tsx` |
  | 516 | `features/comisiones/pages/ComisionesPage.tsx` |
  | 486 | `features/correcciones/components/CorreccionDetailModal.tsx` |
  | 436 | `features/usuarios/pages/UsuariosPage.tsx` |
  | 416 | `features/materias/pages/MateriasPage.tsx` |
  | 369 | `features/rubricas/components/RubricaManualMode.tsx` |
  | 365 | `shared/components/ui/MultiSelect.tsx` |
  | 349 | `shared/content/helpContent.tsx` |
  | 326 | `shared/components/ui/Modal.tsx` |
  | 322 | `features/entregas/components/EntregaViewModal.tsx` |
  | 321 | `features/materia-dashboard/components/ExamenesEditor.tsx` |
  | 304 | `features/comisiones/components/ComisionForm.tsx` |
  | 288 | `features/notificaciones/pages/NotificacionesPage.tsx` |
  | 264 | `features/pendientes/components/ImportarButton.tsx` |
  | 264 | `features/materia-dashboard/pages/MateriaDashboardConfigPage.tsx` |
  | 259 | `features/usuarios/components/UsuarioForm.tsx` |
  | 253 | `features/materia-dashboard/components/UnidadComponentesEditor.tsx` |
  | 227 | `shared/components/ui/Dropdown.tsx` |
  | 223 | `shared/components/layout/Sheet.tsx` |
  | 221 | `features/materias/components/MateriaForm.tsx` |
  | 216 | `features/cron-config/pages/CronConfigPage.tsx` |
  | 210 | `features/por-entregar/components/EntregarTodoButton.tsx` |
  | 210 | `features/cohortes/pages/CohortesPage.tsx` |
  | 208 | `features/materia-dashboard/components/ConfigForm.tsx` |
  | 204 | `features/tutores-nexo/pages/TutoresNexoPage.tsx` |
  | 202 | `features/gestion/components/FiltrosGestionForm.tsx` |
  | (200) | `features/gestion/pages/GestionPage.tsx` — borde exacto del límite |
- **Impacto**: No es solo estética: `EntregasPage` concentra 5 queries, 8+ mutaciones, polling, selección masiva, descarga de PDFs y export Excel en un solo componente — el costo de cada bug de UI reportado en esta auditoría se multiplica porque todo vive en el mismo archivo. Las páginas monstruo son también donde encontramos los `catch (e: any)` y los errores silenciosos.
- **Reproducción**: `wc -l` sobre `frontend/src/**/*.tsx`.
- **Fix propuesto**: Descomposición progresiva priorizando el top 6 (>500 LOC): extraer toolbar de acciones masivas, filtros y modales de `EntregasPage`; separar secciones de `PerfilPage` en componentes por card. Agregar regla ESLint `max-lines` para frenar el crecimiento.
- **Esfuerzo estimado**: L

---

### [MEDIA] ~50 usos de `any` en el frontend pese a la regla "no `any`"

- **ID**: UI-006
- **Ubicación**: múltiples (detalle en evidencia)
- **Severidad**: 🟡 Media
- **Dimensión**: UI-UX
- **Descripción**: La regla dura es "no `any`". Grep de `: any|as any|<any>|any[]` arroja ~50 ocurrencias reales concentradas en el feature de rúbricas, el modal de carga de entregas y catches de EntregasPage.
- **Evidencia** (principales clusters):
  - Rúbricas — props de formulario sin tipar: `Control<any>`, `UseFormRegister<any>`, `FieldErrors<any>` en `features/rubricas/components/CondicionesEditor.tsx:8-10`, `PenalizacionesEditor.tsx:8-10`, `RubricaGeneralInfo.tsx:9-12`, `RubricaManualMode.tsx:22-37`; servicios con `Promise<any>` y `criterios: any[]` en `features/rubricas/services/rubricas-service.ts:103-205` y `hooks/useRubricas.ts:207-229`.
  - `features/entregas/components/CargaEntregaModal.tsx:389-471`: cinco `(errors as any).campo?.message` — el schema condicional de Zod se resolvió casteando en vez de discriminando el tipo, o sea que los errores de validación del form están fuera del type-checking.
  - `features/entregas/pages/EntregasPage.tsx:556,592,612`: `catch (e: any)`.
  - `shared/components/ui/Table.tsx:84`: `(item as any)[column.key]`.
  - `features/pendientes/pages/PendientesPage.tsx:27-28`: `(error as any).response?.status`.
- **Impacto**: En los formularios de rúbricas (el editor más complejo de la app) TypeScript no valida nada de los nombres de campos ni de los mensajes de error: un typo en un `register("criterios.X...")` compila y falla en runtime como validación que nunca aparece.
- **Fix propuesto**: Tipar los editores de rúbrica con el tipo del form (`Control<RubricaFormData>`), discriminar el schema de CargaEntregaModal con union types de Zod, y usar `isAxiosError` como type guard en los catches.
- **Esfuerzo estimado**: M

---

### [MEDIA] Modal: sin focus trap, sin restaurar foco, y el swipe-down cierra siempre

- **ID**: UI-007
- **Ubicación**: `frontend/src/shared/components/ui/Modal.tsx:190-192, 207-217`
- **Severidad**: 🟡 Media
- **Dimensión**: UI-UX
- **Descripción**: El Modal compartido tiene buena base (role="dialog", aria-modal, aria-labelledby, cierre con Escape, foco inicial al panel en :190-192, X con aria-label). Pero: (1) NO hay focus trap — con Tab el foco se escapa a la página de fondo, que sigue en el DOM detrás del backdrop; (2) al cerrar, el foco no vuelve al elemento que abrió el modal (queda en `document.body`); (3) el swipe-down del drag handle mobile (:207-217) llama `onClose()` incondicionalmente — ignora la intención de `disableBackdropClose` (default `true`), así que un formulario largo (CargaEntregaModal, RubricaEditor, 664-746 LOC de campos) se puede cerrar con un gesto accidental perdiendo todo lo tipeado, exactamente lo que `disableBackdropClose` intenta prevenir en desktop.
- **Evidencia**: `Modal.tsx:211-213`: `const shouldClose = dragY > SWIPE_CLOSE_THRESHOLD; ... if (shouldClose) onClose();` — sin chequear ninguna prop de protección. Ausencia de manejo de `Tab`/`focusin` en todo el archivo. Sin ref al elemento previamente enfocado.
- **Impacto**: Usuarios de teclado/lector de pantalla pueden tabular hacia contenido invisible detrás del modal (falla WCAG 2.1 — 2.4.3 Focus Order). En mobile, gesto accidental = pérdida de datos del formulario sin confirmación.
- **Reproducción**: ⚠️ A confirmar en runtime — abrir cualquier modal, Tab repetido: el foco sale del diálogo. En mobile, arrastrar el handle >90px con un form a medio llenar.
- **Fix propuesto**: Focus trap (loop de Tab dentro del panel) + guardar/restaurar `document.activeElement`; que el swipe-close respete `disableBackdropClose` o pida confirmación si el form está dirty.
- **Esfuerzo estimado**: M

---

### [MEDIA] Dropdown de acciones: trigger `<div>` no accesible y menú sin navegación por teclado

- **ID**: UI-008
- **Ubicación**: `frontend/src/shared/components/ui/Dropdown.tsx:214-222`
- **Severidad**: 🟡 Media
- **Dimensión**: UI-UX
- **Descripción**: El componente que renderiza el menú de acciones de TODAS las tablas (editar/eliminar/corregir/etc.) tiene el `onClick`, `aria-haspopup="menu"` y `aria-expanded` puestos sobre un `<div>` wrapper, no sobre un elemento interactivo. Si el `trigger` que se le pasa es un botón real funciona por bubbling, pero los atributos ARIA quedan en el div y el lector de pantalla que enfoca el botón interno no anuncia que abre un menú ni su estado. Además el menú `role="menu"` no implementa navegación con flechas ni `role="menuitem"` (solo cierra con Escape, :125-132).
- **Evidencia**: `Dropdown.tsx:214-222`:
  ```
  <div ref={triggerRef} className={...} onClick={() => setIsOpen(!isOpen)}
       aria-haspopup="menu" aria-expanded={isOpen}>
    {trigger}
  </div>
  ```
- **Impacto**: El patrón ARIA "menu" queda a medias: anuncia semántica de menú pero no cumple su contrato de teclado (flechas, Home/End, foco al primer ítem al abrir). Afecta cada fila de cada tabla CRUD de la app.
- **Fix propuesto**: Mover `aria-*` y el handler al elemento del trigger (cloneElement o render-prop), foco al primer ítem al abrir, flechas arriba/abajo entre ítems. Alternativa pragmática: usar `role="dialog"`-less popover simple (sin `role="menu"`) si no se va a cumplir el contrato de teclado.
- **Esfuerzo estimado**: M

---

### [MEDIA] Comisiones de producción hardcodeadas como default en el envío de emails

- **ID**: UI-009
- **Ubicación**: `frontend/src/features/notificaciones/pages/NotificacionesPage.tsx:53`
- **Severidad**: 🟡 Media
- **Dimensión**: UI-UX
- **Descripción**: El input de "comisiones objetivo" de la corrida de notificaciones viene pre-cargado con valores concretos de producción: `useState('7:1, 7:2, 7:3, 9:7')`. El comentario admite que es una "fase de prueba", pero son identificadores reales quemados en el código de la UI.
- **Evidencia**: `NotificacionesPage.tsx:53`: `const [comisionesText, setComisionesText] = useState('7:1, 7:2, 7:3, 9:7');`
- **Impacto**: Un operador que entra y toca "Disparar corrida" sin leer manda emails a esas cuatro comisiones específicas por defecto. Cuando la fase de prueba termine, alguien tiene que acordarse de tocar código de UI para cambiar el alcance del envío. Combinado con UI-003 (fallo silencioso), este flujo de envío masivo es el más frágil de la app.
- **Fix propuesto**: Default vacío + placeholder con el formato esperado; si se necesita un preset, que venga de la config del backend (ya existe `useNotifConfig`).
- **Esfuerzo estimado**: S

---

### [MEDIA] Input: `id` con `Math.random()` por render y tooltip solo-hover inaccesible

- **ID**: UI-010
- **Ubicación**: `frontend/src/shared/components/ui/Input.tsx:78, 92-105`
- **Severidad**: 🟡 Media
- **Dimensión**: UI-UX
- **Descripción**: Dos problemas en el componente de input compartido (usado en toda la app): (1) `const inputId = id || \`input-${Math.random()...}\`` se ejecuta en CADA render — el `id`, `htmlFor` y `aria-describedby` cambian en cada re-render del form (cada tecleo en RHF-watch o cada setState del padre). La asociación label↔input se mantiene dentro del mismo render, pero los ids inestables rompen password managers/autofill, testing por selector y cualquier referencia externa; React ofrece `useId` exactamente para esto. (2) El tooltip de ayuda (ícono Info) solo aparece con `group-hover:` — no es enfocable por teclado ni visible para usuarios táctiles sin hover, y el `role="tooltip"` está aplicado al contenedor del ícono (el rol corresponde al popup, no al trigger).
- **Evidencia**: `Input.tsx:78`: `const inputId = id || \`input-${Math.random().toString(36).substr(2, 9)}\`;` (sin memoización). `:92-105`: `<div className="group relative" role="tooltip" aria-label={tooltip}>` + `hidden group-hover:block`.
- **Impacto**: Ayuda contextual invisible para teclado y mobile (los tooltips se usan en forms de rúbricas y perfil); ids no determinísticos en todos los formularios.
- **Fix propuesto**: `useId()` de React para el fallback del id; tooltip activable por foco (`focus-within`) con el trigger como `<button>` y `aria-describedby` hacia el popup.
- **Esfuerzo estimado**: S

---

### [BAJA] Inconsistencia de tono: tuteo y voseo mezclados en toda la app

- **ID**: UI-011
- **Ubicación**: múltiples (detalle en evidencia)
- **Severidad**: 🟢 Baja
- **Dimensión**: UI-UX
- **Descripción**: La mitad de la app le habla al usuario de "tú" y la otra mitad de "vos", a veces en la misma pantalla. Los features viejos (auth, materias, comisiones, usuarios, entregas, rubricas) usan tuteo neutro; los nuevos (gestión, dashboard-gestor, notificaciones, perfil, cron-config, cierre-cursada) usan voseo rioplatense.
- **Evidencia**: Tuteo: `LoginPage.tsx:55` ("Ingresa tu usuario"), `ChangePasswordPage.tsx:163` ("Intenta nuevamente"), `EntregasPage.tsx:941` ("Selecciona una comisión"), `ComisionForm.tsx:27` ("Selecciona una materia"). Voseo: `GestionPage.tsx:120` ("Elegí un curso…"), `NotificacionesPage.tsx:100` ("Enviá un email de prueba... mirá cómo se ven"), `PerfilPage.tsx:80` ("Ingresá un email válido... dejalo vacío"), `DashboardGestorPage.tsx:35` ("Elegí una cohorte"). Caso mixto en la misma página: `EntregasPage.tsx:855` ("generá una nueva... actualizala") vs `:941` ("Selecciona una comisión").
- **Impacto**: Percepción de producto descuidado; para una plataforma institucional (TUD) conviene una voz única.
- **Fix propuesto**: Decidir el tono (voseo, dado el público) y hacer una pasada de textos; opcionalmente centralizar strings de UI para prevenir regresiones.
- **Esfuerzo estimado**: M

---

### [BAJA] Labels sin asociar (`htmlFor`) en PerfilPage y GestionPage

- **ID**: UI-012
- **Ubicación**: `frontend/src/features/perfil/pages/PerfilPage.tsx:759` (y sección de contraseña completa), `frontend/src/features/gestion/pages/GestionPage.tsx:110`
- **Severidad**: 🟢 Baja
- **Dimensión**: UI-UX
- **Descripción**: El componente `Input` compartido asocia label↔input correctamente vía su prop `label`, pero en algunos lugares se escriben `<label>` manuales sin `htmlFor` seguidos del control: la sección "Cambiar contraseña" de PerfilPage usa `<label className="block...">Confirmar nueva contraseña</label>` + `<Input>` sin prop `label` ni `id` (patrón repetido para los tres campos de contraseña), y GestionPage:110 tiene `<label>Curso</label>` + `<select>` nativo sin asociación. De paso: esa misma sección de contraseña de PerfilPage valida a mano con `useState`/`passwordError` en vez de RHF+Zod (regla del proyecto), a diferencia del form Moodle de la misma página que sí usa RHF.
- **Evidencia**: `PerfilPage.tsx:759-761` (label sin htmlFor) y `:110-116` (estado manual de password); `GestionPage.tsx:110-120`.
- **Impacto**: Click en el label no enfoca el campo; lectores de pantalla anuncian el input sin nombre. Menor porque son pocos casos y el resto de la app usa el componente correcto.
- **Fix propuesto**: Usar la prop `label` del `Input`/`Select` compartido en esos casos; migrar la sección de contraseña a RHF+Zod como el resto.
- **Esfuerzo estimado**: S

---

### [BAJA] Banner "API Key de Gemini inválida" ignora al proveedor OpenRouter

- **ID**: UI-013
- **Ubicación**: `frontend/src/features/entregas/pages/EntregasPage.tsx:851-866`
- **Severidad**: 🟢 Baja
- **Dimensión**: UI-UX
- **Descripción**: El banner de advertencia de Entregas se muestra con `profile && !profile.gemini_api_key_valid`, pero PerfilPage (:130-135) maneja dos proveedores de corrección (`gemini` | `openrouter`) con keys independientes (`openrouter_api_key_valid`). Un usuario cuyo proveedor activo es OpenRouter con key válida vería igualmente el warning "API Key de Gemini inválida" si su key de Gemini (que no usa) está vencida — y a la inversa, no vería warning si su key de OpenRouter está mal.
- **Evidencia**: `EntregasPage.tsx:852`: `{profile && !profile.gemini_api_key_valid && (<Alert variant="warning" title="⚠️ API Key de Gemini inválida">`. Contraste con `PerfilPage.tsx:131-135`: `const keyValid = isOpenRouter ? profile.openrouter_api_key_valid : ...`.
- **Impacto**: Warning falso positivo/negativo según el proveedor configurado. ⚠️ A confirmar en runtime: depende de si el backend marca `gemini_api_key_valid=true` cuando el proveedor activo es OpenRouter.
- **Fix propuesto**: Que el banner evalúe la key del proveedor activo (misma lógica `keyValid` de PerfilPage, extraíble a un hook compartido) y adapte el texto.
- **Esfuerzo estimado**: S
