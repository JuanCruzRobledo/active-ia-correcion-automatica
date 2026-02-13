# Guía de Deployment - Active-IA en VPS Hostinger

Esta guía te ayudará a desplegar la aplicación Active-IA en tu VPS Hostinger KVM 4 usando Docker Compose.

## 📋 Pre-requisitos

### En tu VPS:
- Ubuntu 20.04/22.04 o Debian 11/12
- Docker Engine (versión 20.10+)
- Docker Compose (versión 2.0+)
- Al menos 4GB RAM
- 20GB de espacio en disco
- Dominio apuntando al VPS (opcional pero recomendado)

### En tu máquina local:
- Git
- SSH access al VPS

---

## 🚀 Paso 1: Preparar el VPS

### 1.1 Conectar al VPS por SSH
```bash
ssh root@TU_IP_VPS
```

### 1.2 Actualizar el sistema
```bash
apt update && apt upgrade -y
```

### 1.3 Instalar Docker
```bash
# Instalar dependencias
apt install -y apt-transport-https ca-certificates curl software-properties-common

# Agregar repositorio de Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verificar instalación
docker --version
docker compose version
```

### 1.4 Configurar firewall (UFW)
```bash
# Instalar UFW si no está instalado
apt install -y ufw

# Permitir SSH
ufw allow 22/tcp

# Permitir HTTP y HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Habilitar firewall
ufw enable
ufw status
```

---

## 📦 Paso 2: Clonar el proyecto

### 2.1 Crear directorio para la aplicación
```bash
mkdir -p /opt/active-ia
cd /opt/active-ia
```

### 2.2 Clonar repositorio
```bash
# Si usas Git
git clone TU_REPOSITORIO_GIT .

# O si subes archivos manualmente con SCP desde tu máquina local:
# scp -r /ruta/local/active-ia/* root@TU_IP_VPS:/opt/active-ia/
```

---

## ⚙️ Paso 3: Configurar variables de entorno

### 3.1 Copiar template de producción
```bash
cd /opt/active-ia
cp .env.production.example .env.production
```

### 3.2 Editar variables de entorno
```bash
nano .env.production
```

### 3.3 Generar claves seguras

**Para SECRET_KEY:**
```bash
openssl rand -hex 32
```

**Para ENCRYPTION_KEY:**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3.4 Configurar valores importantes

Edita `.env.production` con valores reales:

```env
# PostgreSQL - Cambiar contraseñas
POSTGRES_PASSWORD=tu_contraseña_segura_postgres

# Backend - Usar claves generadas
SECRET_KEY=tu_secret_key_generado
ENCRYPTION_KEY=tu_encryption_key_generado

# CORS - Tu dominio o IP del VPS
CORS_ORIGINS=["http://TU_IP_O_DOMINIO","https://TU_IP_O_DOMINIO"]

# Frontend - URL del API
VITE_API_URL=http://TU_IP_O_DOMINIO/api/v1

# N8N - Cambiar credenciales
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=tu_contraseña_n8n

# Webhooks
WEBHOOK_URL=http://TU_IP_O_DOMINIO/n8n
```

---

## 🏗️ Paso 4: Construir e iniciar los servicios

### 4.1 Crear link simbólico del .env
```bash
ln -sf .env.production .env
```

### 4.2 Construir las imágenes
```bash
docker compose -f docker-compose.prod.yml build
```

### 4.3 Iniciar los servicios
```bash
docker compose -f docker-compose.prod.yml up -d
```

### 4.4 Verificar que los servicios estén corriendo
```bash
docker compose -f docker-compose.prod.yml ps
```

Deberías ver todos los servicios como "running" (healthy):
- active-ia-postgres
- active-ia-backend
- active-ia-frontend
- active-ia-n8n
- active-ia-nginx

---

## 🔍 Paso 5: Verificar la instalación

### 5.1 Ver logs de todos los servicios
```bash
docker compose -f docker-compose.prod.yml logs -f
```

