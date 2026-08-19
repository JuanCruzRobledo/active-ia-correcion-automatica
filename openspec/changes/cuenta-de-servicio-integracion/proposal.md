## Why

Verificado contra la API en vivo el 2026-08-17:

```
GET  /rubricas/?materia_id=N     funciona con rol tutor
GET  /rubricas/{id}              403 — "Se requiere rol de coordinador o administrador"
```

AI-Native necesita publicar TPs y rúbricas de una materia de forma automatizada. Con el modelo actual hay tres formas de dárselo, y las tres son malas:

1. **Una cuenta de tutor** — no alcanza: no puede ni leer los criterios de una rúbrica.
2. **Una cuenta de coordinador con usuario y contraseña** — le da acceso a **todas** las materias que coordina, un token que caduca cada 7 días (`ACCESS_TOKEN_EXPIRE_DAYS`) y credenciales de persona en manos de un sistema. No se puede revocar sin romperle la sesión a un humano, y en el log de auditoría las acciones aparecen como si las hubiera hecho esa persona.
3. **Una cuenta de administrador** — todo lo anterior, peor.

Ninguna de las tres es lo que hace falta. Lo que hace falta es una **identidad de máquina**: credencial de larga duración, revocable sola, acotada a las materias del piloto, atribuible en la auditoría, y que consuma su propia cuota de IA en vez de la de una persona.

Este change es lo que el cliente pidió como punto 2 de "qué necesitamos para arrancar", y es lo que les permite probar contra un entorno real sin que nadie preste su contraseña.

## What Changes

- **Nueva entidad `CuentaServicio`**: identidad de máquina de una universidad, con nombre, credencial de larga duración almacenada **hasheada**, alcance explícito de materias, lista de permisos, fecha de expiración, estado activo, marca de último uso, y baja lógica.
- **Autenticación por credencial de servicio**: las peticiones se autentican con un encabezado portador que lleva la credencial. El sistema la resuelve a la cuenta de servicio y construye un contexto equivalente al de un usuario, con su universidad y su alcance.
- **La credencial se muestra una sola vez**, al crearla. Después solo se guarda su hash y un prefijo visible para identificarla en un listado. No hay forma de recuperarla: se rota.
- **Alcance por materia, no por rol global.** Una cuenta de servicio no "es coordinadora": tiene permiso de escritura sobre las materias que se le asignaron y sobre ninguna otra. Fuera de su alcance recibe 403 igual que cualquiera.
- **API key de IA propia.** La cuenta de servicio guarda su propia clave de proveedor de IA, cifrada con el mismo mecanismo Fernet que las de los usuarios, para que las correcciones automatizadas no consuman la cuota de una persona y sean atribuibles.
- **Auditoría con actor de servicio.** Toda acción queda registrada como hecha por la cuenta de servicio, no por un humano.
- **Revocación inmediata.** Desactivar o dar de baja la cuenta corta el acceso en la siguiente petición, sin afectar a ningún usuario.
- **Los permisos existentes no se relajan.** Ningún rol humano gana capacidades con este change. El rol tutor sigue sin poder leer los criterios de una rúbrica.

## Capabilities

### New Capabilities

- `cuenta-servicio-identidad`: entidad de identidad de máquina con credencial hasheada de larga duración, alcance por materia, permisos explícitos, expiración, revocación y auditoría atribuible.
- `cuenta-servicio-autenticacion`: resolución de la credencial portadora a un contexto de ejecución con su universidad y su alcance, y su integración con las verificaciones de permisos existentes.
- `cuenta-servicio-abm`: administración de cuentas de servicio — alta con credencial mostrada una sola vez, rotación, revocación, listado y asignación de materias.

### Modified Capabilities

- `permisos-universidad-activa`: las verificaciones de permisos pasan a aceptar un contexto de cuenta de servicio además del de usuario, sin cambiar ninguna regla existente.
- `aislamiento-datos-por-universidad`: las cuentas de servicio quedan scopeadas por universidad como cualquier otro actor.

## Impact

**Backend**
- `app/models/cuenta_servicio.py` — nuevo, con la tabla de asignación de materias.
- `app/core/security.py` — generación, hasheo y verificación de credenciales de servicio; reuso del cifrado Fernet existente para la clave de IA.
- `app/core/dependencies.py` — resolución de la credencial portadora y construcción del contexto.
- `app/core/permissions.py` — aceptar el contexto de servicio en las verificaciones existentes.
- `app/routers/cuentas_servicio.py` — ABM, solo para administradores.
- `app/services/cuenta_servicio_service.py`, `app/repositories/cuenta_servicio_repository.py` — nuevos.
- `app/services/actividad_service.py` — actor de servicio en la auditoría.
- `alembic/versions/` — migración de las dos tablas nuevas.

**Frontend**
- Pantalla de administración de cuentas de servicio, con la credencial mostrada una sola vez al crearla.

**Gobernanza: 🔴 CRÍTICA.** Este change toca autenticación y autorización. Es análisis y propuesta; **no se escribe código sin aprobación humana explícita, revisando el diseño antes y el diff después**.
