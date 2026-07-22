# 06 - Modelo de Datos

---

## 1. Resumen de Entidades

El sistema utiliza PostgreSQL con SQLAlchemy como ORM. Las entidades principales son:

| Entidad | Descripción | Relaciones principales |
|---------|-------------|------------------------|
| **Usuario** | Usuarios del sistema (Admin, Coordinador, Tutor) | N:M con Materia (coordinadores), N:M con Comisión (tutores) |
| **Materia** | Materias/cursos (ej: Programación 1) | 1:N con Comisión, 1:N con Rúbrica |
| **CoordinadorMateria** | Relación N:M entre coordinadores y materias | FK a Usuario, FK a Materia |
| **Comision** | Grupos de alumnos por materia/año | N:1 con Materia, N:M con Tutor, 1:N con Entrega |
| **ComisionTutor** | Relación N:M entre tutores y comisiones | FK a Usuario, FK a Comisión |
| **Rubrica** | Criterios de evaluación por materia | N:1 con Materia, 1:N con Entrega |
| **Entrega** | Entregas de alumnos | N:1 con Comisión, N:1 con Rúbrica, 1:1 con Corrección |
| **Correccion** | Resultado de evaluación | 1:1 con Entrega |
| **EntregaHistorial** | Historial de entregas sobrescritas | N:1 con Entrega |

---

## 2. Diagrama de Relaciones (ERD)

```
┌─────────────────┐
│     Usuario     │
├─────────────────┤
│ id (PK)         │
│ username        │
│ nombre          │
│ password_hash   │
│ rol             │◄─────────────────────────────────────────────┐
│ gemini_api_key  │                                              │
│ primer_login    │                                              │
│ activo          │                                              │
└────────┬────────┘                                              │
         │                                                       │
         │ Si rol = COORDINADOR                                  │ Si rol = TUTOR
         │                                                       │
         ▼                                                       │
┌─────────────────────┐                                          │
│ CoordinadorMateria  │                                          │
├─────────────────────┤         ┌─────────────────┐              │
│ id (PK)             │         │     Materia     │              │
│ coordinador_id (FK) │────────>├─────────────────┤              │
│ materia_id (FK)     │         │ id (PK)         │              │
│ asignado_en         │         │ codigo          │              │
└─────────────────────┘         │ nombre          │              │
                                │ descripcion     │              │
                                │ activa          │              │
                                └────────┬────────┘              │
                                         │                       │
                          ┌──────────────┼──────────────┐        │
                          │ 1:N          │ 1:N          │        │
                          ▼              ▼              │        │
               ┌─────────────────┐  ┌─────────────────┐ │        │
               │    Comision     │  │     Rubrica     │ │        │
               ├─────────────────┤  ├─────────────────┤ │        │
               │ id (PK)         │  │ id (PK)         │ │        │
               │ materia_id (FK) │  │ materia_id (FK) │◄┘        │
               │ nombre          │  │ tipo            │          │
               │ anio            │  │ nombre          │          │
               │ activa          │  │ numero          │          │
               └────────┬────────┘  │ anio            │          │
                        │           │ criterios_json  │          │
         ┌──────────────┤           │ fuente          │          │
         │              │           │ activa          │          │
         │              │           └────────┬────────┘          │
         │              │                    │                   │
         ▼              │                    │                   │
┌─────────────────────┐ │                    │                   │
│   ComisionTutor     │ │                    │                   │
├─────────────────────┤ │                    │                   │
│ id (PK)             │ │                    │                   │
│ comision_id (FK)    │◄┘                    │                   │
│ tutor_id (FK)       │◄─────────────────────┼───────────────────┘
│ asignado_en         │                      │
└─────────────────────┘                      │
         │                                   │
         │ 1:N                               │ 1:N
         ▼                                   │
┌─────────────────────┐                      │
│      Entrega        │◄─────────────────────┘
├─────────────────────┤
│ id (PK)             │
│ comision_id (FK)    │
│ rubrica_id (FK)     │
│ alumno_nombre       │
│ archivo_nombre      │
│ archivo_ruta        │
│ contenido_preview   │
│ estado              │
│ hash_sha256         │
│ subido_por_id (FK)  │
│ activo              │
└────────┬────────────┘
         │
         │ 1:1
         ▼
┌─────────────────────┐
│    Correccion       │
├─────────────────────┤
│ id (PK)             │
│ entrega_id (FK) UQ  │
│ nota                │
│ criterios_json      │
│ fortalezas          │
│ recomendaciones     │
│ comentario_general  │
│ editado_manualmente │
│ raw_response        │
│ corregido_por_id    │
└─────────────────────┘
```

