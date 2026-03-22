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

if not defined AURA_DRIVE (
    echo [i] Particion AURA encontrada pero sin letra. Asignando letra automaticamente...
    for /f "usebackq tokens=*" %%L in (`powershell -NoProfile -Command "$letters = 70..90 | ForEach-Object { [char]$_ + ':' }; $used = Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Root; $free = $letters | Where-Object { $used -notcontains $_ } | Select-Object -First 1; $vol = Get-Volume -FileSystemLabel 'AURA'; if ($vol) { Set-Partition -InputObject ($vol | Get-Partition) -NewDriveLetter $free.Replace(':', ''); Write-Host $free.Replace(':', '') }"`) do set AURA_DRIVE=%%L
)

if defined AURA_DRIVE (
    echo [i] Particion AURA lista en unidad %AURA_DRIVE%:
    if exist "%AURA_DRIVE%:\AuraLink\config.yaml" (
        set AURALINK_CONFIG_PATH=%AURA_DRIVE%:\AuraLink\config.yaml
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
:: Escuchar en 0.0.0.0 permite que funcione en .23, .43 o cualquier IP del PC
python src/main.py --host 0.0.0.0 --port 8443

if %errorlevel% neq 0 (
    echo [!] Error: %errorlevel%
    pause
)
pause
