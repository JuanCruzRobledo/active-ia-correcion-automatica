# 01 - Visión y Objetivos

---

## 1. Definición del Problema

### 1.1 Contexto

La Tecnicatura Universitaria a Distancia (TUD) enfrenta un desafío operativo crítico en la evaluación de trabajos prácticos de programación. Los tutores destinan entre **15 y 30 minutos por entrega** en tareas repetitivas de revisión manual.

### 1.2 Problemas Identificados

| Problema | Descripción | Impacto |
|----------|-------------|---------|
| **Sobrecarga docente** | Un tutor con 2 comisiones de 30 alumnos debe corregir ~60 entregas por TP. Con 6 TPs por cuatrimestre por materia, esto representa 15-30 horas de trabajo repetitivo por TP | Alto |
| **Inconsistencia en evaluaciones** | La fatiga cognitiva y variabilidad humana generan disparidad en calificaciones. Dos entregas equivalentes pueden recibir notas diferentes | Alto |
| **Retroalimentación insuficiente** | La presión temporal obliga a comentarios breves y genéricos, reduciendo el valor pedagógico | Medio |
| **Demoras en resultados** | El tiempo entre entrega y calificación puede extenderse semanas, perdiendo impacto pedagógico | Medio |
| **Dificultad para detectar copias** | Identificar similitudes entre decenas de entregas es prácticamente inviable sin herramientas | Bajo (fase posterior) |

### 1.3 Usuarios Afectados

- **Tutores**: Dedican tiempo excesivo a tareas repetitivas en lugar de actividades pedagógicas de mayor valor
- **Alumnos**: Reciben retroalimentación tardía y/o genérica que no ayuda a su aprendizaje
- **Coordinadores**: Carecen de visibilidad sobre el estado de correcciones y calidad de evaluaciones

---

## 2. Propuesta de Valor

### 2.1 Nombre del Sistema

**Active-IA** - Plataforma de Corrección Automática con Inteligencia Artificial

### 2.2 Propuesta de Valor Única (UVP)

Active-IA es una solución integral que se diferencia mediante:

| Diferenciador | Descripción |
|---------------|-------------|
| **Corrección contextualizada con IA** | Utiliza Google Gemini para comprender el contexto semántico del código, evaluar calidad más allá del funcionamiento técnico, y generar retroalimentación pedagógica |
| **Evaluación basada en rúbricas dinámicas** | Permite definir criterios de evaluación específicos para cada TP, garantizando alineación con objetivos pedagógicos |
| **Generación de rúbricas desde PDF** | Los tutores pueden cargar consignas en PDF y el sistema extrae automáticamente los criterios de evaluación |
| **Simplicidad operativa** | Arquitectura simplificada con solo dos niveles jerárquicos (Materia → Comisión), eliminando complejidad innecesaria |
| **Preservación del control docente** | Toda corrección automática puede ser revisada, modificada y complementada por el tutor |
| **Flexibilidad en prompts** | Integración con N8N permite modificar prompts de IA sin tocar código |

### 2.3 Beneficios Esperados

| Beneficio | Métrica Objetivo |
|-----------|------------------|
| Reducción de tiempo de corrección | De 25 min a menos de 5 min por entrega |
| Consistencia en evaluaciones | Mismos criterios aplicados a todas las entregas |
| Retroalimentación detallada | Feedback específico por criterio, fortalezas y recomendaciones |
| Tiempo de respuesta | Corrección completa en menos de 60 segundos por entrega |

---

## 3. Alcance del Proyecto

### 3.1 Alcance Institucional

| Aspecto | Decisión |
|---------|----------|
| **Institución objetivo** | Tecnicatura Universitaria a Distancia (TUD) |
| **Estrategia** | Diseñar para TUD primero, con arquitectura que permita expandir a futuro |
| **Multi-tenancy** | NO incluido en esta versión. Arquitectura preparada para agregarlo después |

### 3.2 Alcance Funcional - MVP

El MVP (Producto Mínimo Viable) incluye:

| Módulo | Funcionalidades |
|--------|-----------------|
| **Autenticación** | Login, JWT, cambio de contraseña, configuración de API Key Gemini |
| **Gestión académica** | CRUD de materias, comisiones, usuarios |
| **Gestión de rúbricas** | Crear manual, crear desde PDF, editar, duplicar |
| **Gestión de entregas** | Carga individual y masiva, consolidación de código |
| **Corrección automática** | Individual y en lote vía Gemini/N8N |
| **Edición de correcciones** | Modificar cualquier campo de la corrección |
| **Generación de documentos** | PDFs de devolución, descarga masiva, exportar notas a Excel/CSV |
| **Notificaciones** | Indicadores visuales en-app (sin email) |

### 3.3 Alcance Funcional - Fases Posteriores

