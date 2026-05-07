## Context

El proyecto Active-IA es una plataforma que integra FastAPI, React y n8n. Actualmente existen múltiples archivos de Docker Compose (`docker-compose.yml`, `docker-compose.local.yml`, `docker-compose.prod.yml`). Se han realizado correcciones previas documentadas en `DOCKER-COMPOSE-FIXES.md`, pero es necesario asegurar que el flujo de desarrollo local sea fluido y esté completamente operativo.

## Goals / Non-Goals

**Goals:**
- Asegurar que `docker-compose.local.yml` sea la herramienta estándar para desarrollo local.
- Configurar el archivo `.env` para que el backend se conecte a la base de datos de Docker por defecto cuando se usa Compose.
- Validar la comunicación entre el Backend y n8n dentro de la red de Docker.
- Verificar que los volúmenes de persistencia para PostgreSQL y n8n funcionen correctamente.

**Non-Goals:**
- Configuración de despliegue en producción (esto se maneja en `docker-compose.prod.yml`).
- Optimización extrema de las imágenes de Docker para tamaño (el foco es desarrollo).

## Decisions

- **Uso de `docker-compose.local.yml`**: Se mantendrá este archivo separado del `docker-compose.yml` base para permitir una configuración de base de datos local (PostgreSQL en contenedor) sin afectar la configuración de producción que usa una base de datos externa.
- **Red de Docker Interna**: Todos los servicios se unirán a `active-ia-network`. El backend usará `DATABASE_URL` con el hostname `postgres` y los webhooks de n8n con el hostname `n8n`.
- **Montaje de Volúmenes para Desarrollo**: Se montará `./backend` en `/app` dentro del contenedor del backend para facilitar el desarrollo, aunque el `Dockerfile` copie los archivos para la imagen final.
- **Healthchecks en Cascada**: Se utilizarán healthchecks con `depends_on` y `condition: service_healthy` para asegurar que el backend no inicie antes que la DB y n8n, y que el frontend no inicie antes que el backend.

## Risks / Trade-offs

- **Conflicto de Puertos**: Si el usuario tiene PostgreSQL instalado localmente en el host (puerto 5432), el contenedor fallará al intentar mapear el puerto.
  - *Mitigación*: Usar `${POSTGRES_PORT:-5432}` en el archivo compose para permitir sobrescribirlo desde `.env`.
- **Lentitud en el Build Inicial**: Instalar dependencias de Python y Node puede ser lento la primera vez.
  - *Mitigación*: Usar capas de Docker optimizadas (copiar solo lockfiles antes que el código).
- **Consumo de Recursos**: Correr 4 servicios más la base de datos puede ser pesado para máquinas con poca RAM.
  - *Mitigación*: Documentar que se puede levantar solo lo necesario (ej: `docker-compose up backend postgres`).
