# Documentacion - Active-IA

> Indice de toda la documentacion del proyecto.

---

## Especificaciones del Proyecto

Ubicacion: `docs/specs/`

| # | Documento | Descripcion | Consultar cuando... |
|---|-----------|-------------|---------------------|
| 01 | [Vision y Objetivos](specs/01-VISION-OBJETIVOS.md) | Proposito, alcance, metricas de exito | Necesites entender el "por que" del proyecto |
| 02 | [Usuarios y Roles](specs/02-USUARIOS-ROLES.md) | Perfiles, permisos, matriz de acceso | Implementes validacion de permisos |
| 03 | [Requisitos Funcionales](specs/03-REQUISITOS-FUNCIONALES.md) | 10 modulos con historias de usuario | Necesites saber QUE hace cada funcionalidad |
| 04 | [Requisitos No Funcionales](specs/04-REQUISITOS-NO-FUNCIONALES.md) | Rendimiento, seguridad, limites | Definas timeouts, limites de archivo, etc. |
| 05 | [Arquitectura y Stack](specs/05-ARQUITECTURA-STACK.md) | Tecnologias, diagramas, decisiones | Elijas tecnologias o estructures codigo |
| 06 | [Modelo de Datos](specs/06-MODELO-DATOS.md) | 9 entidades, JSON schemas, indices | Crees/modifiques modelos SQLAlchemy |
| 07 | [Diseno UI/UX](specs/07-DISENO-UI-UX.md) | Navegacion, wireframes, flujos | Crees componentes o paginas |
| 08 | [Sistema de Diseno](specs/08-SISTEMA-DISENO-ESTILOS.md) | Colores, tipografia, componentes | Estilices componentes con Tailwind |
| 09 | [Patrones de Codigo](specs/09-PATRONES-CODIGO.md) | Estructura, convenciones, ejemplos | Dudes sobre estructura de archivos |
| 10 | [Integraciones](specs/10-INTEGRACIONES.md) | Gemini / OpenRouter (llamada directa), prompts | Implementes correccion IA |
| 11 | [Seguridad](specs/11-SEGURIDAD.md) | Auth, encriptacion, protecciones | Implementes auth o manejo de secrets |
| 12 | [Accesibilidad](specs/12-ACCESIBILIDAD.md) | WCAG, aria, keyboard | Crees componentes UI accesibles |
| 13 | [Infraestructura](specs/13-INFRAESTRUCTURA-DEPLOY.md) | Docker, variables, deploy | Configures entorno o Docker |
| 14 | [Glosario](specs/14-GLOSARIO-REFERENCIAS.md) | Terminos, referencias | No entiendas un termino del dominio |

---

## Skills (Knowledge Base para Agentes)

Ubicacion: `skills/`

| Skill | Descripcion | Usar cuando... |
|-------|-------------|----------------|
| [python-fastapi](../skills/python-fastapi/SKILL.md) | Patrones FastAPI + Clean Architecture | Escribas codigo backend |
| [react-typescript](../skills/react-typescript/SKILL.md) | Patrones React + TypeScript + Tailwind | Escribas codigo frontend |
| [correccion-ia](../skills/correccion-ia/SKILL.md) | Flujo de correccion automatica | Implementes integracion con Gemini |
| [rubricas](../skills/rubricas/SKILL.md) | Gestion de rubricas y criterios | Trabajes con rubricas |

---

## Documentos Operativos

| Documento | Ubicacion | Proposito |
|-----------|-----------|-----------|
| [CLAUDE.md](../CLAUDE.md) | Raiz | Entry point para Claude Code |
| [AGENTS.md](../AGENTS.md) | Raiz | Reglas globales para agentes |
| [backend/AGENTS.md](../backend/AGENTS.md) | Backend | Reglas especificas backend |
| [frontend/AGENTS.md](../frontend/AGENTS.md) | Frontend | Reglas especificas frontend |

---

## Referencia Rapida

### Modelo de Datos (Entidades)

```
Usuario
├── CoordinadorMateria (N:M) ──> Materia
└── ComisionTutor (N:M) ──> Comision ──> Materia
                                │
                                ├── Entrega ──> Correccion
                                │      └── EntregaHistorial
                                └── Rubrica (por materia/anio)
```

### Roles y Permisos

| Permiso | Admin | Coordinador | Tutor |
|---------|:-----:|:-----------:|:-----:|
| Gestionar usuarios | X | - | - |
| Gestionar materias | X | - | - |
| Gestionar comisiones | X | X (sus materias) | - |
| Gestionar rubricas | X | X (sus materias) | Solo lectura |
| Subir entregas | X | X | X (sus comisiones) |
| Corregir con IA | X | - | X (sus comisiones) |
| Editar correcciones | X | - | X (sus comisiones) |
| Generar documentos | X | X | X (sus comisiones) |

### Stack Tecnologico

| Capa | Tecnologia |
|------|------------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Backend | Python 3.11 + FastAPI + SQLAlchemy 2.0 |
| Base de datos | PostgreSQL 15+ |
| Autenticacion | JWT (python-jose) |
| Integracion IA | Google Gemini (AI Studio) + OpenRouter (llamada HTTP directa desde el backend) |
| Deploy | Docker + Docker Compose + Nginx |

---

## Como Navegar la Documentacion

1. **Para entender el proyecto**: Empieza por `01-VISION-OBJETIVOS.md`
2. **Para implementar una feature**: Consulta `03-REQUISITOS-FUNCIONALES.md` + skill correspondiente
3. **Para crear modelos**: Consulta `06-MODELO-DATOS.md`
4. **Para disenar UI**: Consulta `07-DISENO-UI-UX.md` + `08-SISTEMA-DISENO-ESTILOS.md`
5. **Para integracion IA**: Consulta `10-INTEGRACIONES.md` + `skills/correccion-ia/SKILL.md`

---

*Ultima actualizacion: 2026-07-18*
