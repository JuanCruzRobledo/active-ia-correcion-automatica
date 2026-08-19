> **Gobernanza: 🔴 CRÍTICA.** Este change toca autenticación y autorización. **No se escribe código sin aprobación humana explícita**: se revisa el diseño antes de empezar y el diff de cada bloque antes de darlo por cerrado. Los CHECKPOINT marcados con 🛑 son bloqueantes.
>
> Regla de orden invertida: en los bloques de autenticación, **los tests negativos se escriben y pasan ANTES que los positivos**. Es la única forma de saber que el camino feliz no funciona por accidente.

## 0. Gate de arranque

- [ ] 🛑 0.1 Revisar el `design.md` completo con el responsable del proyecto y aprobar explícitamente las siete decisiones (credencial opaca, hasheo, alcance por materia, punto de inserción en el contexto, clave de IA propia, expiración obligatoria, auditoría atribuible).
- [ ] 🛑 0.2 Cerrar las cuatro Open Questions del design: vencimiento por defecto, separación del permiso de corrección, límite de tasa, y **canal de entrega de la credencial al cliente** (no correo, no chat).
- [ ] 0.3 Confirmar que el change `api-escritura-trabajos-practicos` está aplicado, para tener contra qué probar el alcance.

## 1. Modelo y migración

- [ ] 1.1 (RED) Test: la cuenta de servicio requiere universidad, nombre, prefijo, hash de credencial y fecha de expiración; sin expiración falla la validación.
- [ ] 1.2 Crear `app/models/cuenta_servicio.py` con `SoftDeleteMixin`, `TimestampMixin`, estado activo, marca de último uso, referencia a quién la creó, y la clave de IA cifrada.
- [ ] 1.3 Crear la tabla de asignación de materias del alcance, con unicidad por `(cuenta_servicio_id, materia_id)`.
- [ ] 1.4 Generar y aplicar la migración vía `docker-compose -f docker-compose.local.yml`; verificar el `downgrade`.
- [ ] 🛑 CHECKPOINT: mostrar el SQL de la migración y aprobar antes de seguir.

## 2. Generación y verificación de credenciales

- [ ] 2.1 (RED) Test: la credencial generada tiene el prefijo esperado y entropía suficiente; dos generaciones consecutivas no colisionan.
- [ ] 2.2 (RED) Test: el hash almacenado no permite recuperar la credencial; el prefijo sí queda en claro.
- [ ] 2.3 Implementar generación, hasheo y verificación en `app/core/security.py`, reusando el cifrado Fernet existente para la clave de IA.
- [ ] 2.4 (RED) Test: la verificación de la credencial compara en **tiempo constante**.
- [ ] 2.5 (TRIANGULATE) Test: una credencial con el prefijo correcto y el resto inválido no verifica.
- [ ] 🛑 CHECKPOINT: revisar el diff de `security.py` línea por línea antes de continuar.

## 3. Resolución y contexto — tests negativos primero

- [ ] 3.1 (RED) **Suite negativa completa, antes de cualquier camino feliz**: credencial inexistente → 401; cuenta desactivada → 401; cuenta dada de baja → 401; cuenta expirada → 401; credencial rotada → 401; credencial de otra universidad → sin acceso, sin revelar existencia.
- [ ] 3.2 (RED) Test: el 401 no revela si el prefijo existe.
- [ ] 3.3 Implementar la resolución de la credencial portadora y la construcción del contexto en `app/core/dependencies.py`.
- [ ] 3.4 (RED) Recién ahora: test de camino feliz — credencial válida de cuenta activa y vigente autentica y trae su universidad y su alcance.
- [ ] 3.5 (RED) Test: la marca de último uso se actualiza en cada autenticación exitosa.
- [ ] 3.6 (RED) Test: **la credencial no aparece en ningún log**, incluidos los de error y las trazas de excepción.
- [ ] 3.7 Verificar 3.6 provocando un error dentro de una petición autenticada y revisando la traza completa.
- [ ] 🛑 CHECKPOINT: la suite negativa pasa entera y el camino feliz pasa por la razón correcta, no por un default permisivo. Revisión humana del diff.

## 4. Integración con los guards existentes

