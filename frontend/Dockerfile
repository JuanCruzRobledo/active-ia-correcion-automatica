# ============================================
# Active-IA Frontend - Multi-stage Dockerfile
# ============================================

# ============================================
# Stage 1: Build
# ============================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copiar archivos de dependencias
COPY package*.json ./

# Instalar dependencias
RUN npm ci

# Copiar código fuente
COPY . .

# Build args para variables de entorno de build.
# Relativa por defecto: la app pega a /api/v1 (mismo origen) y Nginx proxea al backend.
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL

# Compilar aplicación para producción
RUN npm run build

# ============================================
# Stage 2: Production (Nginx)
# ============================================
FROM nginx:alpine

# Copiar archivos compilados del stage anterior
COPY --from=builder /app/dist /usr/share/nginx/html

# Copiar configuración personalizada de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exponer puerto 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/health || exit 1

# Iniciar Nginx en foreground
CMD ["nginx", "-g", "daemon off;"]
