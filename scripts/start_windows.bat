@echo off
TITLE AuraLink Control Daemon
SETLOCAL
cd /d "%~dp0.."

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: Python no esta instalado.
    pause
    exit /b
)

for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-Volume -FileSystemLabel 'AURA' | Select-Object -ExpandProperty DriveLetter"`) do set AURA_DRIVE=%%i

if defined AURA_DRIVE (
    echo [i] Particion AURA detectada en %%AURA_DRIVE%%:
    if exist "%%AURA_DRIVE%%:\AuraLink\config.yaml" (
        set AURALINK_CONFIG_PATH=%%AURA_DRIVE%%:\AuraLink\config.yaml
    )
)

if not defined AURALINK_CONFIG_PATH (
    if exist "config.yaml" (
        set AURALINK_CONFIG_PATH=config.yaml
    ) else if exist "config.yaml.example" (
        set AURALINK_CONFIG_PATH=config.yaml.example
    )
)

echo [i] Verificando dependencias...
python -m pip install -r requirements.txt --quiet

echo [i] Iniciando AuraLink Control...
python src/main.py

if %errorlevel% neq 0 (
    echo [!] Error: %errorlevel%
    pause
)
pause