---

## 3. Definición Detallada de Entidades

### 3.1 Usuario

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | Integer | PK, Auto-increment | Identificador único |
| `username` | String(50) | Unique, Not Null | Nombre de usuario para login |
| `nombre` | String(100) | Not Null | Nombre completo |
| `password_hash` | String(255) | Not Null | Hash bcrypt de la contraseña |
| `rol` | Enum | Not Null | 'ADMIN', 'COORDINADOR', 'TUTOR' |
| `gemini_api_key_encrypted` | Text | Nullable | API Key de IA encriptada con Fernet (AES-128-CBC + HMAC-SHA256) |
| `gemini_api_key_valid` | Boolean | Default False | Flag de validación de API Key |
| `primer_login` | Boolean | Default True | True si debe cambiar contraseña |
| `activo` | Boolean | Default True | False = soft delete |
| `created_at` | DateTime | Default Now | Fecha de creación |
| `updated_at` | DateTime | Auto-update | Fecha de última modificación |

**Índices:**
- `ix_usuario_username` (username)
- `ix_usuario_rol` (rol)
- `ix_usuario_activo` (activo)

**SQLAlchemy Model:**

```python
class RolEnum(str, Enum):
    ADMIN = "ADMIN"
    COORDINADOR = "COORDINADOR"
    TUTOR = "TUTOR"

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(SQLAlchemyEnum(RolEnum), nullable=False, index=True)
    gemini_api_key_encrypted = Column(Text, nullable=True)
    gemini_api_key_valid = Column(Boolean, default=False)
    primer_login = Column(Boolean, default=True)
    activo = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    materias_coordinadas = relationship("CoordinadorMateria", back_populates="coordinador")
    comisiones_asignadas = relationship("ComisionTutor", back_populates="tutor")
    entregas_subidas = relationship("Entrega", back_populates="subido_por")
    correcciones_realizadas = relationship("Correccion", back_populates="corregido_por")
```

---

### 3.2 Materia

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | Integer | PK, Auto-increment | Identificador único |
| `codigo` | String(20) | Unique, Not Null | Código único (ej: PROG1) |
| `nombre` | String(100) | Not Null | Nombre completo |
| `descripcion` | Text | Nullable | Descripción opcional |
| `activa` | Boolean | Default True | False = soft delete |
| `created_at` | DateTime | Default Now | Fecha de creación |
| `updated_at` | DateTime | Auto-update | Fecha de última modificación |

**Índices:**
- `ix_materia_codigo` (codigo) UNIQUE
- `ix_materia_activa` (activa)

**SQLAlchemy Model:**

```python
class Materia(Base):
    __tablename__ = "materias"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)
    activa = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    coordinadores = relationship("CoordinadorMateria", back_populates="materia")
    comisiones = relationship("Comision", back_populates="materia")
    rubricas = relationship("Rubrica", back_populates="materia")
```

---

### 3.3 CoordinadorMateria (Relación N:M)

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | Integer | PK, Auto-increment | Identificador único |
| `coordinador_id` | Integer | FK Usuario, Not Null | ID del coordinador |
| `materia_id` | Integer | FK Materia, Not Null | ID de la materia |
| `asignado_en` | DateTime | Default Now | Fecha de asignación |

**Índices:**
- `uq_coordinador_materia` (coordinador_id, materia_id) UNIQUE

**SQLAlchemy Model:**

```python
class CoordinadorMateria(Base):
    __tablename__ = "coordinador_materia"

    id = Column(Integer, primary_key=True, index=True)
    coordinador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    asignado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('coordinador_id', 'materia_id', name='uq_coordinador_materia'),
    )

    # Relaciones
    coordinador = relationship("Usuario", back_populates="materias_coordinadas")
    materia = relationship("Materia", back_populates="coordinadores")
```

---

