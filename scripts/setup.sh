set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

sudo systemctl stop auralink-control > /dev/null 2>&1 || true

INSTALL_DIR="/opt/auralink-control"
LOG_TEMP="/tmp/auralink_install.log"

clear
echo -e "${BLUE}╔══════════════════════════════════════════════════════╗"
echo -e "║             AuraLink Control — Installer             ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo ""

run_step() {
    local desc=$1
    local cmd=$2
    echo -ne "  >_ $desc..."
    if eval "$cmd" > "$LOG_TEMP" 2>&1; then
        echo -e "\r  ${GREEN}✔ $desc.                                      ${NC}"
    else
        echo -e "\r  ${RED}✘ Error: $desc.                                ${NC}"
        echo -e "${RED}--- DETALLES DEL ERROR ---${NC}"
        cat "$LOG_TEMP"
        echo -e "${RED}--------------------------${NC}"
        exit 1
    fi
}

echo -e "${YELLOW}[ FASE 1 ] Verificando entorno y dependencias...${NC}"

if [ -f /var/lib/pacman/db.lck ]; then
    echo -e "  ${YELLOW}⚠ La base de datos de pacman esta bloqueada.${NC}"
    read -p "  ¿Desea forzar la eliminacion del bloqueo? (s/n): " REMOVE_LOCK
    if [ "$REMOVE_LOCK" = "s" ]; then
        sudo rm /var/lib/pacman/db.lck
    else
        exit 1
    fi
fi

run_step "Actualizando paquetes base" "sudo pacman -Sy --needed --noconfirm python python-pip efibootmgr ethtool alsa-utils iproute2 openssl brightnessctl parted dosfstools"
run_step "Instalando librerías Python" "sudo pip install fastapi \"uvicorn[standard]\" pyjwt bcrypt psutil pyyaml --break-system-packages --root-user-action=ignore"

echo -e "\n${YELLOW}[ FASE 2 ] Configuración de Seguridad${NC}"
while true; do
    read -s -p "  >_ Ingrese PIN (4 dígitos): " PIN; echo ""
    read -s -p "  >_ Confirme su PIN: " PIN2; echo ""
    if [ "$PIN" = "$PIN2" ] && [[ "$PIN" =~ ^[0-9]{4}$ ]]; then break; fi
    echo -e "  ${RED}⚠ Error: El PIN debe ser de 4 dígitos.${NC}"
done

PIN_HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw('$PIN'.encode(), bcrypt.gensalt()).decode())")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo -e "\n${YELLOW}[ FASE 2.5 ] Configuración de Partición Compartida (AURA)${NC}"
AURA_PART=$(lsblk -dno NAME,LABEL | grep -i "AURA" | awk '{print "/dev/"$1}' | head -n1)

if [ -n "$AURA_PART" ]; then
    echo -e "  ${GREEN}✔ Partición 'AURA' detectada en $AURA_PART${NC}"
    MOUNT_POINT=$(lsblk -no MOUNTPOINT "$AURA_PART" | head -n1)
    if [ -z "$MOUNT_POINT" ]; then
        MOUNT_POINT="/mnt/AuraLink"
        run_step "Montando partición AURA" "sudo mkdir -p $MOUNT_POINT && sudo mount $AURA_PART $MOUNT_POINT"
    fi
    SHARED_DIR_LINUX="$MOUNT_POINT/AuraLink"
    sudo mkdir -p "$SHARED_DIR_LINUX"
else
    echo -e "  ${YELLOW}⚠ No se encontró la partición 'AURA'.${NC}"
    read -p "  ¿Desea crear una nueva partición compartida AURA? (s/n): " CREATE_AURA
    if [ "$CREATE_AURA" = "s" ]; then
        echo -e "\n  ${BLUE}Unidades disponibles:${NC}"
        lsblk -dno NAME,SIZE,MODEL | grep -v "loop"
        read -p "  Ingrese el dispositivo (ej: /dev/sda): " TARGET_DISK
        if [ -b "$TARGET_DISK" ]; then
            echo -e "  ${YELLOW}¡ADVERTENCIA! Se creará una partición de 500MB en $TARGET_DISK. Asegúrese de tener espacio libre.${NC}"
            read -p "  ¿Confirmar operación? (s/n): " CONFIRM_PART
            if [ "$CONFIRM_PART" = "s" ]; then
                run_step "Creando partición AURA" "sudo parted -s $TARGET_DISK mkpart primary fat32 -500MiB 100%"
                NEW_PART=$(lsblk -no NAME "$TARGET_DISK" | tail -n1)
                AURA_PART="/dev/$NEW_PART"
                run_step "Formateando partición AURA (FAT32)" "sudo mkfs.fat -F 32 -n AURA $AURA_PART"
                MOUNT_POINT="/mnt/AuraLink"
                run_step "Montando partición AURA" "sudo mkdir -p $MOUNT_POINT && sudo mount $AURA_PART $MOUNT_POINT"
                
                if ! grep -q "LABEL=AURA" /etc/fstab; then
                    run_step "Configurando persistencia en fstab" "echo 'LABEL=AURA $MOUNT_POINT vfat defaults,nofail 0 2' | sudo tee -a /etc/fstab"
                fi
                SHARED_DIR_LINUX="$MOUNT_POINT/AuraLink"
                sudo mkdir -p "$SHARED_DIR_LINUX"
            fi
        else
            echo -e "  ${RED}✘ Dispositivo no válido.${NC}"
        fi
    fi
