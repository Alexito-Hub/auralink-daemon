@echo off
TITLE AuraLink Control Daemon
SETLOCAL

:: Ir al directorio del script y luego subir uno para llegar a la raiz del daemon
cd /d "%~dp0.."
echo [i] Directorio actual: %CD%

:: Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: Python no esta instalado o no esta en el PATH.
    pause
    exit /b
)

:: Verificar config.yaml
if not exist "config.yaml" (
    if exist "config.yaml.example" (
        echo [i] Creando config.yaml desde ejemplo...
        copy "config.yaml.example" "config.yaml"
    ) else (
        echo [!] ERROR: No se encuentra config.yaml ni su ejemplo.
        pause
        exit /b
    )
)

:: Instalar dependencias
echo [i] Verificando dependencias...
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [!] ERROR al instalar dependencias.
    pause
    exit /b
)

:: Iniciar servidor
echo [i] Iniciando AuraLink Control...
echo.
python src/main.py

:: Si el servidor crashea, mostrar el error y pausar
if %errorlevel% neq 0 (
    echo.
    echo [!] El servidor se detuvo con el codigo de error: %errorlevel%
    pause
)

pause