### 3.4 Comision

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | Integer | PK, Auto-increment | Identificador único |
| `materia_id` | Integer | FK Materia, Not Null | ID de la materia |
| `nombre` | String(50) | Not Null | Nombre (ej: Comisión A) |
| `anio` | Integer | Not Null | Año académico (ej: 2026) |
| `activa` | Boolean | Default True | False = soft delete |
| `created_at` | DateTime | Default Now | Fecha de creación |
| `updated_at` | DateTime | Auto-update | Fecha de última modificación |

**Índices:**
- `uq_comision_materia_nombre_anio` (materia_id, nombre, anio) UNIQUE
- `ix_comision_materia_id` (materia_id)
- `ix_comision_anio` (anio)
- `ix_comision_activa` (activa)

**SQLAlchemy Model:**

```python
class Comision(Base):
    __tablename__ = "comisiones"

    id = Column(Integer, primary_key=True, index=True)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False, index=True)
    nombre = Column(String(50), nullable=False)
    anio = Column(Integer, nullable=False, index=True)
    activa = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('materia_id', 'nombre', 'anio', name='uq_comision_materia_nombre_anio'),
    )

    # Relaciones
    materia = relationship("Materia", back_populates="comisiones")
    tutores = relationship("ComisionTutor", back_populates="comision")
    entregas = relationship("Entrega", back_populates="comision")
```

---

### 3.5 ComisionTutor (Relación N:M)

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | Integer | PK, Auto-increment | Identificador único |
| `comision_id` | Integer | FK Comision, Not Null | ID de la comisión |
| `tutor_id` | Integer | FK Usuario, Not Null | ID del tutor |
| `asignado_en` | DateTime | Default Now | Fecha de asignación |

**Índices:**
- `uq_comision_tutor` (comision_id, tutor_id) UNIQUE

**SQLAlchemy Model:**

```python
class ComisionTutor(Base):
    __tablename__ = "comision_tutor"

    id = Column(Integer, primary_key=True, index=True)
    comision_id = Column(Integer, ForeignKey("comisiones.id"), nullable=False)
    tutor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    asignado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('comision_id', 'tutor_id', name='uq_comision_tutor'),
    )

    # Relaciones
    comision = relationship("Comision", back_populates="tutores")
    tutor = relationship("Usuario", back_populates="comisiones_asignadas")
```

---

### 3.6 Rubrica

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | Integer | PK, Auto-increment | Identificador único |
| `materia_id` | Integer | FK Materia, Not Null | ID de la materia |
| `tipo` | Enum | Not Null | Tipo de rúbrica |
| `nombre` | String(100) | Not Null | Nombre (ej: TP1 - Listas) |
| `numero` | Integer | Not Null, Default 1 | Número (1, 2, 3...) |
| `anio` | Integer | Not Null | Año académico |
| `criterios_json` | JSONB | Not Null | Estructura de criterios |
| `fuente` | Enum | Default 'manual' | 'manual', 'pdf' |
| `archivo_original` | String(255) | Nullable | Ruta al PDF original |
| `activa` | Boolean | Default True | False = soft delete |
| `created_at` | DateTime | Default Now | Fecha de creación |
| `updated_at` | DateTime | Auto-update | Fecha de última modificación |

**Tipos de Rúbrica (Enum):**

```python
class TipoRubricaEnum(str, Enum):
    TP = "TP"
    PARCIAL_1 = "PARCIAL_1"
    PARCIAL_2 = "PARCIAL_2"
    RECUPERATORIO_1 = "RECUPERATORIO_1"
    RECUPERATORIO_2 = "RECUPERATORIO_2"
    FINAL = "FINAL"
    GLOBAL = "GLOBAL"
```

**Índices:**
- `uq_rubrica_materia_tipo_numero_anio` (materia_id, tipo, numero, anio) UNIQUE
- `ix_rubrica_materia_id` (materia_id)
- `ix_rubrica_anio` (anio)
- `ix_rubrica_activa` (activa)

**SQLAlchemy Model:**

