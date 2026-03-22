import yaml
import os
import platform
import logging
import shutil
from pathlib import Path

logger = logging.getLogger("auralink.config")

def get_shared_path():
    """Retorna la ruta esperada de la particion compartida."""
    system = platform.system()
    if system == "Windows":
        return Path("D:/AuraLink/config.yaml")
    return Path("/mnt/datos/AuraLink/config.yaml")

def get_config_path():
    """
    Busca el archivo de configuracion en ubicaciones estandar de sistema.
    Prioriza la consistencia entre Linux y Windows mediante una particion compartida.
    """
    # 1. Variable de entorno (Prioridad maxima absoluta)
    env_path = os.environ.get("AURALINK_CONFIG_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    # 2. Rutas de Particion Compartida (Prioridad Alta)
    shared_file = get_shared_path()
    if shared_file.exists():
        return shared_file

    # 3. Rutas especificas por SO (Fallback)
    system = platform.system()
    if system == "Linux":
        paths = [
            Path("/etc/auralink/config.yaml"),
            Path("/opt/auralink-control/config.yaml"),
            Path(__file__).parent.parent / "config.yaml"
        ]
    elif system == "Windows":
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

def attempt_migration(current_path: Path):
    """
    Si tenemos una config local pero existe la carpeta compartida sin config,
    migramos automaticamente para unificar criterios.
    """
    shared_file = get_shared_path()
    shared_dir = shared_file.parent

    # Si la carpeta compartida existe pero el archivo no, y tenemos una config local
    if shared_dir.exists() and not shared_file.exists() and current_path.resolve() != shared_file.resolve():
        try:
            logger.info(f"Detectada particion compartida en {shared_dir}. Migrando configuracion...")
            shutil.copy2(current_path, shared_file)
            logger.info(f"Migracion exitosa: {current_path} -> {shared_file}")
            return shared_file
        except Exception as e:
            logger.error(f"Error durante la migracion de configuracion: {e}")
    
    return current_path

def validate_config(config: dict):
    """Verifica que los campos esenciales existan y aplica valores por defecto."""
    required = {
        "auth": ["pin_hash", "jwt_secret"],
        "boot": ["windows_id", "arch_id"],
        "server": ["host", "port"]
    }
    
    defaults = {
        "auth": {"jwt_expiry_hours": 24, "max_attempts": 5, "lockout_minutes": 15},
        "server": {"cert": "certs/cert.pem", "key": "certs/key.pem"},
        "security": {"allowed_macs": []},
        "boot": {"arch_bcd_id": ""}
    }

    errors = []
    for section, fields in required.items():
        if section not in config:
            errors.append(f"Falta la seccion obligatoria: [{section}]")
            continue
        for field in fields:
            if field not in config[section]:
                errors.append(f"Falta el campo obligatorio: [{section} -> {field}]")

    if errors:
        error_msg = "Errores de configuracion:\n- " + "\n- ".join(errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Aplicar valores por defecto para campos opcionales
    for section, fields in defaults.items():
        if section not in config:
            config[section] = fields
        else:
            for field, value in fields.items():
                if field not in config[section]:
                    config[section][field] = value
    
    return config

def load_config():
    path = get_config_path()
    if not path:
        # Si no existe nada, intentamos usar el del directorio del script como ultimo recurso
        local_path = Path(__file__).parent.parent / "config.yaml"
        if local_path.exists():
            path = local_path
        else:
            raise FileNotFoundError("Critical: config.yaml not found in any standard location.")
    
    # Intentar migrar si es posible
    path = attempt_migration(path)
    
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        validated_config = validate_config(config)
        return validated_config, path

# Carga global
try:
    CONFIG, CONFIG_FILE_PATH = load_config()
    BASE_DIR = CONFIG_FILE_PATH.parent
    logger.info(f"Configuracion cargada y validada desde: {CONFIG_FILE_PATH}")
except Exception as e:
    CONFIG = {}
    CONFIG_FILE_PATH = None
    BASE_DIR = Path(__file__).parent.parent
    print(f"Error critico cargando configuracion: {e}")

def get_log_path():
    """
    Define donde se guardaran los logs segun el sistema.
    Si estamos usando una particion compartida, guardamos los logs alli tambien.
    """
    # Si la config esta en la particion compartida, intentamos crear carpeta logs alli
    if CONFIG_FILE_PATH:
        shared_log_dir = CONFIG_FILE_PATH.parent / "logs"
        try:
            shared_log_dir.mkdir(parents=True, exist_ok=True)
            return shared_log_dir
        except Exception:
            pass # Si falla (permisos), seguimos con el fallback normal

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