### 5.2 Ver logs de un servicio específico
```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.prod.yml logs -f n8n
docker compose -f docker-compose.prod.yml logs -f postgres
```

### 5.3 Verificar health checks
```bash
# Backend
curl http://localhost/api/v1/health

# Frontend
curl http://localhost/

# N8N
curl http://localhost/n8n/healthz
```

### 5.4 Acceder a la aplicación
Abre tu navegador y ve a:
- **Frontend**: `http://TU_IP_VPS/`
- **Backend API**: `http://TU_IP_VPS/api/v1/docs`
- **N8N**: `http://TU_IP_VPS/n8n/`

---

## 🔐 Paso 6: Configurar SSL (Opcional pero recomendado)

### 6.1 Instalar Certbot
```bash
apt install -y certbot
```

### 6.2 Detener Nginx temporalmente
```bash
docker compose -f docker-compose.prod.yml stop nginx
```

### 6.3 Obtener certificado SSL
```bash
certbot certonly --standalone -d tudominio.com -d www.tudominio.com
```

### 6.4 Copiar certificados a la carpeta nginx
```bash
cp /etc/letsencrypt/live/tudominio.com/fullchain.pem /opt/active-ia/nginx/ssl/
cp /etc/letsencrypt/live/tudominio.com/privkey.pem /opt/active-ia/nginx/ssl/
chmod 644 /opt/active-ia/nginx/ssl/*.pem
```

### 6.5 Habilitar HTTPS en nginx.conf
Edita `/opt/active-ia/nginx/nginx.conf`:
- Descomentar el bloque `server` de HTTPS
- Descomentar la línea de redirección HTTP → HTTPS
- Reemplazar `tudominio.com` con tu dominio real

### 6.6 Reiniciar Nginx
```bash
docker compose -f docker-compose.prod.yml start nginx
docker compose -f docker-compose.prod.yml restart nginx
```

### 6.7 Configurar renovación automática
```bash
# Crear script de renovación
cat > /opt/active-ia/renew-ssl.sh << 'EOF'
#!/bin/bash
certbot renew --quiet
cp /etc/letsencrypt/live/tudominio.com/fullchain.pem /opt/active-ia/nginx/ssl/
cp /etc/letsencrypt/live/tudominio.com/privkey.pem /opt/active-ia/nginx/ssl/
docker compose -f /opt/active-ia/docker-compose.prod.yml restart nginx
EOF

chmod +x /opt/active-ia/renew-ssl.sh

# Agregar a crontab (renovar cada 2 meses)
crontab -e
# Agregar esta línea:
0 0 1 */2 * /opt/active-ia/renew-ssl.sh
```

---

## 🗄️ Paso 7: Backup de la base de datos

### 7.1 Crear script de backup manual
```bash
cat > /opt/active-ia/backup-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/active-ia/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="active_ia_backup_$DATE.sql"

mkdir -p $BACKUP_DIR

docker exec active-ia-postgres pg_dump -U active_ia_user active_ia_db > $BACKUP_DIR/$FILENAME

# Comprimir
gzip $BACKUP_DIR/$FILENAME

# Mantener solo los últimos 7 backups
ls -t $BACKUP_DIR/*.sql.gz | tail -n +8 | xargs -r rm

echo "Backup creado: $BACKUP_DIR/$FILENAME.gz"
EOF

chmod +x /opt/active-ia/backup-db.sh
```

### 7.2 Configurar backups automáticos diarios
```bash
crontab -e
# Agregar esta línea (backup diario a las 3 AM):
0 3 * * * /opt/active-ia/backup-db.sh
```

### 7.3 Restaurar un backup
```bash
# Descomprimir
gunzip /opt/active-ia/backups/postgres/active_ia_backup_FECHA.sql.gz

# Restaurar
docker exec -i active-ia-postgres psql -U active_ia_user active_ia_db < /opt/active-ia/backups/postgres/active_ia_backup_FECHA.sql
```

