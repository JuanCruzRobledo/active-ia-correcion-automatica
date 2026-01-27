#!/bin/bash
# Script para construir y pushear imagen de N8N preconfigurada
# Active-IA - Sistema de Corrección Automática

set -e

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==========================================="
echo "  Build N8N Preconfigurada - Active-IA"
echo "===========================================${NC}"

# Verificar que el directorio data/ existe y no está vacío
if [ ! -d "data" ] || [ -z "$(ls -A data)" ]; then
    echo -e "${RED}❌ Error: El directorio data/ no existe o está vacío${NC}"
    echo ""
    echo -e "${YELLOW}Debes configurar N8N primero siguiendo las instrucciones en README.md${NC}"
    echo ""
    echo "Pasos rápidos:"
    echo "1. Levantar N8N en modo configuración"
    echo "2. Crear los workflows en http://localhost:5678"
    echo "3. Detener N8N (los datos quedan en data/)"
    echo "4. Ejecutar este script"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ Directorio data/ encontrado con configuración${NC}"
echo ""

# Solicitar nombre de la imagen
read -p "Nombre de la imagen (ej: tu-usuario/n8n-active-ia): " IMAGE_NAME
if [ -z "$IMAGE_NAME" ]; then
    echo -e "${RED}❌ Nombre de imagen requerido${NC}"
    exit 1
fi

# Solicitar tag (opcional)
read -p "Tag (default: latest): " IMAGE_TAG
IMAGE_TAG=${IMAGE_TAG:-latest}

FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

echo ""
echo -e "${YELLOW}📦 Construyendo imagen: ${FULL_IMAGE_NAME}${NC}"
echo ""

# Construir imagen
docker build -t "$FULL_IMAGE_NAME" -f Dockerfile.preconfigured .

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Imagen construida exitosamente${NC}"
    echo ""

    # Mostrar información de la imagen
    echo -e "${BLUE}Información de la imagen:${NC}"
    docker images "$IMAGE_NAME" | grep "$IMAGE_TAG"
    echo ""

    # Preguntar si quiere pushear
    read -p "¿Deseas pushear la imagen a Docker Hub? (s/N): " PUSH_CONFIRM

    if [ "$PUSH_CONFIRM" = "s" ] || [ "$PUSH_CONFIRM" = "S" ]; then
        echo -e "${YELLOW}📤 Pusheando imagen a Docker Hub...${NC}"
        docker push "$FULL_IMAGE_NAME"

        if [ $? -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✅ Imagen pusheada exitosamente a Docker Hub${NC}"
            echo ""
            echo -e "${BLUE}Para usar esta imagen, actualiza docker-compose.yml:${NC}"
            echo -e "${YELLOW}-------------------------------------------${NC}"
            echo -e "${YELLOW}services:${NC}"
            echo -e "${YELLOW}  n8n:${NC}"
            echo -e "${YELLOW}    image: ${FULL_IMAGE_NAME}${NC}"
            echo -e "${YELLOW}-------------------------------------------${NC}"
            echo ""
        else
            echo ""
            echo -e "${RED}❌ Error al pushear imagen${NC}"
            echo -e "${YELLOW}💡 Asegúrate de estar logueado: docker login${NC}"
            echo ""
        fi
    else
        echo ""
        echo -e "${BLUE}ℹ️  Imagen creada localmente. No se pusheó a Docker Hub.${NC}"
        echo ""
    fi
else
    echo ""
    echo -e "${RED}❌ Error al construir la imagen${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}==========================================="
echo "  ✅ Proceso completado"
echo "===========================================${NC}"
echo ""
