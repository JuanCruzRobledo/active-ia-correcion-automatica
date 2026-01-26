# Backend Rules - Active-IA

## Clean Architecture (OBLIGATORIO)

```
Router (HTTP) → Service (Logica) → Repository (BD)
```

### Router
- Solo recibe HTTP, valida entrada, llama service, retorna response
- NO tiene logica de negocio
- Valida permisos con decoradores

### Service
- Toda la logica de negocio
- Orquesta llamadas a repositories
- Maneja transacciones
- NO accede directamente a la BD

### Repository
- Solo queries a la BD
- CRUD basico
- NO tiene logica de negocio

## Patrones Obligatorios

```python
# Router - siempre usar Depends()
@router.post("/", response_model=UsuarioResponse)
def crear_usuario(
    data: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    require_admin(current_user)
    service = UsuarioService(db)
    return service.crear(data)

# Service - inyectar repositorio
class UsuarioService:
    def __init__(self, db: Session):
        self.repo = UsuarioRepository(db)

    def crear(self, data: UsuarioCreate) -> Usuario:
        if self.repo.get_by_username(data.username):
            raise HTTPException(409, "Username ya existe")
        return self.repo.create(Usuario(**data.dict()))

# Repository - solo queries
class UsuarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str) -> Usuario | None:
        return self.db.query(Usuario).filter(
            Usuario.username == username,
            Usuario.activo == True
        ).first()
```

## HTTP Status Codes

| Situacion | Codigo |
|-----------|--------|
| GET exitoso | 200 |
| POST crear | 201 |
| DELETE exitoso | 204 |
| Validacion fallida | 400 |
| No autenticado | 401 |
| Sin permisos | 403 |
| No encontrado | 404 |
| Duplicado | 409 |
| Error interno | 500 |
| Servicio externo fallo | 502 |

## Validacion de Permisos

```python
from app.core.permissions import require_admin, require_coordinador

@router.post("/")
def crear_materia(current_user: Usuario = Depends(get_current_user)):
    require_admin(current_user)  # Solo admin
    ...

@router.get("/{id}/comisiones")
def listar_comisiones(current_user: Usuario = Depends(get_current_user)):
    require_coordinador(current_user, materia_id=id)  # Coordinador de esta materia
    ...
```

## NUNCA hacer esto

```python
# MAL - logica en router
@router.post("/")
def crear(data: Data, db: Session = Depends(get_db)):
    if db.query(Model).filter(...).first():  # NO! Esto va en service
        raise HTTPException(409)
    obj = Model(**data.dict())
    db.add(obj)
    db.commit()  # NO! commit en repository
    return obj

# MAL - acceso a BD en service
class MiService:
    def crear(self, data):
        return self.db.query(Model).filter(...).first()  # NO! Usar repository
```
