# 04 - Requisitos No Funcionales

---

## 1. Resumen

Este documento define los requisitos no funcionales del sistema Active-IA, incluyendo rendimiento, seguridad, escalabilidad, compatibilidad y restricciones técnicas.

| Categoría | Aspectos Principales |
|-----------|---------------------|
| **Rendimiento** | Tiempos de respuesta, concurrencia, límites de archivos |
| **Seguridad** | Autenticación, encriptación, protección contra ataques |
| **Escalabilidad** | Capacidad inicial, modelo híbrido, fases de crecimiento |
| **Disponibilidad** | Backups, logging, recuperación de errores |
| **Compatibilidad** | Navegadores, dispositivos, conexión |
| **Restricciones** | Tamaños máximos, formatos soportados |

---

## 2. Rendimiento

### 2.1 Tiempos de Respuesta

| Operación | Tiempo Máximo | Notas |
|-----------|---------------|-------|
| **Carga de página (login, dashboard)** | < 2 segundos | Tiempo hasta interactivo |
| **Navegación entre secciones** | < 1 segundo | Cambio de vista/ruta |
| **Listados (hasta 100 registros)** | < 3 segundos | Con paginación si excede |
| **Carga de ZIP individual (hasta 10MB)** | < 10 segundos | Incluye procesamiento |
| **Carga masiva (hasta 100MB)** | < 120 segundos | Progreso visible |
| **Corrección individual con IA** | < 60 segundos (nominal) | Ver nota abajo |
| **Corrección en lote** | ≥ 2 entregas/minuto | Procesamiento secuencial |
| **Generación de PDF individual** | < 5 segundos | |
| **Generación de ZIP con PDFs (30+ entregas)** | < 60 segundos | |
| **Exportación de notas a Excel** | < 10 segundos | |

**Nota sobre corrección con IA:**
- El tiempo de 60 segundos es el objetivo nominal
- En casos excepcionales (Gemini sobrecargado, conexión lenta), puede extenderse
- El sistema debe mostrar indicador de progreso y no abortar prematuramente
- Se implementará timeout configurable con reintentos automáticos

### 2.2 Concurrencia

| Métrica | Requisito |
|---------|-----------|
| **Usuarios concurrentes (modo servidor)** | 20 sin degradación |
| **Correcciones en lote simultáneas** | 5 máximo |
| **Descargas de PDF simultáneas** | 10 máximo |

**Nota:** En modo local (cada tutor en su PC), la concurrencia no aplica de la misma manera ya que cada instancia es independiente.

### 2.3 Límites de Archivos

| Tipo de Archivo | Tamaño Máximo |
|-----------------|---------------|
| **ZIP individual (una entrega)** | 10 MB |
| **ZIP masivo (múltiples entregas)** | 100 MB |
| **PDF de consigna (para generar rúbrica)** | 10 MB |
| **Archivo TXT consolidado** | 5 MB |

### 2.4 Paginación

| Listado | Registros por Página | Notas |
|---------|---------------------|-------|
| **Usuarios** | 20 | Con búsqueda y filtros |
| **Materias** | 20 | Ordenadas alfabéticamente |
| **Comisiones** | 20 | Filtradas por año |
| **Entregas** | 50 | Con filtros y ordenamiento |
| **Rúbricas** | 20 | Filtradas por materia/año |

---

## 3. Seguridad

### 3.1 Autenticación

| Aspecto | Implementación |
|---------|----------------|
| **Almacenamiento de contraseñas** | Hash bcrypt con salt factor 10 |
| **Tokens de sesión** | JWT firmados con HS256, clave de 256 bits |
| **Expiración de token** | 7 días (configurable) |
| **Primer login de usuarios nuevos** | Cambio obligatorio de contraseña |
| **Requisitos de contraseña** | Mínimo 8 caracteres |

### 3.2 Protección de Datos Sensibles

| Dato Sensible | Protección |
|---------------|------------|
| **Contraseñas** | Hash bcrypt, nunca en texto plano, no en logs ni respuestas |
| **API Keys Gemini** | Encriptación AES-256-CBC antes de almacenar |
| **Tokens JWT** | No almacenar en servidor, solo validar firma |
| **Archivos de entregas** | Acceso solo con autenticación válida y permisos |

### 3.3 Encriptación de API Keys

```
Proceso de almacenamiento:
1. Usuario ingresa API Key
2. Sistema valida con llamada de prueba a Gemini
3. Si válida:
   a. Genera IV aleatorio (16 bytes)
   b. Encripta con AES-256-CBC usando clave maestra del servidor
   c. Almacena: IV + datos encriptados (base64)
4. Para usar:
   a. Extrae IV y datos encriptados
   b. Desencripta con clave maestra
   c. Usa API Key en memoria (nunca en logs)
```