```python
class FuenteRubricaEnum(str, Enum):
    MANUAL = "manual"
    PDF = "pdf"

class Rubrica(Base):
    __tablename__ = "rubricas"

    id = Column(Integer, primary_key=True, index=True)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False, index=True)
    tipo = Column(SQLAlchemyEnum(TipoRubricaEnum), nullable=False)
    nombre = Column(String(100), nullable=False)
    numero = Column(Integer, nullable=False, default=1)
    anio = Column(Integer, nullable=False, index=True)
    criterios_json = Column(JSONB, nullable=False)
    fuente = Column(SQLAlchemyEnum(FuenteRubricaEnum), default=FuenteRubricaEnum.MANUAL)
    archivo_original = Column(String(255), nullable=True)
    activa = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('materia_id', 'tipo', 'numero', 'anio', name='uq_rubrica_materia_tipo_numero_anio'),
    )

    # Relaciones
    materia = relationship("Materia", back_populates="rubricas")
    entregas = relationship("Entrega", back_populates="rubrica")
```

---

### 3.7 Entrega

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | Integer | PK, Auto-increment | Identificador único |
| `comision_id` | Integer | FK Comision, Not Null | ID de la comisión |
| `rubrica_id` | Integer | FK Rubrica, Not Null | ID de la rúbrica |
| `alumno_nombre` | String(100) | Not Null | Nombre del alumno |
| `archivo_nombre` | String(255) | Not Null | Nombre original del archivo |
| `archivo_ruta` | String(500) | Not Null | Ruta en sistema de archivos |
| `archivo_tamanio` | Integer | Default 0 | Tamaño en bytes |
| `archivo_tipo` | String(10) | Not Null | 'zip' o 'txt' |
| `contenido_preview` | Text | Nullable | Primeros 500 caracteres del código |
| `estado` | Enum | Default 'SUBIDA' | Estado de la entrega |
| `hash_sha256` | String(64) | Nullable | Hash SHA-256 del contenido |
| `subido_por_id` | Integer | FK Usuario, Not Null | Usuario que subió |
| `activo` | Boolean | Default True | False = soft delete |
| `created_at` | DateTime | Default Now | Fecha de subida |
| `updated_at` | DateTime | Auto-update | Fecha de última modificación |

**Estados de Entrega (Enum):**

```python
class EstadoEntregaEnum(str, Enum):
    SUBIDA = "SUBIDA"           # Archivo cargado, sin corregir
    PENDIENTE = "PENDIENTE"     # En proceso de corrección
    CORREGIDA = "CORREGIDA"     # Corrección completada
    ERROR = "ERROR"             # Falló el proceso
```

**Índices:**
- `uq_entrega_rubrica_alumno` (rubrica_id, alumno_nombre) UNIQUE (solo activos)
- `ix_entrega_comision_id` (comision_id)
- `ix_entrega_rubrica_id` (rubrica_id)
- `ix_entrega_estado` (estado)
- `ix_entrega_hash` (hash_sha256)
- `ix_entrega_activo` (activo)

**SQLAlchemy Model:**

```python
class Entrega(Base):
    __tablename__ = "entregas"

    id = Column(Integer, primary_key=True, index=True)
    comision_id = Column(Integer, ForeignKey("comisiones.id"), nullable=False, index=True)
    rubrica_id = Column(Integer, ForeignKey("rubricas.id"), nullable=False, index=True)
    alumno_nombre = Column(String(100), nullable=False)
    archivo_nombre = Column(String(255), nullable=False)
    archivo_ruta = Column(String(500), nullable=False)
    archivo_tamanio = Column(Integer, default=0)
    archivo_tipo = Column(String(10), nullable=False)
    contenido_preview = Column(Text, nullable=True)
    estado = Column(SQLAlchemyEnum(EstadoEntregaEnum), default=EstadoEntregaEnum.SUBIDA, index=True)
    hash_sha256 = Column(String(64), nullable=True, index=True)
    subido_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    activo = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # Unique solo para entregas activas (partial index en PostgreSQL)
        Index('uq_entrega_rubrica_alumno_activo', 'rubrica_id', 'alumno_nombre',
              unique=True, postgresql_where=text('activo = true')),
    )

    # Relaciones
    comision = relationship("Comision", back_populates="entregas")
    rubrica = relationship("Rubrica", back_populates="entregas")
    subido_por = relationship("Usuario", back_populates="entregas_subidas")
    correccion = relationship("Correccion", back_populates="entrega", uselist=False)
    historial = relationship("EntregaHistorial", back_populates="entrega_actual")
```

---

