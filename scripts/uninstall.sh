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
SHARED_CONFIG="/mnt/data/AuraLink/config.yaml"

clear
echo -e "${RED}╔══════════════════════════════════════════════════════╗"
echo -e "║            AuraLink Control — Uninstaller            ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo ""

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

if grep -q "LABEL=AURA" /etc/fstab; then
    echo -e "\n${YELLOW}[ FASE 2.5 ] Limpieza de Partición Compartida (AURA)${NC}"
    read -p "  ¿Desea desmontar y eliminar la persistencia de AURA en fstab? (s/n): " REMOVE_FSTAB
    if [ "$REMOVE_FSTAB" = "s" ]; then
        AURA_MOUNT=$(grep "LABEL=AURA" /etc/fstab | awk '{print $2}')
        if [ -n "$AURA_MOUNT" ]; then
            run_step "Desmontando partición AURA" "sudo umount $AURA_MOUNT"
        fi
        run_step "Eliminando entrada de fstab" "sudo sed -i '/LABEL=AURA/d' /etc/fstab"
        
        AURA_DEV=$(lsblk -dno NAME,LABEL | grep -i "AURA" | awk '{print "/dev/"$1}' | head -n1)
        if [ -n "$AURA_DEV" ]; then
            read -p "  ¿Desea ELIMINAR físicamente la partición AURA en $AURA_DEV? (s/n): " DELETE_PART
            if [ "$DELETE_PART" = "s" ]; then
                PARENT_DISK=$(lsblk -no PKNAME "$AURA_DEV" | head -n1)
                PART_NUM=$(echo "$AURA_DEV" | grep -o '[0-9]\+$')
                if [ -n "$PARENT_DISK" ] && [ -n "$PART_NUM" ]; then
                    run_step "Eliminando partición física" "sudo parted -s /dev/$PARENT_DISK rm $PART_NUM"
                fi
            fi
        fi
    fi
fi

echo -e "\n${RED}╔══════════════════════════════════════════════════════╗"
echo -e "║             DESINSTALACIÓN COMPLETADA                ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo -e "  Los servicios y configuraciones han sido eliminados.\n"