| Fase | Funcionalidades |
|------|-----------------|
| **Fase 2** | Mejoras UX, filtros avanzados, optimización de rendimiento |
| **Fase 3** | Detección de similitud (copias), reportes de similitud, comparación lado a lado |
| **Fase 4** | Expansión multi-institucional (si se requiere) |

### 3.4 Lenguajes de Programación Soportados

El sistema debe soportar múltiples lenguajes de programación (configurable):

| Lenguaje | Extensiones |
|----------|-------------|
| Python | .py |
| Java | .java |
| JavaScript | .js |
| TypeScript | .ts |
| C/C++ | .c, .cpp, .h |
| Go | .go |
| Otros | Configurable |

---

## 4. Qué SÍ Incluye el Sistema

### 4.1 Funcionalidades Core

| Categoría | Funcionalidad | Descripción |
|-----------|---------------|-------------|
| **Autenticación** | Login seguro | JWT con expiración configurable |
| **Autenticación** | Gestión de API Keys | Cada usuario configura su API Key de Gemini, encriptada con AES-256 |
| **Autenticación** | Primer login forzado | Tutores deben cambiar contraseña provisional |
| **Gestión** | CRUD Materias | Código único, nombre, descripción, soft delete |
| **Gestión** | CRUD Comisiones | Asociadas a materia, año académico, tutores asignados |
| **Gestión** | CRUD Usuarios | Username, nombre, rol, contraseña, soft delete |
| **Rúbricas** | Creación manual | Definir criterios, puntajes, niveles de logro |
| **Rúbricas** | Creación desde PDF | IA extrae criterios de consigna PDF |
| **Rúbricas** | Tipos configurables | TP, Parcial 1, Parcial 2, Recuperatorio, Final, otros |
| **Entregas** | Carga individual | ZIP o TXT de un alumno |
| **Entregas** | Carga masiva | ZIP con carpetas por alumno |
| **Entregas** | Consolidación | Unifica archivos de código en texto único |
| **Corrección** | Automática individual | Envía a Gemini vía N8N, retorna evaluación estructurada |
| **Corrección** | En lote | Procesa todas las pendientes secuencialmente |
| **Corrección** | Edición manual | Modificar nota, puntajes, feedback, fortalezas, recomendaciones |
| **Corrección** | Re-corrección | Generar nueva evaluación con IA descartando anterior |
| **Documentos** | PDF de devolución | Diseño profesional con criterios, indicadores visuales |
| **Documentos** | Descarga masiva PDFs | ZIP con todos los PDFs de un TP |
| **Documentos** | Exportar notas | CSV/Excel con calificaciones |
| **UI** | Notificaciones en-app | Indicadores visuales de progreso y finalización |

### 4.2 Elementos Reutilizados del Proyecto Actual

| Elemento | Descripción |
|----------|-------------|
| **Lógica de consolidación** | Código que une archivos de proyecto en un solo texto para enviar a IA |
| **Generación de PDFs** | Diseño y formato de los PDFs de devolución |
| **Encriptación de API Keys** | Sistema AES-256 para almacenar API Keys de Gemini |

---

## 5. Qué NO Incluye el Sistema

### 5.1 Funcionalidades Excluidas del MVP

| Funcionalidad | Razón de exclusión |
|---------------|-------------------|
| **Multi-tenancy** | No necesario para TUD. Arquitectura preparada para agregarlo después |
| **Consolidador público** | No se requiere herramienta de consolidación sin autenticación |
| **Detección de similitud** | Fase posterior (Fase 3). Priorizar corrección primero |
| **Notificaciones por email** | Solo notificaciones en-app por simplicidad |
| **Roles adicionales** | Solo 3 roles (Admin, Coordinador, Tutor). Sin jerarquías complejas |
| **Jerarquía extendida** | Sin niveles Universidad/Facultad/Carrera. Solo Materia → Comisión |
| **API pública** | Sin endpoints para integraciones externas (por ahora) |
| **Historial de versiones** | Sin versionado de correcciones (fase posterior) |
| **Dashboard de analytics** | Sin reportes estadísticos avanzados |
| **Modo offline** | Requiere conexión a internet |

### 5.2 Decisiones de Diseño Explícitas

| Decisión | Justificación |
|----------|---------------|
| **PostgreSQL sobre MongoDB** | Mejor para datos estructurados con relaciones claras |
| **N8N como intermediario** | Permite modificar prompts de IA sin redeployear código |
| **2 niveles jerárquicos** | Simplicidad. Materia → Comisión es suficiente para TUD |
| **3 roles únicamente** | Balance entre flexibilidad y simplicidad |
| **API Key por usuario** | Cada tutor controla su cuota y costos de Gemini |

---

## 6. Estructura Jerárquica

### 6.1 Jerarquía Académica (2 niveles)