---

## 🔧 Comandos útiles

### Gestión de servicios
```bash
# Ver estado
docker compose -f docker-compose.prod.yml ps

# Ver logs en tiempo real
docker compose -f docker-compose.prod.yml logs -f

# Reiniciar un servicio
docker compose -f docker-compose.prod.yml restart backend

# Reiniciar todos los servicios
docker compose -f docker-compose.prod.yml restart

# Detener todos los servicios
docker compose -f docker-compose.prod.yml down

# Iniciar todos los servicios
docker compose -f docker-compose.prod.yml up -d

# Reconstruir y reiniciar (después de cambios en código)
docker compose -f docker-compose.prod.yml up -d --build
```

### Gestión de volúmenes
```bash
# Listar volúmenes
docker volume ls

# Ver tamaño de volúmenes
docker system df -v
```

### Limpieza
```bash
# Limpiar contenedores detenidos
docker container prune -f

# Limpiar imágenes no usadas
docker image prune -a -f

# Limpiar todo (CUIDADO: elimina volúmenes)
docker system prune -a --volumes -f
```

---

## 🐛 Troubleshooting

### Problema: Los servicios no inician
```bash
# Ver logs detallados
docker compose -f docker-compose.prod.yml logs

# Verificar que los puertos no estén ocupados
netstat -tulpn | grep -E '80|443|5432|5678'
```

### Problema: Backend no conecta con PostgreSQL
```bash
# Verificar que PostgreSQL esté healthy
docker compose -f docker-compose.prod.yml ps postgres

# Verificar logs de PostgreSQL
docker compose -f docker-compose.prod.yml logs postgres

# Verificar credenciales en .env
cat .env.production | grep POSTGRES
```

### Problema: Frontend no carga
```bash
# Verificar logs de frontend
docker compose -f docker-compose.prod.yml logs frontend

# Verificar que VITE_API_URL esté correctamente configurado
docker compose -f docker-compose.prod.yml exec frontend cat /etc/nginx/conf.d/default.conf
```

### Problema: N8N no responde
```bash
# Verificar logs de N8N
docker compose -f docker-compose.prod.yml logs n8n

# Verificar health
curl http://localhost/n8n/healthz
```

---

## 📊 Monitoreo

### Ver uso de recursos
```bash
docker stats
```

### Ver logs de Nginx
```bash
tail -f /opt/active-ia/nginx/logs/access.log
tail -f /opt/active-ia/nginx/logs/error.log
```

---

## 🔄 Actualizar la aplicación

```bash
cd /opt/active-ia

# Obtener última versión
git pull origin main

# Reconstruir y reiniciar
docker compose -f docker-compose.prod.yml up -d --build

# Verificar que todo esté corriendo
docker compose -f docker-compose.prod.yml ps
```

---

## 📞 Soporte

Si encuentras problemas durante el deployment, verifica:
1. Logs de los servicios con `docker compose logs`
2. Variables de entorno en `.env.production`
3. Puertos abiertos en el firewall
4. Que el dominio apunte correctamente al VPS (si usas dominio)

---

## ✅ Checklist final

- [ ] Docker y Docker Compose instalados
- [ ] Firewall configurado (puertos 22, 80, 443)
- [ ] Variables de entorno configuradas en `.env.production`
- [ ] Claves de seguridad generadas (SECRET_KEY, ENCRYPTION_KEY)
- [ ] Servicios iniciados con `docker compose up -d`
- [ ] Health checks pasando (todos los servicios "healthy")
- [ ] Frontend accesible desde el navegador
- [ ] Backend API respondiendo
- [ ] N8N accesible y configurado
- [ ] SSL configurado (opcional)
- [ ] Backups automáticos configurados
- [ ] Dominio apuntando al VPS (si aplica)

¡Listo! Tu aplicación Active-IA debería estar corriendo en producción. 🚀
