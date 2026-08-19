## Context

Estado verificado en el código al 2026-08-19:

- La autenticación es JWT (`app/core/dependencies.py:60` `get_current_user`), con expiración configurable por `ACCESS_TOKEN_EXPIRE_DAYS` (default 7).
- **El rol no vive en el usuario: vive en la membresía de universidad.** `UsuarioUniversidad` (`app/models/usuario_universidad.py`) tiene `usuario_id`, `universidad_id`, `rol` y `activo`. `ContextoUniversidad` (`dependencies.py:232`) es lo que construye `get_universidad_activa` (L247) y lo que consumen todas las verificaciones de `app/core/permissions.py`.
- Los guards son funciones puras sobre el contexto: `require_admin`, `require_coordinador_or_admin`, `require_tutor`, etc. (L37-277), más verificaciones de pertenencia asíncronas: `verificar_acceso_materia` (L317), `verificar_acceso_rubrica` (L418), `verificar_acceso_comision` (L438).
- Cada usuario guarda su propia clave de proveedor de IA cifrada con Fernet: `gemini_api_key_encrypted`, `openrouter_api_key_encrypted` (`app/models/usuario.py:52-63`). La corrección usa la clave del usuario que la dispara.
- `Usuario.es_superadmin` existe como bandera global, y `_acceso_total` (`permissions.py:21`) la contempla.

**El dato de diseño más importante**: como todos los guards consumen `ContextoUniversidad` y no el `Usuario`, una identidad de máquina que produzca un contexto compatible **hereda todo el sistema de permisos sin reescribirlo**. Ese es el punto de inserción.

Governance: **🔴 CRÍTICA** (autenticación y autorización). Análisis y propuesta; ninguna línea de código sin aprobación humana explícita.

## Goals / Non-Goals

**Goals**

- Una identidad de máquina revocable sola, sin credenciales de persona en manos de un sistema.
- Alcance acotado a materias concretas, no a un rol global.
- Auditoría que distinga una acción de máquina de una acción humana.
- Cero relajación de los permisos humanos existentes.

**Non-Goals**

- No se implementa OAuth2 client credentials ni un servidor de autorización. Es desproporcionado para un consumidor conocido.
- No se cambia el mecanismo de login de los usuarios humanos.
- No se agrega ningún rol nuevo al enumerado de roles.
- No se relaja el 403 de lectura de criterios de rúbrica para el rol tutor.

## Decisions

### D1. Credencial opaca de larga duración, no un JWT

La credencial es una cadena aleatoria de alta entropía con un prefijo identificable, presentada en un encabezado portador.

Rationale: un JWT de larga duración no se puede revocar sin una lista de revocación, que es infraestructura nueva. Una credencial opaca se revoca poniendo un booleano en `false` — la validación consulta la base en cada petición de todos modos, porque necesita el alcance.

Alternativa descartada: JWT con expiración larga. Menos consultas a la base, pero la revocación exige una lista de revocación o rotar la clave de firma, que afecta a todos los usuarios.

**Costo aceptado**: una consulta a la base por petición autenticada por servicio. Es un consumidor con volumen bajo (publicación de TPs y correcciones de a una), así que no es un problema de rendimiento.

### D2. La credencial se almacena hasheada y se muestra una sola vez

Se persiste el hash de la credencial más un prefijo corto en claro, que sirve para identificarla en un listado sin revelarla. **La credencial completa se devuelve únicamente en la respuesta del alta o de la rotación.**

Rationale: es el mismo razonamiento por el que las contraseñas se hashean. Una credencial recuperable es una credencial que un compromiso de base de datos entrega en claro. El proyecto ya distingue "cifrado reversible" (las claves de IA, que hay que poder usar) de "hash" (las contraseñas, que solo hay que verificar): esta cae del lado del hash.

**Rotación en vez de recuperación**: si el cliente pierde la credencial, se genera una nueva y se invalida la anterior. No hay "mostrármela de nuevo".

### D3. El alcance es por materia, no por rol

La cuenta de servicio tiene una lista explícita de materias sobre las que puede operar y una lista explícita de permisos (por ejemplo, escribir trabajos prácticos, disparar correcciones). Fuera de eso, 403.