### 3.8 Correccion

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | Integer | PK, Auto-increment | Identificador único |
| `entrega_id` | Integer | FK Entrega, Unique, Not Null | ID de la entrega (1:1) |
| `nota` | Decimal(5,2) | Not Null | Calificación (0.00 - 100.00) |
| `criterios_json` | JSONB | Not Null | Evaluación por criterio |
| `fortalezas` | ARRAY(Text) | Default [] | Lista de fortalezas |
| `recomendaciones` | ARRAY(Text) | Default [] | Lista de recomendaciones |
| `comentario_general` | Text | Nullable | Feedback general |
| `editado_manualmente` | Boolean | Default False | True si fue editado por tutor |
| `raw_response` | JSONB | Nullable | Respuesta cruda de Gemini |
| `corregido_por_id` | Integer | FK Usuario, Not Null | Usuario que corrigió/editó |
| `created_at` | DateTime | Default Now | Fecha de corrección |
| `updated_at` | DateTime | Auto-update | Fecha de última modificación |

**SQLAlchemy Model:**

```python
class Correccion(Base):
    __tablename__ = "correcciones"

    id = Column(Integer, primary_key=True, index=True)
    entrega_id = Column(Integer, ForeignKey("entregas.id"), unique=True, nullable=False)
    nota = Column(Numeric(5, 2), nullable=False)
    criterios_json = Column(JSONB, nullable=False)
    fortalezas = Column(ARRAY(Text), default=[])
    recomendaciones = Column(ARRAY(Text), default=[])
    comentario_general = Column(Text, nullable=True)
    editado_manualmente = Column(Boolean, default=False)
    raw_response = Column(JSONB, nullable=True)
    corregido_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    entrega = relationship("Entrega", back_populates="correccion")
    corregido_por = relationship("Usuario", back_populates="correcciones_realizadas")
```

---

### 3.9 EntregaHistorial (Para sobrescrituras)

Cuando se sobrescribe una entrega existente, la entrega anterior se guarda aquí.

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | Integer | PK, Auto-increment | Identificador único |
| `entrega_actual_id` | Integer | FK Entrega, Not Null | ID de la entrega actual |
| `alumno_nombre` | String(100) | Not Null | Nombre del alumno |
| `archivo_nombre` | String(255) | Not Null | Nombre del archivo anterior |
| `archivo_ruta` | String(500) | Not Null | Ruta del archivo anterior |
| `archivo_tamanio` | Integer | Default 0 | Tamaño en bytes |
| `contenido_preview` | Text | Nullable | Preview del código anterior |
| `hash_sha256` | String(64) | Nullable | Hash del contenido anterior |
| `nota_anterior` | Decimal(5,2) | Nullable | Nota si estaba corregida |
| `correccion_json` | JSONB | Nullable | Corrección completa anterior |
| `sobrescrito_en` | DateTime | Default Now | Fecha de sobrescritura |
| `sobrescrito_por_id` | Integer | FK Usuario, Not Null | Usuario que sobrescribió |

**SQLAlchemy Model:**

```python
class EntregaHistorial(Base):
    __tablename__ = "entregas_historial"

    id = Column(Integer, primary_key=True, index=True)
    entrega_actual_id = Column(Integer, ForeignKey("entregas.id"), nullable=False, index=True)
    alumno_nombre = Column(String(100), nullable=False)
    archivo_nombre = Column(String(255), nullable=False)
    archivo_ruta = Column(String(500), nullable=False)
    archivo_tamanio = Column(Integer, default=0)
    contenido_preview = Column(Text, nullable=True)
    hash_sha256 = Column(String(64), nullable=True)
    nota_anterior = Column(Numeric(5, 2), nullable=True)
    correccion_json = Column(JSONB, nullable=True)
    sobrescrito_en = Column(DateTime, default=datetime.utcnow)
    sobrescrito_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    # Relaciones
    entrega_actual = relationship("Entrega", back_populates="historial")
    sobrescrito_por = relationship("Usuario")
```

---

## 4. Estructuras JSON

### 4.1 criterios_json (Rúbrica)

Estructura que define los criterios de evaluación:

