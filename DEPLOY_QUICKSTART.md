# 🚀 Deploy Rápido - Active-IA en VPS Hostinger

## Quick Start (5 minutos)

### 1. En tu VPS:
```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Clonar proyecto
cd /opt
git clone TU_REPO active-ia
cd active-ia
```

### 2. Configurar variables:
```bash
# Copiar template
cp .env.production.example .env.production

# Editar con tus valores
nano .env.production
```

**Valores críticos a cambiar:**
- `POSTGRES_PASSWORD` → Contraseña fuerte
- `SECRET_KEY` → Generar con: `openssl rand -hex 32`
- `ENCRYPTION_KEY` → Generar con Python/Fernet
- `CORS_ORIGINS` → Tu IP/dominio
- `VITE_API_URL` → `http://TU_IP/api/v1`
- `N8N_BASIC_AUTH_PASSWORD` → Contraseña fuerte

### 3. Iniciar servicios:
```bash
# Crear symlink
ln -sf .env.production .env

# Levantar todo
docker compose -f docker-compose.prod.yml up -d

# Ver estado
docker compose -f docker-compose.prod.yml ps
```

### 4. Verificar:
```bash
# Ver logs
docker compose -f docker-compose.prod.yml logs -f

# Probar health checks
curl http://localhost/api/v1/health
curl http://localhost/
```

### 5. Acceder:
- **Frontend**: `http://TU_IP_VPS/`
- **API Docs**: `http://TU_IP_VPS/api/v1/docs`
- **N8N**: `http://TU_IP_VPS/n8n/`

---

## 📚 Para más detalles:
Ver **[DEPLOYMENT.md](./DEPLOYMENT.md)** para:
- Configuración SSL/HTTPS
- Backups automáticos
- Troubleshooting
- Monitoreo
- Actualización de la app

---

## 🔥 Comandos útiles:

```bash
# Ver logs
docker compose -f docker-compose.prod.yml logs -f

# Reiniciar servicio
docker compose -f docker-compose.prod.yml restart backend

# Ver estado
docker compose -f docker-compose.prod.yml ps

# Detener todo
docker compose -f docker-compose.prod.yml down

# Actualizar app
git pull && docker compose -f docker-compose.prod.yml up -d --build
```

---

## ⚠️ Checklist mínimo:

- [ ] Docker instalado
- [ ] Puerto 80 abierto en firewall
- [ ] `.env.production` configurado con valores reales
- [ ] Contraseñas cambiadas (no usar valores por defecto)
- [ ] Servicios corriendo (`docker compose ps`)
- [ ] Frontend accesible desde navegador

---

**¿Problemas?** → Ver logs: `docker compose -f docker-compose.prod.yml logs`