```
MATERIA (ej: Programación 1, Programación 2, Programación 3, Programación 4)
│
├── COMISIONES (ej: Comisión A - 2026, Comisión B - 2026)
│   ├── Tutores asignados (uno o más por comisión)
│   └── Entregas de alumnos (por cada rúbrica/TP)
│
└── RÚBRICAS (ej: TP1 - Listas, TP2 - Funciones, Parcial 1)
    └── Aplican a TODAS las comisiones de la materia
```

### 6.2 Principio Fundamental

Las rúbricas (trabajos prácticos, parciales, etc.) se definen a nivel de **materia** y son compartidas automáticamente por **todas las comisiones** de esa materia en el mismo año académico.

---

## 7. Roles y Permisos

### 7.1 Definición de Roles (3 roles)

| Rol | Descripción |
|-----|-------------|
| **Administrador** | Gestiona toda la plataforma. Acceso total |
| **Coordinador** | Gestiona rúbricas y comisiones de sus materias asignadas. Ve correcciones de tutores |
| **Tutor** | Corrige entregas de sus comisiones asignadas |

### 7.2 Matriz de Permisos

| Acción | Admin | Coordinador | Tutor |
|--------|:-----:|:-----------:|:-----:|
| Crear/editar materias | ✓ | - | - |
| Crear/editar usuarios | ✓ | - | - |
| Asignar coordinadores a materias | ✓ | - | - |
| Crear/editar comisiones | ✓ | ✓ (solo sus materias) | - |
| Asignar tutores a comisiones | ✓ | ✓ (solo sus materias) | - |
| Crear/editar rúbricas | ✓ | ✓ (solo sus materias) | - |
| Ver todas las comisiones | ✓ | Solo sus materias | Solo asignadas |
| Ver correcciones de otros tutores | ✓ | ✓ (solo sus materias) | - |
| Subir entregas | ✓ | ✓ | ✓ |
| Corregir entregas | ✓ | ✓ | ✓ (solo sus comisiones) |
| Editar correcciones | ✓ | ✓ | ✓ (solo sus comisiones) |
| Descargar PDFs | ✓ | ✓ | ✓ (solo sus comisiones) |
| Exportar notas | ✓ | ✓ | ✓ (solo sus comisiones) |
| Configurar su API Key Gemini | ✓ | ✓ | ✓ |

---

## 8. Objetivos del Proyecto

### 8.1 Objetivos Principales

| # | Objetivo | Métrica de Éxito |
|---|----------|------------------|
| 1 | Reducir tiempo de corrección por entrega | < 5 minutos de trabajo activo del tutor |
| 2 | Garantizar consistencia en evaluaciones | Misma rúbrica aplicada uniformemente a todas las entregas |
| 3 | Proporcionar retroalimentación pedagógica | Feedback específico por criterio + fortalezas + recomendaciones |
| 4 | Simplificar la gestión académica | Estructura de 2 niveles, 3 roles, sin complejidad innecesaria |
| 5 | Mantener control docente | Toda corrección editable, tutor tiene última palabra |

### 8.2 Objetivos de Rendimiento

| Métrica | Objetivo |
|---------|----------|
| Tiempo de corrección individual | < 60 segundos |
| Corrección en lote | ≥ 2 entregas/minuto |
| Generación de PDF | < 5 segundos |
| Carga de página | < 2 segundos |
| Usuarios concurrentes | 20 sin degradación |

### 8.3 Objetivos de Seguridad

| Aspecto | Objetivo |
|---------|----------|
| Contraseñas | Hash bcrypt, nunca en texto plano |
| API Keys | Encriptación AES-256 |
| Autenticación | JWT con expiración |
| Acceso a datos | Cada rol solo ve lo que le corresponde |

---

## 9. Resumen de Decisiones

| Aspecto | Decisión | Justificación |
|---------|----------|---------------|
| Nombre | Active-IA | Mantener nombre del documento original |
| Alcance | TUD primero, luego expandir | Simplicidad inicial, arquitectura preparada |
| Jerarquía | 2 niveles (Materia → Comisión) | Suficiente para TUD, reduce complejidad |
| Roles | 3 (Admin, Coordinador, Tutor) | Balance entre flexibilidad y simplicidad |
| Base de datos | PostgreSQL con Prisma | Mejor para datos estructurados |
| Integración IA | N8N como intermediario | Flexibilidad para modificar prompts |
| Notificaciones | Solo en-app | Sin complejidad de servidor de email |
| Lenguajes | Múltiples (configurable) | Flexibilidad para diferentes materias |
| Similitud | Fase posterior | Priorizar corrección, agregar después |
| Multi-tenancy | No incluido | No necesario para TUD inicial |

---

## 10. Próximos Pasos

Este documento define la visión y objetivos del proyecto. Los siguientes documentos detallarán:

- **02-USUARIOS-ROLES.md**: Personas detalladas, flujos de usuario, permisos granulares
- **03-REQUISITOS-FUNCIONALES.md**: Historias de usuario, módulos, funcionalidades detalladas

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
