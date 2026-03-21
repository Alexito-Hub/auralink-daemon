@echo off
TITLE AuraLink Control Daemon
SETLOCAL
SET DAEMON_DIR=%~dp0..
SET PYTHON_EXE=python.exe
echo [i] Iniciando AuraLink Control para Windows...
cd /d "%DAEMON_DIR%"
%PYTHON_EXE% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: Python no esta instalado o no esta en el PATH.
    echo Descargalo de https://www.python.org/
    pause
    exit /b
)
echo [i] Verificando dependencias de Python...
%PYTHON_EXE% -m pip install fastapi uvicorn psutil pyyaml pyjwt bcrypt cryptography >nul
powershell -Command "if (-not (Get-Module -ListAvailable AudioDeviceCmdlets)) { echo '[!] Aviso: Modulo AudioDeviceCmdlets no encontrado. El control de volumen podria fallar.'; echo '[i] Intenta: Install-Module -Name AudioDeviceCmdlets -Scope CurrentUser' }"
echo [i] Servidor iniciado en el puerto configurado (config.yaml)
echo [i] No cierres esta ventana para mantener el control remoto activo.
echo.
%PYTHON_EXE% src/main.py
pause
