## Context

Fase 5 de `PLAN-MULTI-TENANT-UNIVERSIDADES.md`. Las Fases 0–4 dejaron el backend multi-tenant completo y archivado; el frontend nunca se tocó y hoy está roto contra ese backend.

Estado del cliente hoy (relevado en explore):

- **Stack**: React 19 + React Query 5 + React Router 7 + axios + Tailwind 4. **No hay Zustand ni Context de auth.**
- **Fuente de verdad**: `localStorage` con dos claves, `auth_token` (JWT) y `auth_user` (`UserInfo`). `useAuth()` las lee en `useEffect` y escucha el evento `storage` para sincronizar pestañas.
- **Gating**: `navConfig.ts:70` → `navItems.filter(i => !i.roles || i.roles.includes(rol))`.
- **Superficie del rol**: 31 lecturas de `.rol` en 16 archivos.

Roturas concretas verificadas contra el código:

| # | Archivo | Síntoma |
|---|---|---|
| ① | `auth-service.ts:37` | Destructura `access_token` sin discriminar; con `SeleccionUniversidadRequerida` guarda `undefined` y `useLogin.onSuccess` explota leyendo `data.user.nombre` |
| ② | `navConfig.ts:70` | Con `rol = null` (superadmin) sólo sobrevive el único item sin `roles`: el superadmin ve **un** item de menú |
| ③ | `PerfilPage.tsx:20` | `moodle_host` es campo requerido con validación de URL, pero Fase 3 lo sacó de `MoodleCredentialsUpdate` |
| ④ | `api-client.ts:124` | 409 cae en "El recurso ya existe" y 424 no tiene caso: cae en el genérico |

Hueco de contrato encontrado en explore: **no existe forma de listar universidades**. `UniversidadDisponible` sólo se construye dentro de `authenticate()` y sólo en la rama de 2+ membresías. Por eso este change es full-stack y no sólo frontend.

Gobernanza: **HIGH**. Toca el flujo de autenticación y agrega creación de tenants.

## Goals / Non-Goals

**Goals:**

- Dejar la app funcional contra el backend de Fases 1–4 (las cuatro roturas cerradas).
- Un único punto de verdad reactivo para la universidad activa y el rol.
- Que cambiar de universidad **nunca** deje datos del tenant anterior en pantalla.
- Endpoints de universidades: listado propio (para el selector) y ABM de superadmin.
- Superadmin operativo: modo global por defecto y capacidad de acotarse a una universidad.

**Non-Goals:**

- Eliminar `usuarios.rol` y las columnas `moodle_*` del usuario. Eso es la Fase 6.
- Gestionar membresías (asignar usuarios a universidades) desde la UI. Es un ABM aparte, no entra acá.
- Arreglar `passlib`/`bcrypt`. Es un problema del entorno local, con alcance propio.
- Rediseñar la navegación. Se ajusta el gating, no la estructura.

## Decisions

### D1 — Contexto de tenant sobre `localStorage`, no en reemplazo

**Decisión**: `TenantProvider` mantiene el estado de tenant en React state, **derivado** de la sesión en `localStorage`, que sigue siendo la persistencia. El provider expone `useTenant()` y es el único que escribe la sesión al hacer switch.

**Por qué**: `localStorage` no es reactivo — es exactamente lo que obliga hoy a recargar. Pero tirarlo abajo obligaría a rehacer la persistencia de sesión, que funciona bien. El Context aporta reactividad; `localStorage` aporta durabilidad entre recargas.

**Alternativas descartadas**:
- *Seguir sólo con `localStorage` + reload en cada switch*: dos pestañas en universidades distintas se pisan la misma clave, y el listener de `storage` que hoy sincroniza pestañas pasa a ser el enemigo.
- *Universidad activa en la URL (`/u/:uniId/...`)*: es el modelo más correcto y habilita deep-links por tenant, pero obliga a tocar todas las rutas y todos los links. Desproporcionado para este change. **Queda anotado como evolución posible.**

### D2 — El rol vive en el contexto, no en el usuario

`useTenant().rol` es el rol de la **membresía activa**. Las 31 lecturas de `.rol` migran a `useTenant()`. `UserInfo.rol` pasa a `Rol | null` en tipos para reflejar el contrato real del backend.

**Por qué**: en multi-tenant el rol es propiedad del *contexto*, no de la *persona*. Dejar `user.rol` como fuente invita a que alguien lo lea y obtenga el rol equivocado. El cambio de tipo a `| null` fuerza a `npm run typecheck` a señalar cada lugar que hay que revisar: el compilador es la lista de tareas.

### D3 — El gating de navegación se resuelve en una sola función

Se introduce un único helper de visibilidad —`puedeVer(item, { rol, esSuperadmin })`— usado por `Sidebar` y `BottomNav`. Regla: `esSuperadmin === true` ⇒ visible siempre; si no, la regla actual.

**Por qué**: hoy la regla está inline en `navConfig.ts:70`. Un solo lugar de decisión evita que Sidebar y BottomNav diverjan, que es el patrón que ya usamos en backend con `_acceso_total` (Fase 2).

### D4 — Invalidación total de la caché al cambiar de universidad