Rationale: darle rol coordinador le daría acceso a **todas** las materias que ese rol alcanza, incluidas las que no tienen nada que ver con el piloto. Un consumidor automatizado no necesita generalidad; necesita exactamente lo que necesita.

Y un incidente acotado es un incidente acotado: si la credencial se filtra, el alcance del daño está escrito en la fila.

### D4. Punto de inserción: un contexto compatible con `ContextoUniversidad`

La resolución de la credencial produce un contexto que las verificaciones existentes de `permissions.py` puedan consumir, con su `universidad_id` y su capacidad de responder a las verificaciones de pertenencia a materia.

Rationale: es lo que hace que este change **no reescriba el sistema de permisos**. Todas las reglas actuales siguen valiendo tal como están escritas, y el actor de servicio simplemente no satisface las que no le corresponden.

**Regla dura**: un actor de servicio NO satisface `require_admin` ni ninguna verificación de rol humano. Sus capacidades salen de su lista de permisos, no de un rol. Esto hay que verificarlo con tests explícitos, porque es justo el lugar donde un atajo de implementación abriría un agujero.

### D5. Clave de IA propia, cifrada con el mecanismo existente

La cuenta de servicio guarda su propia clave de proveedor de IA, cifrada con el mismo Fernet que usan los usuarios.

Rationale: (a) las correcciones automatizadas no deben consumir la cuota de un tutor; (b) el costo del piloto queda separado y medible; (c) si la clave del piloto se agota, no deja a ningún humano sin poder corregir.

### D6. Expiración obligatoria

Toda cuenta de servicio tiene fecha de expiración. Una credencial vencida deja de autenticar aunque la cuenta esté activa.

Rationale: una credencial de máquina sin vencimiento sobrevive al proyecto que la creó. El piloto tiene una duración conocida; la credencial debería vencer con él y renovarse a propósito.

### D7. Auditoría con actor de servicio

Toda acción de una cuenta de servicio queda registrada como tal, distinguible de una acción humana. La cuenta registra además su marca de último uso, que hace visible una credencial olvidada y activa.

Rationale: sin esto, la auditoría del proyecto pierde exactamente la distinción que importa cuando algo sale mal — si lo hizo una persona o un sistema.

## Risks / Trade-offs

- **Es una superficie de autenticación nueva.** Una credencial mal validada abre la API entera. Mitigación: gobernanza crítica con revisión humana del diseño y del diff; comparación en tiempo constante; suite de tests negativos (credencial inválida, vencida, revocada, de otra universidad, fuera de alcance) antes de cualquier test positivo.
- **La credencial va en un encabezado en cada petición.** Si se loguea, se filtra. Mitigación: los logs no deben registrar el encabezado; verificarlo explícitamente, incluidos los logs de error y las trazas.
- **El alcance por materia agrega una consulta más por petición.** Aceptado en D1.
- **La cuenta de servicio se puede olvidar activa.** Mitigación: expiración obligatoria de D6 y marca de último uso de D7.
- **Riesgo de atajo**: implementar el actor de servicio dándole un rol humano "por debajo" para no tocar los guards. Sería más rápido y rompería D3 y D4 en silencio. Los tests de D4 existen para impedirlo.

## Migration Plan

Migración aditiva: la tabla de cuentas de servicio y la de asignación de materias. Nada existente se modifica.

Orden: (1) modelo y migración; (2) generación y verificación de credenciales; (3) resolución y contexto, con la suite negativa completa antes que la positiva; (4) integración con los guards; (5) ABM y pantalla de administración; (6) alta de la cuenta del piloto y entrega de la credencial al cliente por un canal seguro.

## Open Questions

- ¿Qué vencimiento por defecto? La propuesta sugiere alinearlo con la duración del piloto y renovarlo a propósito, en vez de fijar un default largo.
- ¿La cuenta de servicio debería poder disparar correcciones, o solo escribir estructura? El pedido del cliente cubre las dos cosas, pero son permisos separables y conviene que lo sean.
- ¿Hace falta limitar la tasa de peticiones por cuenta de servicio? No lo pidieron, pero una identidad de máquina sin límite es una identidad de máquina que puede agotar la cuota de IA de un tirón.
- ¿Por qué canal se le entrega la credencial al cliente? No por correo ni por chat. Definirlo antes de generarla.
