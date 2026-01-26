# 14. Glosario y Referencias

## Introducción

Este documento proporciona definiciones de términos técnicos utilizados en la especificación del sistema de corrección automática, así como referencias a documentación externa relevante para el desarrollo del proyecto.

---

## Glosario de Términos

### A

**Accesibilidad (Accessibility)**
Práctica de diseñar software que pueda ser utilizado por personas con diversas capacidades, incluyendo discapacidades visuales, auditivas, motoras o cognitivas. Ver `12-ACCESIBILIDAD.md`.

**Admin (Administrador)**
Rol de usuario con máximos privilegios en el sistema. Responsable de gestionar usuarios, materias, comisiones y configuración general. Ver `02-USUARIOS-ROLES.md`.

**Alembic**
Herramienta de migración de bases de datos para SQLAlchemy. Permite versionar y aplicar cambios en el esquema de la base de datos de forma controlada.

**API (Application Programming Interface)**
Interfaz que permite la comunicación entre el frontend y el backend mediante endpoints HTTP. En este proyecto, implementada con FastAPI.

**API Key**
Clave de autenticación para servicios externos. En este proyecto, cada usuario tiene su propia API Key de Google Gemini, almacenada encriptada en la base de datos.

**ARIA (Accessible Rich Internet Applications)**
Conjunto de atributos HTML que mejoran la accesibilidad de aplicaciones web para usuarios de lectores de pantalla. Ejemplos: `aria-label`, `aria-describedby`, `aria-live`.

### B

**Backend**
Capa del servidor que maneja la lógica de negocio, acceso a datos y comunicación con servicios externos. Implementado con FastAPI (Python).

**Backup**
Copia de seguridad de datos críticos. En este proyecto, se respaldan archivos de entregas y correcciones de forma automática.

**Badge**
Componente visual que muestra información de estado de forma compacta (ej: "Pendiente", "Corregida", "Fallida").

**Bcrypt**
Algoritmo de hash criptográfico utilizado para almacenar contraseñas de forma segura en la base de datos.

**Bridge Network**
Tipo de red Docker que permite la comunicación entre contenedores en el mismo host.

### C

**Clean Architecture**
Patrón arquitectónico que separa la lógica de negocio de los detalles de implementación mediante capas (Routers → Services → Repositories).

**Comisión**
Grupo de alumnos de una materia específica en un año académico determinado. Cada comisión tiene tutores asignados.

**Consolidación**
Proceso de combinar múltiples archivos de código de un alumno en un único archivo para facilitar la corrección. Soporta diferentes modos (extensiones, carpetas, tags personalizados).

**Coordinador**
Rol de usuario que gestiona rúbricas y comisiones de sus materias asignadas. Supervisa el trabajo de los tutores pero no corrige directamente.

**CORS (Cross-Origin Resource Sharing)**
Mecanismo de seguridad que controla qué dominios pueden acceder a la API del backend desde el navegador.

**Criterio**
Elemento individual de evaluación dentro de una rúbrica. Cada criterio tiene un nombre, descripción, puntaje máximo y estado de cumplimiento.

**CSP (Content Security Policy)**
Header HTTP de seguridad que previene ataques XSS especificando qué recursos pueden cargarse en la página.

### D

**DATABASE_URL**
Variable de entorno que contiene la cadena de conexión a PostgreSQL. Formato: `postgresql://user:password@host:port/database`.

**Dependency Injection**
Patrón de diseño que permite inyectar dependencias (como conexiones a BD) en funciones y clases. En FastAPI se usa `Depends()`.

**Docker**
Plataforma de contenedores que permite empaquetar aplicaciones con todas sus dependencias en imágenes portables.

**Docker Compose**
Herramienta para definir y ejecutar aplicaciones Docker multi-contenedor mediante archivos YAML.

**Dockerfile**
Archivo de texto que contiene instrucciones para construir una imagen Docker.

### E

**Encriptación**
Proceso de convertir datos legibles en formato cifrado. En este proyecto se usa AES-256/Fernet para encriptar API Keys de Gemini.

**Entrega (Submission)**
Archivo ZIP subido por un tutor que contiene el código de un alumno para ser corregido.

