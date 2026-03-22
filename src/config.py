import yaml
import os
import platform
import logging
from pathlib import Path

logger = logging.getLogger("auralink.config")

def get_config_path():
    """
    Busca el archivo de configuracion en ubicaciones estandar de sistema.
    Prioriza la consistencia entre Linux y Windows.
    """
    # 1. Variable de entorno (Prioridad maxima para configuraciones personalizadas/particiones compartidas)
    env_path = os.environ.get("AURALINK_CONFIG_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    system = platform.system()
    
    # 2. Rutas especificas por SO
    if system == "Linux":
        paths = [
            Path("/etc/auralink/config.yaml"),
            Path("/opt/auralink-control/config.yaml"),
            Path(__file__).parent.parent / "config.yaml"
        ]
    elif system == "Windows":
        # En Windows buscamos en ProgramData o en la raiz del daemon
        program_data = os.environ.get("ProgramData")
        paths = [
            Path(program_data) / "AuraLink" / "config.yaml" if program_data else None,
            Path(__file__).parent.parent / "config.yaml"
        ]
    else:
        paths = [Path(__file__).parent.parent / "config.yaml"]

    for path in paths:
        if path and path.exists():
            return path
            
    return None

def load_config():
    path = get_config_path()
    if not path:
        raise FileNotFoundError("Critical: config.yaml not found in any standard location.")
    
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), path

# Carga global
try:
    CONFIG, CONFIG_FILE_PATH = load_config()
    BASE_DIR = CONFIG_FILE_PATH.parent
    logger.info(f"Configuracion cargada desde: {CONFIG_FILE_PATH}")
except Exception as e:
    CONFIG = {}
    CONFIG_FILE_PATH = None
    BASE_DIR = Path(__file__).parent.parent
    print(f"Error critico cargando configuracion: {e}")

def get_log_path():
    """Define donde se guardaran los logs segun el sistema."""
    if platform.system() == "Linux":
        # Intentar ruta de sistema, fallback a local
        p = Path("/var/log/auralink")
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except:
            return BASE_DIR / "logs"
    else:
        p = BASE_DIR / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p
