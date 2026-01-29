# Active-IA Backend - Guía de Inicialización

## Prerrequisitos

- Python 3.11+
- PostgreSQL 15+ (local o Docker)
- pip (gestor de paquetes de Python)

## 1. Instalación de Dependencias

```bash
cd backend
pip install -r requirements.txt
```

## 2. Configuración de Base de Datos

### Opción A: PostgreSQL Local

1. Crear la base de datos:

```sql
CREATE DATABASE activeai;
CREATE USER activeai WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE activeai TO activeai;
```

2. El archivo `.env` ya está configurado con estas credenciales:
```
DATABASE_URL=postgresql+asyncpg://activeai:password@localhost:5432/activeai
```

### Opción B: PostgreSQL con Docker

```bash
docker run --name activeai-db \
  -e POSTGRES_DB=activeai \
  -e POSTGRES_USER=activeai \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  -d postgres:15
```

## 3. Inicializar Base de Datos

Este comando creará todas las tablas y el usuario administrador inicial:

```bash
python scripts/init_db.py
```

**Salida esperada:**
```
🚀 Iniciando configuración de base de datos...
📦 Creando tablas...
✅ Tablas creadas exitosamente
👤 Creando usuario administrador...
✅ Usuario admin creado exitosamente

============================================================
📝 CREDENCIALES DE ACCESO
============================================================
  Username: admin
  Password: admin123
============================================================
⚠️  IMPORTANTE: Cambia la contraseña en el primer login
============================================================

✨ Inicialización completada
```

## 4. Ejecutar el Servidor

```bash
uvicorn app.main:app --reload --port 8000
```

El servidor estará disponible en: `http://localhost:8000`

Documentación API (Swagger): `http://localhost:8000/docs`

## 5. Credenciales de Desarrollo

### Administrador (creado automáticamente)
```
Username: admin
Password: admin123
```

**Al hacer primer login**, el sistema te obligará a cambiar la contraseña.

### Coordinador y Tutor

Estos roles deben ser creados por el administrador:

1. Inicia sesión como admin
2. Ve a `/admin/usuarios`
3. Crea usuarios con rol Coordinador o Tutor
4. El sistema genera una **contraseña temporal** automáticamente
5. Comunica las credenciales al usuario
6. El usuario debe cambiar su contraseña en el primer login

## 6. Crear Usuarios de Prueba (Opcional)

Puedes crear usuarios de prueba manualmente a través de la API:

```bash
# Crear coordinador
curl -X POST http://localhost:8000/api/v1/usuarios \
  -H "Authorization: Bearer <token_admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "coord1",
    "nombre": "María Coordinadora",
    "rol": "COORDINADOR"
  }'

# Crear tutor
curl -X POST http://localhost:8000/api/v1/usuarios \
  -H "Authorization: Bearer <token_admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "tutor1",
    "nombre": "Carlos Tutor",
    "rol": "TUTOR"
  }'
```

La respuesta incluirá la contraseña temporal generada.

## 7. Verificar Instalación

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Login de Prueba
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

Deberías recibir un token JWT y la información del usuario.

## 8. Migraciones de Base de Datos

Si modificas los modelos de SQLAlchemy, genera y aplica migraciones:

```bash
# Generar migración
alembic revision --autogenerate -m "descripción del cambio"

# Aplicar migraciones
alembic upgrade head

# Revertir última migración
alembic downgrade -1
```

## 9. Variables de Entorno Importantes

El archivo `.env` ya está configurado con valores de desarrollo:

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `DATABASE_URL` | postgresql+asyncpg://... | Conexión a PostgreSQL |
| `SECRET_KEY` | (generado) | Clave para firmar JWT |
| `ENCRYPTION_KEY` | (generado) | Clave para encriptar API Keys |
| `ACCESS_TOKEN_EXPIRE_DAYS` | 7 | Días de expiración del token |
| `CORS_ORIGINS` | localhost:3000,5173 | Orígenes permitidos |

## 10. Problemas Comunes

### Error: "Database does not exist"
- Asegúrate de haber creado la base de datos (ver paso 2)

### Error: "password authentication failed"
- Verifica que las credenciales en `.env` coincidan con las de PostgreSQL

### Error: "module not found"
- Ejecuta `pip install -r requirements.txt`

### Error: "port 8000 already in use"
- Cambia el puerto: `uvicorn app.main:app --reload --port 8001`

## 11. Próximos Pasos

1. ✅ Inicializar base de datos
2. ✅ Iniciar backend
3. ⏭️ Iniciar frontend (ver `frontend/README.md`)
4. ⏭️ Probar login con credenciales admin
5. ⏭️ Crear usuarios coordinador y tutor
6. ⏭️ Configurar API Keys Gemini en perfiles de usuario

---

**¿Problemas?** Revisa los logs del servidor o consulta la documentación completa en `docs/`.