**Enum (Enumeración)**
Tipo de dato que define un conjunto fijo de valores posibles. Ejemplo: `TipoRubrica` (TP, PARCIAL_1, PARCIAL_2, etc.).

**ESLint**
Herramienta de linting para JavaScript/TypeScript que identifica problemas de código y aplica convenciones de estilo.

### F

**FastAPI**
Framework web moderno de Python para construir APIs REST de alto rendimiento con validación automática de datos.

**Fernet**
Esquema de encriptación simétrica de Python (parte de cryptography) que implementa AES-256 en modo CBC.

**Frontend**
Capa de presentación de la aplicación que corre en el navegador del usuario. Implementada con React y TypeScript.

**Fortalezas (Strengths)**
Lista de aspectos positivos identificados por la IA en el código del alumno durante la corrección.

### G

**Gemini**
Modelo de inteligencia artificial de Google utilizado para la corrección automática de código. Específicamente se usa `gemini-2.0-flash`.

**Gzip**
Algoritmo de compresión utilizado por Nginx para reducir el tamaño de archivos transferidos al navegador.

### H

**Hash**
Función criptográfica que convierte datos de entrada en una cadena de longitud fija. Se usa SHA-256 para identificar archivos únicos.

**Health Check**
Endpoint o comando que verifica si un servicio está funcionando correctamente. Usado por Docker para monitorear contenedores.

**Hot Reload**
Funcionalidad de desarrollo que recarga automáticamente la aplicación cuando se detectan cambios en el código.

### I

**Indicador de Criterio**
Estado visual que muestra el cumplimiento de un criterio en una corrección. Tres estados: OK (verde), WARNING (amarillo), ERROR (rojo).

### J

**JSON (JavaScript Object Notation)**
Formato de intercambio de datos basado en texto. Usado para almacenar criterios de rúbricas, respuestas de IA y configuración.

**JSONB**
Tipo de dato de PostgreSQL para almacenar JSON de forma binaria, permitiendo consultas eficientes.

**JWT (JSON Web Token)**
Estándar para crear tokens de acceso que permiten autenticación sin estado. Expiran en 7 días por defecto.

### L

**Lint / Linting**
Proceso de análisis estático de código para identificar errores, bugs potenciales y violaciones de estilo.

**LOC (Lines of Code)**
Métrica que cuenta líneas de código. En este proyecto hay un límite de 500 LOC por archivo/clase.

**Logs**
Registros de eventos del sistema (logins, errores, correcciones, etc.) que facilitan debugging y auditoría.

**Lucide React**
Biblioteca de iconos SVG para React, utilizada como sistema de iconografía del proyecto.

### M

**Materia**
Asignatura académica (ej: "Programación I"). Contiene comisiones y rúbricas asociadas.

**Migración (Migration)**
Script que modifica el esquema de la base de datos (crear tablas, agregar columnas, etc.). Gestionadas con Alembic.

**Modal**
Componente UI que muestra contenido en una ventana superpuesta que requiere interacción del usuario antes de continuar.

**Multi-stage Build**
Técnica de Docker que usa múltiples etapas en un Dockerfile para optimizar el tamaño de la imagen final.

### N

**N8N**
Plataforma de automatización de workflows de código abierto. Actúa como intermediario entre el backend y Google Gemini.

**Nginx**
Servidor web y proxy reverso de alto rendimiento. Usado para servir el frontend y como proxy al backend.

**Node (Nodo)**
En el contexto de código, se refiere a elementos como clases, funciones o métodos que pueden ser visualizados individualmente.

### O

**OKLCH**
Espacio de color perceptualmente uniforme utilizado en el sistema de diseño para garantizar consistencia visual.

**ORM (Object-Relational Mapping)**
Técnica que permite interactuar con la base de datos usando objetos en lugar de SQL directo. Se usa SQLAlchemy.

### P

**Paginación**
Técnica para dividir grandes conjuntos de datos en páginas más pequeñas, mejorando el rendimiento y la experiencia de usuario.

**PDF (Portable Document Format)**
Formato de archivo para documentos. El sistema genera PDFs de correcciones usando ReportLab.

**PostgreSQL**
Sistema de gestión de bases de datos relacional de código abierto. Base de datos principal del proyecto.