Al switchear: `queryClient.clear()`, no `invalidateQueries()` selectivo.

**Por qué**: `invalidateQueries` marca como stale pero **deja los datos anteriores servidos** mientras revalida. Eso significa mostrar datos de la universidad A mientras se piden los de la B. Con `clear()` no hay ventana de exposición. El costo es un flash de loading; es el precio correcto por no filtrar entre tenants.

**Alternativa descartada**: prefijar todas las query keys con `universidadId`. Es más elegante y evita el flash, pero depende de que **cada** hook recuerde incluir el prefijo — un olvido silencioso filtra datos. `clear()` es seguro por defecto.

### D5 — El listado del selector es un endpoint propio, no el perfil

`GET /universidades/mias`, separado de `GET /perfil`.

**Por qué**: el selector se necesita en un momento donde puede no haber universidad activa (superadmin en modo global, o justo después del login). `GET /perfil` monta `get_universidad_activa` desde la Fase 3, que responde 409 sin universidad activa. Meterlo ahí crearía el mismo deadlock que ya analizamos en la Fase 2: el endpoint que te deja elegir universidad no puede exigir una universidad elegida.

**Requisito derivado**: `GET /universidades/mias` monta sólo autenticación, nunca `get_universidad_activa`.

### D6 — Modo global del superadmin = `universidad_activa_id = null`

"Todas las universidades" emite un token sin universidad activa, vía `POST /auth/switch-universidad`.

**Por qué**: es exactamente el estado que el backend ya soporta desde la Fase 4 (`universidad_id=None` ⇒ sin filtro en los repositorios) y desde la Fase 1 (login de superadmin sin membresía). No hace falta nada nuevo del lado del servidor. Hay que verificar en la implementación que `switch-universidad` acepte un `universidad_id` nulo para un superadmin; si no lo acepta, se extiende.

### D7 — El ABM reutiliza el bypass de superadmin existente

Los guards del ABM usan `ctx.es_superadmin`, no un mecanismo nuevo, y `DELETE` es baja lógica (`activa = false`) como toda baja del proyecto (CRUD-002).

### D8 — Orden de implementación: roturas → backend → contexto → ABM

**Por qué**: las roturas ① y ② bloquean la verificación de todo lo demás. Para probar el selector hacen falta un usuario con dos universidades y un superadmin — que son justamente los dos perfiles que hoy no pueden entrar. Arreglarlas primero no es prolijidad, es la única forma de poder probar.

## Risks / Trade-offs

- **Filtración de datos entre tenants al switchear** → `queryClient.clear()` (D4), más un test explícito del escenario "veo materias de A, switcheo a B, no debe quedar nada de A".
- **`rol: Rol | null` rompe la compilación en muchos lugares a la vez** → se toma como red de seguridad, no como accidente: `npm run typecheck` limpio es criterio de aceptación de la Parte 1.
- **No se puede probar un login real end-to-end en local** (`passlib`/`bcrypt` roto) → los tests del flujo de login se hacen con el cliente HTTP mockeado; la verificación manual contra el backend levantado queda pendiente hasta arreglar el entorno. **Se declara explícitamente como limitación, no se simula que está verificado.**
- **El ABM crea tenants: una universidad mal creada es un silo de datos huérfano** → gobernanza HIGH, guard de superadmin y baja lógica; nunca borrado físico.
- **`switch-universidad` puede no aceptar `universidad_id` nulo** → se verifica en la primera tarea de la Parte 3; si no lo acepta, se extiende el endpoint dentro de este change.
- **Dos pestañas en universidades distintas** → sigue sin resolverse del todo: la sesión vive en `localStorage`, que es compartido. El Context reduce el problema pero no lo elimina. Se documenta; la solución real es D1-alternativa (universidad en la URL) y queda fuera de alcance.

## Migration Plan

Sin migraciones de base: la tabla `universidades` existe desde la Fase 0 y no cambia.

Precondiciones de despliegue que este change **no** resuelve y siguen abiertas del plan:

- **OP-1**: cargar `Universidad.moodle_host` de TUPaD en el ambiente destino. Sin eso el resolver de Fase 3 falla con 424, y ahora además el perfil lo va a mostrar vacío con su advertencia.
- **OP-2**: decidir qué ADMIN recibe `es_superadmin = true`. Hoy los 56 usuarios están en `false`, así que **al desplegar este change nadie podría entrar al ABM de universidades**. Debe resolverse antes o junto con el despliegue.

Rollback: revertir el commit. No hay estado persistente nuevo que deshacer.

## Open Questions

- ¿El ABM debería permitir además asignar membresías (usuario ↔ universidad ↔ rol)? Hoy no hay ninguna UI para eso, así que crear una universidad nueva la deja sin usuarios y sólo alcanzable por superadmin. Se propone resolverlo en un change aparte para no inflar éste, pero condiciona cuán útil es el ABM el día uno.
- ¿El superadmin en modo global debería poder *escribir* (crear una materia sin universidad activa), o el modo global es de sólo lectura? El backend hoy responde 400 al crear una materia sin `ctx.universidad_id` (Fase 4), así que de hecho es de sólo lectura para creación. Conviene que la UI lo refleje en vez de dejar que el usuario se coma el 400.