```json
{
  "puntaje_maximo": 100,
  "criterios": [
    {
      "id": "c1",
      "nombre": "Funcionalidad correcta",
      "descripcion": "El programa realiza las operaciones solicitadas",
      "puntaje_maximo": 40,
      "niveles": [
        {
          "puntaje": 40,
          "descripcion": "Todas las funciones operan correctamente"
        },
        {
          "puntaje": 30,
          "descripcion": "Funciona con errores menores"
        },
        {
          "puntaje": 20,
          "descripcion": "Funciona parcialmente"
        },
        {
          "puntaje": 10,
          "descripcion": "Errores graves"
        },
        {
          "puntaje": 0,
          "descripcion": "No funciona"
        }
      ]
    },
    {
      "id": "c2",
      "nombre": "Uso correcto de listas",
      "descripcion": "Implementa operaciones de listas según requerido",
      "puntaje_maximo": 30,
      "niveles": [...]
    },
    {
      "id": "c3",
      "nombre": "Estilo y legibilidad",
      "descripcion": "Código limpio, bien indentado, nombres descriptivos",
      "puntaje_maximo": 20,
      "niveles": [...]
    },
    {
      "id": "c4",
      "nombre": "Manejo de errores",
      "descripcion": "Validación de entradas y casos borde",
      "puntaje_maximo": 10,
      "niveles": [...]
    }
  ]
}
```

**Validaciones:**
- `puntaje_maximo` debe ser 100
- La suma de `puntaje_maximo` de todos los criterios debe ser 100
- Cada criterio debe tener `id`, `nombre`, `puntaje_maximo`
- `niveles` es opcional pero recomendado

---

### 4.2 criterios_json (Corrección)

Estructura con la evaluación de cada criterio:

```json
{
  "criterios": [
    {
      "id": "c1",
      "nombre": "Funcionalidad correcta",
      "puntaje_obtenido": 35,
      "puntaje_maximo": 40,
      "estado": "WARNING",
      "feedback": "Error en el manejo de lista vacía. El resto de las funciones operan correctamente. Se recomienda agregar validación para este caso borde."
    },
    {
      "id": "c2",
      "nombre": "Uso correcto de listas",
      "puntaje_obtenido": 30,
      "puntaje_maximo": 30,
      "estado": "OK",
      "feedback": "Excelente uso de list comprehensions y métodos de lista. Demuestra buen dominio del tema."
    },
    {
      "id": "c3",
      "nombre": "Estilo y legibilidad",
      "puntaje_obtenido": 15,
      "puntaje_maximo": 20,
      "estado": "WARNING",
      "feedback": "Código generalmente legible pero algunos nombres de variables podrían ser más descriptivos."
    },
    {
      "id": "c4",
      "nombre": "Manejo de errores",
      "puntaje_obtenido": 5,
      "puntaje_maximo": 10,
      "estado": "ERROR",
      "feedback": "Falta validación de entrada. El programa puede fallar con datos inesperados."
    }
  ]
}
```

**Estados posibles:**
- `OK` - Criterio cumplido satisfactoriamente (verde)
- `WARNING` - Criterio con observaciones menores (amarillo)
- `ERROR` - Criterio con problemas significativos (rojo)

---

### 4.3 raw_response (Respuesta de IA)

Se guarda la respuesta completa de Gemini para auditoría y debugging:

```json
{
  "model": "gemini-3.5-flash",
  "timestamp": "2026-01-15T10:30:00Z",
  "prompt_tokens": 1500,
  "completion_tokens": 800,
  "response": {
    "nota": 85,
    "criterios": [...],
    "fortalezas": [...],
    "recomendaciones": [...],
    "comentario_general": "..."
  },
  "raw_text": "... respuesta original en texto ..."
}
```

---

## 5. Índices y Optimización

### 5.1 Índices Principales

| Tabla | Índice | Columnas | Tipo |
|-------|--------|----------|------|
| usuarios | ix_usuario_username | username | Unique |
| usuarios | ix_usuario_rol | rol | Normal |
| materias | ix_materia_codigo | codigo | Unique |
| comisiones | uq_comision_materia_nombre_anio | materia_id, nombre, anio | Unique |
| rubricas | uq_rubrica_materia_tipo_numero_anio | materia_id, tipo, numero, anio | Unique |
| entregas | uq_entrega_rubrica_alumno_activo | rubrica_id, alumno_nombre | Partial Unique (activo=true) |
| entregas | ix_entrega_comision_rubrica | comision_id, rubrica_id | Composite |
| entregas | ix_entrega_estado | estado | Normal |
| correcciones | entrega_id | entrega_id | Unique |

### 5.2 Consultas Frecuentes Optimizadas

