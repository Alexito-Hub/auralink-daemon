#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="/opt/auralink-control"
SERVICE_NAME="auralink-control.service"
SUDOERS_FILE="/etc/sudoers.d/auralink-control"
SHARED_CONFIG="/mnt/datos/AuraLink/config.yaml"

clear
echo -e "${RED}╔══════════════════════════════════════════════════════╗"
echo -e "║            AuraLink Control — Uninstaller            ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Funcion para ejecutar comandos silenciosamente
run_step() {
    local desc=$1
    local cmd=$2
    echo -ne "  >_ $desc..."
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "\r  ${GREEN}✔ $desc.                                      ${NC}"
    else
        echo -e "\r  ${YELLOW}⚠ Info: $desc (no requerido u omitido).       ${NC}"
    fi
}

echo -e "${YELLOW}[ FASE 1 ] Deteniendo servicios y procesos...${NC}"

run_step "Deteniendo servicio $SERVICE_NAME" "sudo systemctl stop $SERVICE_NAME"
run_step "Deshabilitando servicio" "sudo systemctl disable $SERVICE_NAME"
run_step "Eliminando archivo de unidad" "sudo rm /etc/systemd/system/$SERVICE_NAME"

# Matar cualquier proceso huérfano que use el puerto 8443 o sea main.py
run_step "Limpiando procesos huérfanos (puerto 8443)" "sudo fuser -k 8443/tcp"
run_step "Finalizando instancias de python AuraLink" "sudo pkill -f 'python.*main.py'"

run_step "Recargando daemon de systemd" "sudo systemctl daemon-reload"

echo -e "\n${YELLOW}[ FASE 2 ] Limpieza de sistema...${NC}"

run_step "Eliminando permisos sudoers" "sudo rm $SUDOERS_FILE"

if [ -d "$INSTALL_DIR" ]; then
    read -p "  ¿Desea eliminar el directorio de instalación ($INSTALL_DIR)? (s/n): " REMOVE_INSTALL
    if [ "$REMOVE_INSTALL" = "s" ]; then
        run_step "Eliminando directorio de instalación" "sudo rm -rf $INSTALL_DIR"
    fi
fi

if [ -f "$SHARED_CONFIG" ]; then
    echo -e "\n  ${BLUE}ℹ Se detectó una configuración en la partición compartida.${NC}"
    read -p "  ¿Desea eliminar el archivo de configuración ($SHARED_CONFIG)? (s/n): " REMOVE_CONFIG
    if [ "$REMOVE_CONFIG" = "s" ]; then
        run_step "Eliminando configuración compartida" "sudo rm $SHARED_CONFIG"
    fi
fi

echo -e "\n${RED}╔══════════════════════════════════════════════════════╗"
echo -e "║             DESINSTALACIÓN COMPLETADA                ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo -e "  Los servicios y configuraciones han sido eliminados.\n"
