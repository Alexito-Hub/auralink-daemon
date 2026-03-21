set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
sudo systemctl stop auralink-control > /dev/null 2>&1 || true
INSTALL_DIR="/opt/auralink-control"
clear
echo -e "${BLUE}╔══════════════════════════════════════════════════════╗"
echo -e "║             AuraLink Control — Installer             ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}[ FASE 1 ] Verificando entorno y dependencias...${NC}"
echo -ne "  >_ Instalando paquetes base y librerías de Python..."
sudo pacman -Sy --noconfirm python python-pip efibootmgr ethtool alsa-utils iproute2 openssl > /dev/null 2>&1
sudo pip install fastapi "uvicorn[standard]" pyjwt bcrypt psutil pyyaml --break-system-packages --root-user-action=ignore --quiet > /dev/null 2>&1
echo -e "\r  ${GREEN}✔ Entorno preparado correctamente.                    ${NC}\n"
echo -e "${YELLOW}[ FASE 2 ] Configuración de Seguridad (App Login)${NC}"
echo -e "  Por favor, define un PIN numérico de 4 dígitos para acceder"
echo -e "  desde la aplicación móvil."
echo ""
while true; do
    read -s -p "  >_ Ingrese PIN (4 dígitos): " PIN; echo ""
    read -s -p "  >_ Confirme su PIN: " PIN2; echo ""
    if [ "$PIN" = "$PIN2" ] && [[ "$PIN" =~ ^[0-9]{4}$ ]]; then 
        break 
    fi
    echo -e "  ${RED}⚠ Error: El PIN debe ser de exactamente 4 números.${NC}"
done
PIN_HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw('$PIN'.encode(), bcrypt.gensalt()).decode())")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo -e "\n  ${GREEN}✔ Seguridad configurada con éxito.${NC}\n"
echo -e "${YELLOW}[ FASE 3 ] Detección de Sistemas Operativos (Dual Boot)${NC}"
echo -e "  Se han detectado los siguientes IDs en su placa base."
echo -e "  Presione [ENTER] para aceptar el ID sugerido o cámbielo."
echo ""
EFI_OUT=$(efibootmgr)
AUTO_WIN=$(echo "$EFI_OUT" | grep -i "Windows Boot Manager" | grep -oP "Boot\K[0-9A-F]{4}" | head -n1)
AUTO_ARCH=$(echo "$EFI_OUT" | grep -Ei "rEFInd|Arch|Linux" | grep -oP "Boot\K[0-9A-F]{4}" | head -n1)
read -p "  >_ ID de Windows [$AUTO_WIN]: " WIN_ID; WIN_ID=${WIN_ID:-$AUTO_WIN}
read -p "  >_ ID de Arch Linux/rEFInd [$AUTO_ARCH]: " ARCH_ID; ARCH_ID=${ARCH_ID:-$AUTO_ARCH}
echo -e "\n  ${GREEN}✔ Configuración de boot guardada.${NC}\n"
echo -e "${YELLOW}[ FASE 4 ] Finalizando despliegue del sistema...${NC}"
echo -ne "  >_ Copiando archivos y activando servicio daemon..."
LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || echo "127.0.0.1")
sudo mkdir -p $INSTALL_DIR/{certs,logs}
sudo cp -r ./* $INSTALL_DIR/ > /dev/null 2>&1 || true
sudo openssl req -x509 -newkey rsa:2048 -keyout $INSTALL_DIR/certs/key.pem \
    -out $INSTALL_DIR/certs/cert.pem -days 3650 -nodes \
    -subj "/CN=auralink" -addext "subjectAltName=IP:$LOCAL_IP" > /dev/null 2>&1
echo "$PIN_HASH" > /tmp/auralink_hash
sudo python3 -c "
import yaml, os
with open('/tmp/auralink_hash', 'r') as h:
    phash = h.read().strip()
config = {
    'server': {'host': '0.0.0.0', 'port': 8443, 'cert': '$INSTALL_DIR/certs/cert.pem', 'key': '$INSTALL_DIR/certs/key.pem'},
    'auth': {'pin_hash': phash, 'jwt_secret': '$JWT_SECRET', 'jwt_expiry_hours': 24, 'max_attempts': 5, 'lockout_minutes': 30},
    'security': {'allowed_macs': []},
    'boot': {'windows_id': '$WIN_ID', 'arch_id': '$ARCH_ID'},
    'system': {'local_ip': '$LOCAL_IP'}
}
with open('$INSTALL_DIR/config.yaml', 'w') as f:
    yaml.dump(config, f)
"
rm /tmp/auralink_hash
sudo tee /etc/sudoers.d/auralink-control > /dev/null <<EOF
root ALL=(ALL) NOPASSWD: /usr/bin/efibootmgr
root ALL=(ALL) NOPASSWD: /usr/bin/systemctl poweroff
root ALL=(ALL) NOPASSWD: /usr/bin/systemctl reboot
EOF
sudo cp auralink-control.service /etc/systemd/system/auralink-control.service
sudo systemctl daemon-reload > /dev/null 2>&1
sudo systemctl enable auralink-control > /dev/null 2>&1
sudo systemctl start auralink-control > /dev/null 2>&1
echo -e "\r  ${GREEN}✔ Servicio AuraLink desplegado y activo.              ${NC}\n"
echo -e "${BLUE}╔══════════════════════════════════════════════════════╗"
echo -e "║             CONFIGURACIÓN COMPLETADA                 ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  📱 URL de la App:  ${BLUE}https://$LOCAL_IP:8443${NC}"
echo -e "  💻 Dirección MAC:  ${BLUE}$(ip link show $(ip route get 1.1.1.1 2>/dev/null | grep -oP 'dev \K\S+') | grep -oP 'link/ether \K\S+' | head -n1)${NC}"
echo ""
echo -e "  ${YELLOW}Use el PIN de 4 dígitos para iniciar sesión.${NC}\n"