**Prompt**
Instrucciones en lenguaje natural enviadas a un modelo de IA para guiar su comportamiento. Ver `10-INTEGRACIONES.md`.

**Proxy Reverso**
Servidor que recibe peticiones de clientes y las reenvía a otros servidores. Nginx actúa como proxy reverso al backend.

**Pydantic**
Biblioteca de Python para validación de datos usando type hints. Integrada en FastAPI para validar requests/responses.

### R

**Rate Limiting**
Técnica de seguridad que limita el número de peticiones que un usuario o IP puede hacer en un período de tiempo.

**React**
Biblioteca de JavaScript para construir interfaces de usuario mediante componentes reutilizables.

**Recomendaciones (Recommendations)**
Lista de sugerencias de mejora generadas por la IA para el código del alumno durante la corrección.

**ReportLab**
Biblioteca de Python para generar documentos PDF programáticamente.

**Repository (Repositorio)**
Capa de la arquitectura que maneja toda la interacción con la base de datos. Parte del patrón Clean Architecture.

**REST (Representational State Transfer)**
Estilo arquitectónico para diseñar APIs web usando HTTP y operaciones CRUD (GET, POST, PUT, DELETE).

**Rúbrica**
Documento que define criterios de evaluación y puntajes para un tipo de trabajo práctico específico.

**Ruff**
Linter extremadamente rápido para Python que reemplaza múltiples herramientas (Flake8, isort, etc.).

### S

**Service (Servicio)**
Capa de la arquitectura que contiene la lógica de negocio pura. Parte del patrón Clean Architecture.

**SHA-256**
Algoritmo de hash criptográfico que genera un identificador único de 256 bits para archivos.

**Sidebar**
Barra lateral de navegación fija que contiene el menú principal de la aplicación.

**Skip Link**
Enlace invisible que permite a usuarios de teclado/lectores de pantalla saltar directamente al contenido principal.

**SPA (Single Page Application)**
Aplicación web que carga una sola página HTML y actualiza dinámicamente el contenido sin recargar la página.

**SQLAlchemy**
ORM de Python más popular, utilizado para interactuar con PostgreSQL de forma orientada a objetos.

**SSL/TLS**
Protocolos de seguridad que cifran la comunicación entre cliente y servidor (HTTPS).

### T

**Tailwind CSS**
Framework de CSS basado en clases utilitarias para construir interfaces de usuario rápidamente.

**Toast**
Notificación temporal que aparece en la pantalla para informar al usuario sobre eventos (éxito, error, info).

**Token**
Cadena de caracteres que representa credenciales de autenticación. En este proyecto se usan JWT.

**Tooltip**
Pequeño mensaje informativo que aparece al pasar el cursor sobre un elemento UI.

**TooltipIcon**
Componente personalizado que muestra un icono `(?)` con un tooltip explicativo al hacer hover.

**tRPC**
Biblioteca TypeScript para crear APIs type-safe entre cliente y servidor. No se usa en este proyecto (se usa REST).

**Tutor**
Rol de usuario que corrige entregas de alumnos en las comisiones asignadas. Típicamente estudiantes avanzados.

**TypeScript**
Superset de JavaScript que agrega tipado estático, mejorando la detección de errores y el autocompletado.

### U

**Upload**
Proceso de subir archivos al servidor. En este proyecto, tutores suben ZIPs de entregas.

**Uvicorn**
Servidor ASGI de alto rendimiento para aplicaciones Python asíncronas como FastAPI.

### V

**Validación**
Proceso de verificar que los datos cumplan con reglas específicas antes de procesarlos o almacenarlos.

**Variables de Entorno**
Valores de configuración que se pasan a la aplicación desde el entorno de ejecución (archivo `.env`).

**Vite**
Herramienta de build moderna para aplicaciones frontend que ofrece hot reload instantáneo y builds optimizados.

**Volumen Docker**
Mecanismo de persistencia de datos en Docker que sobrevive al ciclo de vida de los contenedores.

### W

**WCAG (Web Content Accessibility Guidelines)**
Estándares internacionales para hacer contenido web accesible. Este proyecto cumple WCAG 2.1 nivel AA.

**Webhook**
Endpoint HTTP que recibe notificaciones automáticas cuando ocurre un evento. N8N expone webhooks para corrección.