### 3.4 Rate Limiting

| Tipo | Límite | Ventana |
|------|--------|---------|
| **Por IP (no autenticado)** | 100 peticiones | 1 minuto |
| **Por usuario (autenticado)** | 200 peticiones | 1 minuto |
| **Login fallido por IP** | 10 intentos | 15 minutos |
| **Correcciones por usuario** | 60 entregas | 1 hora |

**Acciones al exceder límite:**
- Respuesta HTTP 429 (Too Many Requests)
- Header `Retry-After` con segundos de espera
- Log de evento para monitoreo

### 3.5 Protección contra Ataques

| Amenaza | Mitigación |
|---------|------------|
| **Inyección SQL** | ORM (Prisma) con parámetros tipados, nunca queries en crudo |
| **XSS (Cross-Site Scripting)** | Escape de contenido en frontend, CSP headers |
| **CSRF (Cross-Site Request Forgery)** | Token JWT en header Authorization, no en cookies |
| **Path Traversal** | Sanitización de nombres de archivo, rutas absolutas controladas |
| **Fuerza bruta** | Rate limiting, bloqueo temporal por intentos fallidos |
| **Denegación de servicio** | Rate limiting, límites de tamaño de archivo |
| **Exposición de datos** | Validación de permisos en cada endpoint |

### 3.6 Validación de Permisos

```
Cada endpoint debe validar:
1. Token JWT válido (autenticación)
2. Usuario activo (no soft deleted)
3. Rol del usuario tiene permiso para la acción
4. Si aplica: recurso pertenece al scope del usuario
   - Coordinador: solo sus materias asignadas
   - Tutor: solo sus comisiones asignadas
```

### 3.7 Headers de Seguridad

| Header | Valor |
|--------|-------|
| `X-Content-Type-Options` | nosniff |
| `X-Frame-Options` | DENY |
| `X-XSS-Protection` | 1; mode=block |
| `Strict-Transport-Security` | max-age=31536000; includeSubDomains (solo HTTPS) |
| `Content-Security-Policy` | default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' |

---

## 4. Escalabilidad

### 4.1 Contexto del Sistema

El sistema opera en un modelo **híbrido**:

| Modo | Descripción |
|------|-------------|
| **Local** | Cada tutor ejecuta la aplicación en su PC, conectada a BD en la nube. Archivos almacenados localmente. |
| **Servidor web** | Instancia centralizada accesible vía navegador. Todo en la nube. |
| **Híbrido** | Combinación de ambos según preferencia del usuario. |

### 4.2 Capacidad Real (TUD)

| Métrica | Cantidad |
|---------|----------|
| **Tutores activos** | ~20 |
| **Materias** | 5+ |
| **Comisiones por materia** | ~17 |
| **Total comisiones** | ~85 |
| **Alumnos por comisión** | ~40 |
| **Total alumnos** | ~3,400 |
| **TPs por materia por cuatrimestre** | ~6 |
| **Entregas estimadas por cuatrimestre** | ~20,000+ |

### 4.3 Capacidad por Fase

#### Fase 1: MVP

| Aspecto | Capacidad |
|---------|-----------|
| **Usuarios registrados** | 100 |
| **Tutores activos concurrentes** | 20 |
| **Materias** | 10 |
| **Comisiones totales** | 100 |
| **Entregas por cuatrimestre** | 25,000 |
| **Almacenamiento BD** | 10 GB |
| **Almacenamiento archivos (modo servidor)** | 50 GB |

#### Fase 2: Crecimiento

| Aspecto | Capacidad |
|---------|-----------|
| **Usuarios registrados** | 300 |
| **Tutores activos concurrentes** | 50 |
| **Materias** | 20 |
| **Comisiones totales** | 300 |
| **Entregas por cuatrimestre** | 75,000 |
| **Almacenamiento BD** | 30 GB |
| **Almacenamiento archivos** | 200 GB |

### 4.4 Estrategias de Escalamiento

| Estrategia | Descripción | Fase |
|------------|-------------|------|
| **Índices de BD optimizados** | Índices en campos de búsqueda frecuente | 1 |
| **Paginación en listados** | Evitar cargar todos los registros | 1 |
| **Lazy loading de código** | Cargar preview, expandir bajo demanda | 1 |
| **Caché de consultas frecuentes** | Materias, comisiones, rúbricas activas | 2 |
| **Escalamiento vertical BD** | Mayor RAM/CPU en servidor PostgreSQL | 2 |
| **Migración a cloud storage** | S3/GCS para archivos (modo servidor) | 2 |
| **Réplicas de lectura BD** | Separar lecturas de escrituras | 3 |
| **Backend stateless múltiples instancias** | Load balancer entre instancias | 3 |

