# AuraLink Control — Daemon

Controlador remoto de bajo nivel para la gestión integral de energía, hardware y arranque dual en sistemas Linux (Arch) y Windows.

## Características Principales

*   Lógica Nativa Real: Interacción directa con el hardware.
    *   Linux: amixer (audio), brightnessctl (brillo), efibootmgr (EFI NVRAM).
    *   Windows: PyCaw/COM (audio), WMI (brillo), BCDedit (boot manager).
*   AURA Shared Partition: Soporte para una partición compartida (FAT32/exFAT) etiquetada como AURA que actúa como fuente única de verdad para la configuración entre ambos SO.
*   Seguridad: Autenticación mediante PIN (hash bcrypt), tokens JWT firmados, Rate Limiting por IP y lista blanca de MACs.
*   Gestión de Energía: Soporte real para Apagado, Reinicio y Suspensión (S3) en ambas plataformas.

## Instalación y Configuración

### Linux (Arch Linux)
El instalador automatizado gestiona dependencias, certificados SSL y la partición compartida.

```bash
cd auralink-daemon/scripts
sudo ./setup.sh
```
Durante la instalación, podrás elegir crear una partición AURA de 500MB si no existe, la cual se montará persistentemente en /mnt/data/AuraLink.

### Windows
1. Instala Python y asegúrate de marcar "Add to PATH".
2. Ejecuta start_windows.bat como Administrador.
   *   El script detectará automáticamente la letra de unidad de la partición AURA usando PowerShell y la usará como prioridad.

## Gestión de Configuración

El demonio busca el archivo de configuración siguiendo este orden estricto de prioridad:

1.  Variable de Entorno: AURALINK_CONFIG_PATH (si está definida).
2.  Partición Compartida: Archivo config.yaml dentro de la partición con etiqueta AURA.
3.  Local: config.yaml en la raíz del demonio.
4.  Legacy: /opt/auralink-control/config.yaml (Solo Linux).
5.  Original Example: config.yaml.example (como último recurso, sin realizar copias automáticas).

## Desinstalación Completa

Para eliminar el servicio y realizar una depuración profunda del sistema (incluyendo la partición física):

```bash
cd auralink-daemon/scripts
sudo ./uninstall.sh
```
El script permite desmontar la partición AURA, eliminar su entrada en /etc/fstab y borrar físicamente la partición del disco duro.

## Requisitos de Seguridad
*   El servidor corre bajo HTTPS (puerto 8443 por defecto).
*   Se requiere privilegios de Root/Administrador para interactuar con el hardware y la tabla de particiones.