- [ ] 4.1 (RED) **Test antipatrón, el más importante del change**: una cuenta de servicio NO satisface `require_admin`, `require_coordinador`, `require_tutor`, `require_gestor` ni `require_coordinador_or_admin`, aunque tenga permisos de escritura.
- [ ] 4.2 (RED) Test: materia fuera del alcance → 403 sin revelar existencia; permiso no otorgado sobre materia del alcance → 403.
- [ ] 4.3 Implementar la aceptación del contexto de servicio en `app/core/permissions.py`, sin cambiar ninguna regla humana existente.
- [ ] 4.4 (RED) Test de no regresión: el rol tutor **sigue** recibiendo 403 al leer los criterios de una rúbrica.
- [ ] 4.5 (RED) Tests de no regresión de coordinador y administrador: comportamiento idéntico al previo al change.
- [ ] 4.6 (TRIANGULATE) Test: una operación cubierta por los permisos de la cuenta, sobre una materia de su alcance, se permite.
- [ ] 🛑 CHECKPOINT: verificar que ningún rol humano ganó capacidades. Este es el punto donde un atajo de implementación abre un agujero — revisar el diff con esa pregunta en la mano.

## 5. ABM y servicio

- [ ] 5.1 (RED) Tests de permisos del ABM: alta por administrador → permitida; por coordinador → 403; por una cuenta de servicio → 403.
- [ ] 5.2 (RED) Tests de alta: materia de otra universidad en el alcance → rechazo; sin permisos declarados → rechazo; sin expiración → rechazo.
- [ ] 5.3 Implementar `app/services/cuenta_servicio_service.py` y `app/repositories/cuenta_servicio_repository.py`.
- [ ] 5.4 (RED) Test: la credencial completa se devuelve **solo** en el alta y en la rotación; nunca en listado ni en consulta.
- [ ] 5.5 (RED) Test: la rotación invalida la anterior de inmediato y conserva alcance, permisos y clave de IA.
- [ ] 5.6 (RED) Test: quitar una materia del alcance corta el acceso en la siguiente petición; agregar un permiso lo habilita.
- [ ] 5.7 Implementar `app/routers/cuentas_servicio.py` con el ABM, sin lógica de negocio.
- [ ] 5.8 (RED) Test: la clave de IA se almacena cifrada y no se devuelve en ninguna lectura; la lectura solo indica si está configurada.
- [ ] CHECKPOINT: ABM completo con la superficie de exposición de la credencial acotada al alta y la rotación.

## 6. Corrección con clave de IA propia

- [ ] 6.1 (RED) Test: una corrección disparada por una cuenta de servicio usa la clave de esa cuenta.
- [ ] 6.2 (RED) Test: una cuenta de servicio sin clave de IA recibe un error que indica qué falta, y **no** cae a la clave de ningún usuario.
- [ ] 6.3 Implementar la resolución de la clave por actor en el flujo de corrección.
- [ ] CHECKPOINT: el costo del piloto queda separado y medible.

## 7. Auditoría

- [ ] 7.1 (RED) Test: una acción de cuenta de servicio se registra con la cuenta como actor, distinguible de una acción humana.
- [ ] 7.2 Implementar el actor de servicio en `app/services/actividad_service.py`.
- [ ] CHECKPOINT: la auditoría distingue máquina de persona.

## 8. Frontend

- [ ] 8.1 Pantalla de administración de cuentas de servicio para administradores: alta, rotación, modificación de alcance, desactivación.
- [ ] 8.2 Mostrar la credencial recién generada una sola vez, con la advertencia explícita de que no podrá recuperarse.
- [ ] 8.3 Verificar que al reabrir la cuenta solo se ve el prefijo.
- [ ] 8.4 `npm run typecheck` y `npm run lint` sin errores; sin `any`.

## 9. Verificación y entrega

- [ ] 9.1 `pytest` completo en el backend, sin regresiones.
- [ ] 9.2 Repasar la suite negativa entera una vez más contra la implementación final.
- [ ] 9.3 Confirmar por grep sobre los logs de una corrida real que la credencial no aparece en ningún lado.
- [ ] 9.4 Crear la cuenta de servicio del piloto, con alcance a las materias del piloto y vencimiento acordado en 0.2.
- [ ] 9.5 Entregarle la credencial al equipo de AI-Native por el canal definido en 0.2.
- [ ] 9.6 `openspec validate cuenta-de-servicio-integracion --strict`.