---

## 5. Disponibilidad y Mantenibilidad

### 5.1 Backups

| Aspecto | Requisito |
|---------|-----------|
| **Frecuencia** | Diario (automático) |
| **Retención** | 7 días |
| **Tipo** | Dump completo de PostgreSQL |
| **Almacenamiento** | Ubicación separada del servidor principal |
| **Verificación** | Restauración de prueba mensual |

### 5.2 Logging

| Nivel | Qué se registra |
|-------|-----------------|
| **INFO** | Logins exitosos, correcciones completadas, descargas de PDF |
| **WARN** | Intentos de acceso a recursos sin permiso, rate limit alcanzado |
| **ERROR** | Errores de aplicación, fallos de IA, timeouts |
| **DEBUG** | Detalles técnicos (solo en desarrollo) |

**Eventos a registrar:**

| Evento | Datos registrados |
|--------|-------------------|
| **Login** | Usuario, IP, timestamp, éxito/fallo |
| **Logout** | Usuario, timestamp |
| **Corrección iniciada** | Usuario, entrega_id, timestamp |
| **Corrección completada** | Usuario, entrega_id, nota, duración, timestamp |
| **Corrección fallida** | Usuario, entrega_id, error, timestamp |
| **Edición de corrección** | Usuario, corrección_id, campos editados, timestamp |
| **Descarga de PDF** | Usuario, entrega_id, timestamp |
| **Exportación de notas** | Usuario, comisión_id, cantidad, timestamp |
| **Creación de rúbrica** | Usuario, materia_id, método (manual/PDF), timestamp |

### 5.3 Recuperación de Errores

| Escenario | Comportamiento |
|-----------|----------------|
| **Timeout de IA** | Reintentar 1 vez, luego marcar como ERROR con mensaje descriptivo |
| **Error de N8N** | Registrar error, marcar entrega como ERROR, notificar al usuario |
| **Fallo en carga masiva** | Continuar con las demás entregas, reportar errores al final |
| **Error de BD** | Mostrar mensaje amigable, registrar error técnico |
| **Sesión expirada** | Redirigir a login, preservar URL de retorno |

### 5.4 Monitoreo (Modo Servidor)

| Métrica | Umbral de Alerta |
|---------|------------------|
| **Uso de CPU** | > 80% por 5 minutos |
| **Uso de memoria** | > 85% |
| **Espacio en disco** | < 10% disponible |
| **Tiempo de respuesta promedio** | > 3 segundos |
| **Tasa de errores** | > 5% de peticiones |
| **Conexiones a BD** | > 80% del pool |

---

## 6. Compatibilidad

### 6.1 Navegadores Soportados

| Navegador | Versiones |
|-----------|-----------|
| **Google Chrome** | Últimas 2 versiones |
| **Mozilla Firefox** | Últimas 2 versiones |
| **Microsoft Edge** | Últimas 2 versiones |
| **Apple Safari** | Últimas 2 versiones |

**No soportados:**
- Internet Explorer (cualquier versión)
- Navegadores móviles antiguos (pre-2022)

### 6.2 Dispositivos

| Dispositivo | Soporte |
|-------------|---------|
| **Desktop/Laptop** | Completo (optimizado) |
| **Tablet** | Funcional (responsive) |
| **Smartphone** | Básico (responsive simplificado) |

**Resoluciones:**

| Breakpoint | Ancho | Diseño |
|------------|-------|--------|
| **Móvil** | < 640px | Una columna, menú hamburguesa |
| **Tablet** | 640px - 1024px | Dos columnas donde aplique |
| **Desktop** | > 1024px | Diseño completo |

### 6.3 Requisitos del Cliente

| Requisito | Especificación |
|-----------|----------------|
| **JavaScript** | Habilitado (requerido) |
| **Cookies** | No requeridas (auth via localStorage) |
| **LocalStorage** | Requerido (token JWT) |
| **Conexión a internet** | Requerida (no hay modo offline) |

---

## 7. Restricciones Técnicas

### 7.1 Formatos de Archivo Soportados

**Entrada (carga de entregas):**

| Formato | Extensión | Descripción |
|---------|-----------|-------------|
| **ZIP** | .zip | Proyecto comprimido |
| **TXT** | .txt | Código ya consolidado |

**Salida:**

| Formato | Extensión | Uso |
|---------|-----------|-----|
| **PDF** | .pdf | Devoluciones |
| **Excel** | .xlsx | Exportación de notas |
| **ZIP** | .zip | Descarga masiva de PDFs |