```sql
-- Entregas de una comisión/rúbrica con corrección
SELECT e.*, c.*
FROM entregas e
LEFT JOIN correcciones c ON e.id = c.entrega_id
WHERE e.comision_id = ? AND e.rubrica_id = ? AND e.activo = true
ORDER BY e.alumno_nombre;

-- Comisiones de un tutor
SELECT c.*
FROM comisiones c
JOIN comision_tutor ct ON c.id = ct.comision_id
WHERE ct.tutor_id = ? AND c.activa = true;

-- Materias de un coordinador
SELECT m.*
FROM materias m
JOIN coordinador_materia cm ON m.id = cm.materia_id
WHERE cm.coordinador_id = ? AND m.activa = true;
```

---

## 6. Migraciones con Alembic

### 6.1 Estructura de Migraciones

```
alembic/
├── versions/
│   ├── 001_initial_schema.py
│   ├── 002_add_entrega_historial.py
│   └── ...
├── env.py
└── script.py.mako
```

### 6.2 Ejemplo de Migración Inicial

```python
"""Initial schema

Revision ID: 001
Create Date: 2026-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None

def upgrade():
    # Crear enum types
    op.execute("CREATE TYPE rol_enum AS ENUM ('ADMIN', 'COORDINADOR', 'TUTOR')")
    op.execute("CREATE TYPE tipo_rubrica_enum AS ENUM ('TP', 'PARCIAL_1', 'PARCIAL_2', 'RECUPERATORIO_1', 'RECUPERATORIO_2', 'FINAL', 'GLOBAL')")
    op.execute("CREATE TYPE estado_entrega_enum AS ENUM ('SUBIDA', 'PENDIENTE', 'CORREGIDA', 'ERROR')")
    op.execute("CREATE TYPE fuente_rubrica_enum AS ENUM ('manual', 'pdf')")

    # Crear tablas
    op.create_table('usuarios', ...)
    op.create_table('materias', ...)
    # ... resto de tablas

def downgrade():
    # Eliminar tablas en orden inverso
    op.drop_table('correcciones')
    op.drop_table('entregas')
    # ... resto

    # Eliminar enum types
    op.execute("DROP TYPE estado_entrega_enum")
    # ...
```

---

## 7. Datos Iniciales (Seeding)

### 7.1 Usuario Admin Inicial

```python
async def create_initial_admin(db: AsyncSession):
    admin = Usuario(
        username="admin",
        nombre="Administrador del Sistema",
        password_hash=get_password_hash("admin123"),  # Cambiar en producción
        rol=RolEnum.ADMIN,
        primer_login=True,
        activo=True
    )
    db.add(admin)
    await db.commit()
```

### 7.2 Tipos de Rúbrica

Los tipos de rúbrica están definidos como Enum en el código, no en base de datos:

```python
# No se necesita tabla, es un Enum
TipoRubricaEnum = {
    "TP": "Trabajo Práctico",
    "PARCIAL_1": "Parcial 1",
    "PARCIAL_2": "Parcial 2",
    "RECUPERATORIO_1": "Recuperatorio 1",
    "RECUPERATORIO_2": "Recuperatorio 2",
    "FINAL": "Final",
    "GLOBAL": "Global"
}
```

---

## 8. Resumen de Decisiones

| Aspecto | Decisión |
|---------|----------|
| **Base de datos** | PostgreSQL 15+ con SQLAlchemy 2.0 |
| **Historial de correcciones** | NO para re-corrección, SÍ para sobrescritura (EntregaHistorial) |
| **Metadata de entrega** | Básica (nombre, tamaño, tipo, fecha, hash) |
| **Tipos de rúbrica** | Enum fijo en código (7 tipos) |
| **Respuesta IA** | Guardada en campo `raw_response` (JSONB) |
| **Soft delete** | Campo `activo` en entidades principales |
| **Relación Entrega-Corrección** | 1:1 (una corrección por entrega) |
| **Arrays en PostgreSQL** | Usar ARRAY nativo para fortalezas/recomendaciones |
| **JSON** | Usar JSONB para criterios y respuestas |

---

## 9. Próximos Pasos

Este documento define el modelo de datos. Los siguientes documentos detallarán:

- **07-DISENO-UI-UX.md**: Navegación, wireframes, flujos de pantallas
- **08-SISTEMA-DISENO-ESTILOS.md**: Variables CSS, componentes, tooltips

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