fi

echo -e "\n${YELLOW}[ FASE 3 ] Dual Boot${NC}"
EFI_OUT=$(efibootmgr)
AUTO_WIN=$(echo "$EFI_OUT" | grep -i "Windows Boot Manager" | grep -oP "Boot\K[0-9A-F]{4}" | head -n1)
AUTO_ARCH=$(echo "$EFI_OUT" | grep -Ei "rEFInd|Arch|Linux" | grep -oP "Boot\K[0-9A-F]{4}" | head -n1)
read -p "  >_ ID Windows [$AUTO_WIN]: " WIN_ID; WIN_ID=${WIN_ID:-$AUTO_WIN}
read -p "  >_ ID Arch/Linux [$AUTO_ARCH]: " ARCH_ID; ARCH_ID=${ARCH_ID:-$AUTO_ARCH}

echo -e "\n${YELLOW}[ FASE 4 ] Finalizando instalación${NC}"
LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || echo "127.0.0.1")

run_step "Preparando directorios" "sudo mkdir -p $INSTALL_DIR/{certs,logs} && sudo chown -R $USER:$USER $INSTALL_DIR"
run_step "Copiando archivos" "cp -r ../* $INSTALL_DIR/"
run_step "Generando certificados SSL" "openssl req -x509 -newkey rsa:2048 -keyout $INSTALL_DIR/certs/key.pem -out $INSTALL_DIR/certs/cert.pem -days 3650 -nodes -subj '/CN=auralink' -addext 'subjectAltName=IP:$LOCAL_IP'"

FINAL_CONFIG_PATH="$INSTALL_DIR/config.yaml"

if [ -n "$SHARED_DIR_LINUX" ] && [ -d "$SHARED_DIR_LINUX" ]; then
    FINAL_CONFIG_PATH="$SHARED_DIR_LINUX/config.yaml"
    echo -e "  ${BLUE}ℹ La configuración se guardará en la partición compartida: $FINAL_CONFIG_PATH${NC}"
elif [ -d "/mnt/data/AuraLink" ]; then
    SHARED_DIR_LINUX="/mnt/data/AuraLink"
    FINAL_CONFIG_PATH="$SHARED_DIR_LINUX/config.yaml"
    echo -e "  ${BLUE}ℹ Detectada partición heredada. La configuración se guardará en: $FINAL_CONFIG_PATH${NC}"
fi

sudo python3 -c "
import yaml
config = {
    'server': {'host': '0.0.0.0', 'port': 8443, 'cert': '$INSTALL_DIR/certs/cert.pem', 'key': '$INSTALL_DIR/certs/key.pem'},
    'auth': {'pin_hash': '$PIN_HASH', 'jwt_secret': '$JWT_SECRET', 'jwt_expiry_hours': 24, 'max_attempts': 5, 'lockout_minutes': 30},
    'security': {'allowed_macs': []},
    'boot': {'windows_id': '$WIN_ID', 'arch_id': '$ARCH_ID'},
    'system': {'local_ip': '$LOCAL_IP'}
}
with open('$FINAL_CONFIG_PATH', 'w') as f:
    yaml.dump(config, f)
"

run_step "Configurando permisos sudo" "sudo tee /etc/sudoers.d/auralink-control > /dev/null <<EOF
root ALL=(ALL) NOPASSWD: /usr/bin/efibootmgr
root ALL=(ALL) NOPASSWD: /usr/bin/systemctl poweroff
root ALL=(ALL) NOPASSWD: /usr/bin/systemctl reboot
EOF"

run_step "Instalando servicio" "sudo cp $INSTALL_DIR/scripts/auralink-control.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now auralink-control"

echo -e "\n${BLUE}╔══════════════════════════════════════════════════════╗"
echo -e "║             CONFIGURACIÓN COMPLETADA                 ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo -e "\n  📱 URL App:  ${BLUE}https://$LOCAL_IP:8443${NC}"
echo -e "  💻 MAC:      ${BLUE}$(ip link show $(ip route get 1.1.1.1 2>/dev/null | grep -oP 'dev \K\S+') | grep -oP 'link/ether \K\S+' | head -n1)${NC}\n"