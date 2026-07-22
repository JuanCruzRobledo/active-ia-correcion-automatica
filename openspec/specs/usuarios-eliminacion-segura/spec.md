# usuarios-eliminacion-segura Specification

## Purpose
Asegurar que el borrado de un usuario desde la UI de administración exija una confirmación explícita en un diálogo destructivo y provea feedback de éxito y de error, evitando borrados accidentales y fallos silenciosos.
## Requirements
### Requirement: Confirmación explícita antes de eliminar un usuario

El sistema SHALL requerir una confirmación explícita del administrador en un diálogo destructivo (`ConfirmDialog` con `variant="destructive"`) antes de ejecutar el borrado de un usuario desde la UI de administración. La mutación de borrado NO SHALL dispararse hasta que el administrador confirme.

#### Scenario: Abrir el diálogo de confirmación no borra al usuario

- **WHEN** el administrador selecciona "Eliminar" en el menú de acciones de un usuario
- **THEN** el sistema muestra un `ConfirmDialog` destructivo con título, mensaje y botón "Eliminar"
- **AND** NO invoca todavía el servicio de borrado del usuario

#### Scenario: Confirmar dispara el borrado

- **WHEN** el administrador pulsa el botón de confirmación ("Eliminar") en el diálogo
- **THEN** el sistema invoca la mutación de borrado con el id del usuario seleccionado
- **AND** cierra el diálogo cuando la operación termina

#### Scenario: Cancelar aborta el borrado

- **WHEN** el administrador cierra el diálogo (Cancelar, X o Escape) sin confirmar
- **THEN** el sistema cierra el diálogo sin invocar el servicio de borrado
- **AND** el usuario permanece sin cambios

### Requirement: Feedback de éxito al eliminar un usuario

El sistema SHALL informar al administrador con un `toast.success` cuando el borrado de un usuario se completa correctamente, además de refrescar la lista de usuarios (invalidación de queries).

#### Scenario: Borrado exitoso muestra confirmación

- **WHEN** la mutación de borrado de un usuario resuelve sin error
- **THEN** el sistema muestra un `toast.success` indicando que el usuario fue eliminado
- **AND** invalida las queries de usuarios para refrescar la lista

### Requirement: Feedback de error cuando el borrado falla

El hook de borrado de usuario (`useDeleteUsuario`) SHALL definir un `onError` que muestre un `toast.error` con un mensaje legible derivado del error mediante `getErrorMessage(error)`, de modo que un fallo del borrado nunca sea silencioso.

#### Scenario: Borrado fallido notifica al usuario

- **WHEN** la mutación de borrado de un usuario rechaza con un error
- **THEN** el sistema muestra un `toast.error` con el mensaje obtenido de `getErrorMessage(error)`
- **AND** no se produce ninguna invalidación de éxito ni toast de éxito

