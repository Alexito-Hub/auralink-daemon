# AuraLink Daemon
Control remoto multiplataforma (Linux/Windows) para gestión de energía, volumen, brillo y arranque dual.

## Características
- **Multiplataforma**: Lógica nativa para Arch Linux (amixer/brightnessctl) y Windows (PowerShell/WMI).
- **Gestión de Energía**: Apagado, Reinicio y Suspensión remota.
- **Control de Hardware**: Ajuste preciso de volumen y brillo de pantalla.
- **Dual Boot**: Selección del próximo sistema operativo mediante `efibootmgr` (BootNext).
- **Seguridad**: Autenticación JWT, protección por PIN (bcrypt), Rate Limiting y MAC Whitelist opcional.

## Gestión del Servicio (Linux)

### Instalación Automática
El repositorio incluye un script de configuración que instala dependencias, genera certificados SSL, configura el arranque dual y habilita el servicio de sistema:
```bash
cd auralink-daemon/scripts
sudo ./setup.sh
```

### Desinstalación y Limpieza
Para detener los servicios, eliminar la configuración y limpiar los archivos del sistema:
```bash
cd auralink-daemon/scripts
sudo ./uninstall.sh
```

## Configuración Manual (Windows)
1. Instala Python y asegúrate de marcar "Add to PATH".
2. Ejecuta `start_windows.bat` como Administrador para instalar dependencias e iniciar el servidor.
3. (Opcional) Instala el módulo de audio para mayor precisión:
   ```powershell
   Install-Module -Name AudioDeviceCmdlets -Scope CurrentUser
   ```

## Archivos de Configuración
La configuración principal se almacena en `config.yaml`. El sistema busca este archivo en las siguientes ubicaciones (en orden de prioridad):
1. `/mnt/datos/AuraLink/config.yaml` (Partición compartida recomendada para Dual Boot).
2. `/opt/auralink-control/config.yaml`.

Campos clave:
- `pin_hash`: Hash bcrypt de tu PIN de 4 dígitos.
- `boot`: IDs de las entradas EFI (ej: `0001` para Windows, `0002` para Arch).
- `server`: Rutas de certificados SSL (obligatorio para HTTPS en la App).