### 7.2 Extensiones de Código para Consolidación

| Modo | Extensiones |
|------|-------------|
| **Solo código** | .py, .java, .js, .ts, .c, .cpp, .h, .go, .rb, .php |
| **Web completo** | + .html, .css, .json, .jsx, .tsx, .vue |
| **Proyecto completo** | + .md, .txt, .yml, .yaml, .xml, .sql |
| **Personalizado** | Definido por usuario |

**Archivos siempre excluidos:**
- Binarios: .exe, .dll, .so, .class, .pyc
- Media: .jpg, .png, .gif, .mp4, .mp3
- Dependencias: node_modules/, venv/, .git/, __pycache__/
- IDE: .idea/, .vscode/, *.iml

### 7.3 Caracteres y Encoding

| Aspecto | Especificación |
|---------|----------------|
| **Encoding de archivos** | UTF-8 (preferido), detección automática |
| **Caracteres en nombres de usuario** | a-z, 0-9, guión (-), guión bajo (_) |
| **Caracteres en nombres de alumno** | Unicode permitido (acentos, ñ, etc.) |
| **Longitud máxima de nombres** | 100 caracteres |

### 7.4 Límites de Contenido

| Elemento | Límite |
|----------|--------|
| **Criterios por rúbrica** | 20 máximo |
| **Niveles por criterio** | 10 máximo |
| **Fortalezas por corrección** | 10 máximo |
| **Recomendaciones por corrección** | 10 máximo |
| **Longitud de feedback por criterio** | 1000 caracteres |
| **Longitud de comentario general** | 2000 caracteres |
| **Caracteres en código consolidado** | 500,000 (para envío a IA) |

---

## 8. Requisitos de Red

### 8.1 Conectividad

| Conexión | Requisito |
|----------|-----------|
| **Internet** | Requerida para funcionamiento |
| **Modo offline** | No soportado |
| **Velocidad mínima** | 1 Mbps (para carga de archivos) |
| **Velocidad recomendada** | 5 Mbps+ |

### 8.2 Puertos (Modo Local)

| Servicio | Puerto | Configurable |
|----------|--------|--------------|
| **Frontend** | 3000 | Sí |
| **Backend** | 5000 | Sí |
| **PostgreSQL (si local)** | 5432 | Sí |
| **N8N** | 5678 | Sí |

### 8.3 Conexiones Externas

| Servicio | URL/Host | Puerto | Protocolo |
|----------|----------|--------|-----------|
| **Google Gemini API** | generativelanguage.googleapis.com | 443 | HTTPS |
| **PostgreSQL (nube)** | Configurable | 5432 | TCP/SSL |

---

## 9. Internacionalización

### 9.1 Idioma

| Aspecto | Especificación |
|---------|----------------|
| **Idioma de interfaz** | Español (único) |
| **Idioma de documentación** | Español |
| **Idioma de logs** | Inglés (términos técnicos) |
| **Soporte multi-idioma** | No incluido en MVP |

### 9.2 Formato de Datos

| Dato | Formato |
|------|---------|
| **Fechas (display)** | DD/MM/YYYY |
| **Fechas (BD)** | ISO 8601 (YYYY-MM-DD) |
| **Hora** | HH:MM (24 horas) |
| **Números decimales** | Punto como separador (ej: 8.5) |
| **Zona horaria** | Configurable, default America/Argentina/Buenos_Aires |

---

## 10. Resumen de Decisiones

| Aspecto | Decisión |
|---------|----------|
| **Tiempo corrección IA** | 60 segundos nominal, flexible en casos excepcionales |
| **Concurrencia (servidor)** | 20 usuarios sin degradación |
| **Tamaño ZIP masivo** | 100 MB máximo |
| **JWT expiración** | 7 días |
| **Navegadores** | Modernos, últimas 2 versiones |
| **Rate limiting** | Sí, por IP y por usuario |
| **Logging** | Completo (logins, correcciones, ediciones, descargas) |
| **Móvil** | Responsive básico |
| **Modelo despliegue** | Híbrido (local + servidor web) |
| **Storage archivos** | Local en modo PC, configurable para cloud en servidor |
| **Backups BD** | Diarios, retención 7 días |
| **ZIP PDFs** | 60 segundos máximo |

---

## 11. Próximos Pasos

Este documento define los requisitos no funcionales del sistema. Los siguientes documentos detallarán:

- **05-ARQUITECTURA-STACK.md**: Tecnologías, justificación, diagramas de arquitectura
- **06-MODELO-DATOS.md**: Entidades, relaciones, estructuras JSON

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