**Workflow**
Flujo de trabajo automatizado en N8N que define una secuencia de pasos para completar una tarea.

### X

**XSS (Cross-Site Scripting)**
Vulnerabilidad de seguridad donde un atacante inyecta scripts maliciosos en páginas web. Prevenido con CSP y validación.

### Z

**ZIP**
Formato de archivo comprimido. Los tutores suben entregas como archivos ZIP que contienen el código del alumno.

---

## Referencias Técnicas

### Documentación Oficial

#### Backend y Base de Datos

- **FastAPI**: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
  - Framework web principal del backend
  - Documentación completa de endpoints, validación, dependency injection

- **SQLAlchemy**: [https://docs.sqlalchemy.org/](https://docs.sqlalchemy.org/)
  - ORM para PostgreSQL
  - Guías de modelos, relaciones, queries

- **Alembic**: [https://alembic.sqlalchemy.org/](https://alembic.sqlalchemy.org/)
  - Migraciones de base de datos
  - Tutorial de creación y aplicación de migraciones

- **PostgreSQL**: [https://www.postgresql.org/docs/](https://www.postgresql.org/docs/)
  - Base de datos relacional
  - Referencia de tipos de datos, índices, performance

- **Pydantic**: [https://docs.pydantic.dev/](https://docs.pydantic.dev/)
  - Validación de datos con type hints
  - Schemas y modelos de validación

- **ReportLab**: [https://www.reportlab.com/docs/reportlab-userguide.pdf](https://www.reportlab.com/docs/reportlab-userguide.pdf)
  - Generación de PDFs
  - Guía de layouts, estilos, tablas

#### Frontend

- **React**: [https://react.dev/](https://react.dev/)
  - Biblioteca UI principal
  - Documentación de hooks, componentes, best practices

- **TypeScript**: [https://www.typescriptlang.org/docs/](https://www.typescriptlang.org/docs/)
  - Lenguaje tipado para JavaScript
  - Handbook completo de tipos y patrones

- **Vite**: [https://vitejs.dev/](https://vitejs.dev/)
  - Build tool y dev server
  - Configuración, plugins, optimización

- **Tailwind CSS**: [https://tailwindcss.com/docs](https://tailwindcss.com/docs)
  - Framework CSS utilitario
  - Referencia completa de clases, customización

- **Lucide React**: [https://lucide.dev/](https://lucide.dev/)
  - Biblioteca de iconos
  - Catálogo completo de iconos disponibles

#### Integraciones

- **N8N**: [https://docs.n8n.io/](https://docs.n8n.io/)
  - Plataforma de automatización
  - Guías de workflows, webhooks, credenciales

- **Google Gemini API**: [https://ai.google.dev/docs](https://ai.google.dev/docs)
  - API de inteligencia artificial
  - Referencia de modelos, prompts, parámetros

#### Infraestructura

- **Docker**: [https://docs.docker.com/](https://docs.docker.com/)
  - Plataforma de contenedores
  - Dockerfile reference, best practices

- **Docker Compose**: [https://docs.docker.com/compose/](https://docs.docker.com/compose/)
  - Orquestación de contenedores
  - Sintaxis de compose files, networking, volumes

- **Nginx**: [https://nginx.org/en/docs/](https://nginx.org/en/docs/)
  - Servidor web y proxy reverso
  - Configuración, performance tuning, security

#### Seguridad

- **OWASP Top 10**: [https://owasp.org/www-project-top-ten/](https://owasp.org/www-project-top-ten/)
  - Principales riesgos de seguridad web
  - Guías de prevención y mitigación

- **JWT.io**: [https://jwt.io/](https://jwt.io/)
  - Introducción a JSON Web Tokens
  - Debugger y bibliotecas

- **Cryptography (Python)**: [https://cryptography.io/](https://cryptography.io/)
  - Biblioteca de criptografía
  - Fernet, hashing, encriptación

#### Accesibilidad

- **WCAG 2.1**: [https://www.w3.org/WAI/WCAG21/quickref/](https://www.w3.org/WAI/WCAG21/quickref/)
  - Guía rápida de criterios de accesibilidad
  - Técnicas y ejemplos de implementación

- **WAI-ARIA**: [https://www.w3.org/WAI/ARIA/apg/](https://www.w3.org/WAI/ARIA/apg/)
  - Patrones de diseño accesibles
  - Ejemplos de componentes con ARIA

- **axe DevTools**: [https://www.deque.com/axe/devtools/](https://www.deque.com/axe/devtools/)
  - Herramienta de testing de accesibilidad
  - Extensión de navegador para auditorías

---

## Herramientas de Desarrollo

### Linting y Formateo

- **Ruff**: [https://docs.astral.sh/ruff/](https://docs.astral.sh/ruff/)
  - Linter y formateador para Python
  - Configuración recomendada en `09-PATRONES-CODIGO.md`

- **Black**: [https://black.readthedocs.io/](https://black.readthedocs.io/)
  - Formateador de código Python
  - Estilo consistente y sin configuración

- **ESLint**: [https://eslint.org/docs/](https://eslint.org/docs/)
  - Linter para JavaScript/TypeScript
  - Reglas y plugins recomendados

- **Prettier**: [https://prettier.io/docs/](https://prettier.io/docs/)
  - Formateador de código para frontend
  - Integración con ESLint

### Testing

- **pytest**: [https://docs.pytest.org/](https://docs.pytest.org/)
  - Framework de testing para Python
  - Fixtures, parametrización, coverage

- **pytest-asyncio**: [https://pytest-asyncio.readthedocs.io/](https://pytest-asyncio.readthedocs.io/)
  - Testing de código asíncrono en Python
  - Necesario para tests de FastAPI

- **Vitest**: [https://vitest.dev/](https://vitest.dev/)
  - Framework de testing para Vite/React
  - Compatible con Jest, más rápido

- **React Testing Library**: [https://testing-library.com/react](https://testing-library.com/react)
  - Testing de componentes React
  - Enfoque en comportamiento de usuario

### Control de Versiones

- **Git**: [https://git-scm.com/doc](https://git-scm.com/doc)
  - Sistema de control de versiones
  - Comandos, workflows, best practices

- **Conventional Commits**: [https://www.conventionalcommits.org/](https://www.conventionalcommits.org/)
  - Convención para mensajes de commit
  - Formato: `type(scope): description`

---

## Recursos Adicionales

### Patrones de Diseño

- **Clean Architecture**: [https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
  - Artículo original de Robert C. Martin
  - Principios de separación de capas

- **Repository Pattern**: [https://martinfowler.com/eaaCatalog/repository.html](https://martinfowler.com/eaaCatalog/repository.html)
  - Patrón para abstracción de persistencia
  - Por Martin Fowler

### Performance

- **Web.dev**: [https://web.dev/](https://web.dev/)
  - Guías de Google sobre performance web
  - Core Web Vitals, optimización de imágenes

- **PostgreSQL Performance**: [https://wiki.postgresql.org/wiki/Performance_Optimization](https://wiki.postgresql.org/wiki/Performance_Optimization)
  - Optimización de queries
  - Índices, EXPLAIN, tuning

### UI/UX

- **Material Design**: [https://m3.material.io/](https://m3.material.io/)
  - Sistema de diseño de Google
  - Inspiración para componentes y patrones

- **Laws of UX**: [https://lawsofux.com/](https://lawsofux.com/)
  - Principios psicológicos aplicados a UX
  - Guías de usabilidad

### Comunidades y Soporte

- **Stack Overflow**: [https://stackoverflow.com/](https://stackoverflow.com/)
  - Preguntas y respuestas técnicas
  - Tags relevantes: `fastapi`, `react`, `postgresql`, `docker`

- **GitHub Discussions**: Repositorios oficiales de las tecnologías
  - Discusiones sobre features, bugs, best practices

- **Discord/Slack**: Comunidades oficiales
  - FastAPI Discord
  - Reactiflux (React)
  - N8N Community

---

## Estándares y Convenciones

### Código

- **PEP 8**: [https://peps.python.org/pep-0008/](https://peps.python.org/pep-0008/)
  - Guía de estilo para código Python
  - Naming, indentación, imports

- **PEP 257**: [https://peps.python.org/pep-0257/](https://peps.python.org/pep-0257/)
  - Convenciones para docstrings en Python
  - Formato y contenido

- **Google Python Style Guide**: [https://google.github.io/styleguide/pyguide.html](https://google.github.io/styleguide/pyguide.html)
  - Guía de estilo de Google para Python
  - Docstrings, type hints, best practices

- **Airbnb JavaScript Style Guide**: [https://github.com/airbnb/javascript](https://github.com/airbnb/javascript)
  - Guía de estilo para JavaScript/React
  - Convenciones ampliamente adoptadas

### REST API

- **REST API Design**: [https://restfulapi.net/](https://restfulapi.net/)
  - Best practices para diseño de APIs
  - Naming, HTTP methods, status codes

- **OpenAPI Specification**: [https://swagger.io/specification/](https://swagger.io/specification/)
  - Estándar para documentar APIs REST
  - FastAPI genera automáticamente OpenAPI docs

### Seguridad

- **OWASP Cheat Sheets**: [https://cheatsheetseries.owasp.org/](https://cheatsheetseries.owasp.org/)
  - Guías rápidas de seguridad
  - Authentication, SQL Injection, XSS, CSRF

- **Security Headers**: [https://securityheaders.com/](https://securityheaders.com/)
  - Verificador de headers de seguridad
  - Recomendaciones de configuración

---

## Archivos de Especificación del Proyecto

Esta especificación está dividida en 14 documentos. A continuación, la referencia completa:

### Fase 1: Fundamentos

1. **[01-VISION-OBJETIVOS.md](./01-VISION-OBJETIVOS.md)**
   - Problema que resuelve el sistema
   - Propuesta de valor
   - Alcance y limitaciones
   - Qué SÍ y qué NO incluye

2. **[02-USUARIOS-ROLES.md](./02-USUARIOS-ROLES.md)**
   - User personas (Admin, Coordinador, Tutor)
   - Roles y permisos
   - Flujos de usuario por rol
   - Relaciones entre usuarios y entidades

### Fase 2: Requisitos

3. **[03-REQUISITOS-FUNCIONALES.md](./03-REQUISITOS-FUNCIONALES.md)**
   - Historias de usuario
   - Módulos del sistema
   - Funcionalidades detalladas
   - Casos de uso

4. **[04-REQUISITOS-NO-FUNCIONALES.md](./04-REQUISITOS-NO-FUNCIONALES.md)**
   - Rendimiento y escalabilidad
   - Restricciones técnicas
   - Capacidad del sistema
   - Tiempos de respuesta

### Fase 3: Arquitectura y Datos

5. **[05-ARQUITECTURA-STACK.md](./05-ARQUITECTURA-STACK.md)**
   - Stack tecnológico completo
   - Justificación de tecnologías
   - Diagramas de arquitectura
   - Estructura de carpetas

6. **[06-MODELO-DATOS.md](./06-MODELO-DATOS.md)**
   - Entidades y relaciones
   - Esquema de base de datos
   - Estructuras JSON
   - Índices y constraints

### Fase 4: Diseño y Experiencia

7. **[07-DISENO-UI-UX.md](./07-DISENO-UI-UX.md)**
   - Navegación y layout
   - Wireframes de pantallas
   - Flujos de interacción
   - Responsive design

8. **[08-SISTEMA-DISENO-ESTILOS.md](./08-SISTEMA-DISENO-ESTILOS.md)**
   - Variables CSS y tokens
   - Componentes base
   - Tooltips y jerarquía visual
   - Temas claro/oscuro

### Fase 5: Desarrollo

9. **[09-PATRONES-CODIGO.md](./09-PATRONES-CODIGO.md)**
   - Clean Architecture
   - Estructura de carpetas
   - Convenciones de código
   - Buenas prácticas
   - Límites de LOC

### Fase 6: Integraciones y Seguridad

10. **[10-INTEGRACIONES.md](./10-INTEGRACIONES.md)**
    - Integración con Google Gemini
    - Workflows de N8N
    - Prompts de IA
    - Manejo de errores

11. **[11-SEGURIDAD.md](./11-SEGURIDAD.md)**
    - Autenticación y autorización
    - Encriptación de datos
    - Validaciones
    - Auditoría y logs

### Fase 7: Infraestructura y Cierre

12. **[12-ACCESIBILIDAD.md](./12-ACCESIBILIDAD.md)**
    - Cumplimiento WCAG 2.1 AA
    - Navegación por teclado
    - Screen readers
    - Contraste y temas

13. **[13-INFRAESTRUCTURA-DEPLOY.md](./13-INFRAESTRUCTURA-DEPLOY.md)**
    - Docker y Docker Compose
    - Ambientes (desarrollo/producción)
    - Volúmenes y persistencia
    - Procedimientos de deploy
    - Backups y migraciones

14. **[14-GLOSARIO-REFERENCIAS.md](./14-GLOSARIO-REFERENCIAS.md)** (este documento)
    - Definiciones de términos técnicos
    - Referencias a documentación externa
    - Herramientas de desarrollo

---

## Cómo Usar Esta Especificación

### Para Desarrolladores

1. **Inicio del proyecto**: Leer `01-VISION-OBJETIVOS.md` para entender el contexto
2. **Setup técnico**: Seguir `05-ARQUITECTURA-STACK.md` y `13-INFRAESTRUCTURA-DEPLOY.md`
3. **Desarrollo de features**: Consultar documentos específicos según el área:
   - Backend: `06-MODELO-DATOS.md`, `09-PATRONES-CODIGO.md`, `10-INTEGRACIONES.md`
   - Frontend: `07-DISENO-UI-UX.md`, `08-SISTEMA-DISENO-ESTILOS.md`, `12-ACCESIBILIDAD.md`
   - Seguridad: `11-SEGURIDAD.md`
4. **Dudas de términos**: Consultar este glosario

### Para Diseñadores

1. **Entender usuarios**: Leer `02-USUARIOS-ROLES.md`
2. **Diseño visual**: Seguir `08-SISTEMA-DISENO-ESTILOS.md`
3. **Flujos de usuario**: Consultar `07-DISENO-UI-UX.md`
4. **Accesibilidad**: Cumplir `12-ACCESIBILIDAD.md`

### Para Product Managers

1. **Visión del producto**: `01-VISION-OBJETIVOS.md`
2. **Funcionalidades**: `03-REQUISITOS-FUNCIONALES.md`
3. **Limitaciones técnicas**: `04-REQUISITOS-NO-FUNCIONALES.md`
4. **Usuarios objetivo**: `02-USUARIOS-ROLES.md`

### Para QA/Testers

1. **Casos de prueba**: Derivar de `03-REQUISITOS-FUNCIONALES.md`
2. **Requisitos no funcionales**: Validar según `04-REQUISITOS-NO-FUNCIONALES.md`
3. **Seguridad**: Verificar `11-SEGURIDAD.md`
4. **Accesibilidad**: Auditar según `12-ACCESIBILIDAD.md`

---

## Mantenimiento de la Especificación

### Actualización de Documentos

Cuando se realicen cambios significativos al proyecto:

1. **Identificar documentos afectados**: Determinar qué partes de la especificación necesitan actualizarse
2. **Actualizar contenido**: Modificar los archivos `.md` correspondientes
3. **Mantener consistencia**: Asegurar que los cambios se reflejen en todos los documentos relacionados
4. **Documentar decisiones**: Agregar notas sobre por qué se hizo el cambio

### Versionado

- La especificación debe versionarse junto con el código
- Usar tags de Git para marcar versiones importantes
- Mantener un CHANGELOG.md con cambios significativos

### Revisión Periódica

- Revisar la especificación cada 3-6 meses
- Actualizar referencias a documentación externa si cambian URLs
- Verificar que las tecnologías sigan siendo las recomendadas

---

## Conclusión

Este glosario y conjunto de referencias proporciona:

✅ **Definiciones claras** de todos los términos técnicos usados en la especificación  
✅ **Enlaces directos** a documentación oficial de todas las tecnologías  
✅ **Recursos adicionales** para profundizar en temas específicos  
✅ **Guía de uso** de la especificación según el rol

La especificación completa en sus 14 partes constituye una base sólida para desarrollar el sistema de corrección automática desde cero, manteniendo consistencia, calidad y alineación con los objetivos del proyecto.

---

**Fin de la Especificación del Proyecto de Corrección Automática**

_Versión: 1.0_  
_Fecha: Enero 2026_  
_Autores: Equipo de Desarrollo TUD_
