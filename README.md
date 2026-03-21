# AuraLink Daemon
Control remoto multiplataforma (Linux/Windows) para gestión de energía, volumen, brillo y arranque dual.

## Características
- **Multiplataforma**: Lógica nativa para Arch Linux (amixer/brightnessctl) y Windows (PowerShell/WMI).
- **Gestión de Energía**: Apagado, Reinicio y Suspensión remota.
- **Control de Hardware**: Ajuste preciso de volumen y brillo de pantalla.
- **Dual Boot**: Selección del próximo sistema operativo mediante `efibootmgr` (BootNext).
- **Seguridad**: Autenticación JWT, protección por PIN (bcrypt), Rate Limiting y MAC Whitelist opcional.

## Instalación

### Linux (Arch)
1. Copia la carpeta a `/opt/auralink-control`.
2. Instala dependencias: `pip install fastapi uvicorn psutil pyyaml pyjwt bcrypt cryptography`.
3. Asegúrate de tener `brightnessctl` y `amixer` instalados.
4. Habilita el servicio:
   ```bash
   sudo cp auralink-control.service /etc/systemd/system/
   sudo systemctl enable --now auralink-control
   ```

### Windows
1. Instala Python y asegúrate de marcar "Add to PATH".
2. Ejecuta `start_windows.bat` como Administrador para instalar dependencias e iniciar el servidor.
3. (Opcional) Instala el módulo de audio para mayor precisión:
   ```powershell
   Install-Module -Name AudioDeviceCmdlets -Scope CurrentUser
   ```

## Configuración
Edita `config.yaml` para ajustar:
- `pin_hash`: Hash bcrypt de tu PIN.
- `boot`: IDs de las entradas EFI para Linux y Windows.
- `server`: Rutas de certificados SSL (necesario para HTTPS).
