import yaml
import os
import platform
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("auralink.config")

SHARED_KEYS = ["server", "boot", "system"]
PRIVATE_KEYS = ["auth", "security"]

def get_private_config_path():
    """Retorna la ruta local segura para secretos, fuera de FAT32."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", "C:/ProgramData")) / "AuraLink"
    else:
        base = Path("/etc/auralink")
        if not base.exists():
            # Fallback a home si no hay permisos de root
            base = Path.home() / ".config" / "auralink"
            
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback final al directorio del script si todo falla
        base = Path(__file__).parent.parent
        
    return base / "secrets.yaml"

def get_path_by_label(label="AURA"):
    system = platform.system()
    try:
        if system == "Windows":
            # Listar todos los volumenes para depuración
            cmd_list = ["powershell", "-Command", "Get-Volume | Select-Object DriveLetter, FileSystemLabel | ConvertTo-Json"]
            res_list = subprocess.run(cmd_list, capture_output=True, text=True, timeout=5)
            logger.info(f"Escaneando unidades en Windows...")
            
            cmd = ["powershell", "-Command", f"Get-Volume -FileSystemLabel '{label}' | Select-Object -ExpandProperty DriveLetter"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            letter = res.stdout.strip()
            if letter:
                path = Path(f"{letter}:/AuraLink/config.yaml")
                logger.info(f"¡Partición {label} detectada en unidad {letter}:!")
                return path
            else:
                logger.warning(f"No se encontró ninguna unidad con la etiqueta '{label}'.")
        else:
            label_path = Path(f"/dev/disk/by-label/{label}")
            if label_path.exists():
                with open("/proc/mounts", "r") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2 and (parts[0] == str(label_path.resolve()) or f"LABEL={label}" in parts[0]):
                            return Path(parts[1]) / "AuraLink/config.yaml"
    except Exception as e:
        logger.error(f"Error escaneando particiones: {e}")
    return None

def get_config_path():
    env_path = os.environ.get("AURALINK_CONFIG_PATH")
    if env_path and Path(env_path).exists(): return Path(env_path)
    
    label_file = get_path_by_label()
    if label_file and label_file.exists(): return label_file
    
    for name in ["config.yaml", "config.yaml.example"]:
        local_path = Path(__file__).parent.parent / name
        if local_path.exists(): return local_path
    
    system = platform.system()
    if system == "Linux":
        opt_path = Path("/opt/auralink-control/config.yaml")
        if opt_path.exists(): return opt_path
    
    return None

def safe_write_config(config: dict, shared_path: Path):
    """Escribe la config de forma segura, dividiendo secretos y usando locks."""
    current_os = platform.system().lower()
    private_path = get_private_config_path()
    
    # 1. Dividir config
    shared_data = {k: config[k] for k in SHARED_KEYS if k in config}
    private_data = {k: config[k] for k in PRIVATE_KEYS if k in config}
    
    # 2. Escribir privados (local)
    try:
        with open(private_path, "w", encoding="utf-8") as f:
            yaml.dump(private_data, f)
        if platform.system() != "Windows":
            os.chmod(private_path, 0o600)
    except Exception as e:
        logger.error(f"Error escribiendo secretos: {e}")
        return False

    # 3. Escribir compartidos (AURA) con lock
    if shared_path:
        lock_file = shared_path.parent / ".aura_writer"
        try:
            if lock_file.exists():
                owner = lock_file.read_text().strip()
                if owner != current_os:
                    logger.warning(f"Config lock pertenece a {owner}, no escribimos desde {current_os}")
                    return False
            
            lock_file.write_text(current_os)
            with open(shared_path, "w", encoding="utf-8") as f:
                yaml.dump(shared_data, f)
            return True
        except Exception as e:
            logger.error(f"Error escribiendo en AURA: {e}")
            return False
            
    return True

def validate_config(config: dict):
    required = {"auth": ["pin_hash", "jwt_secret"], "boot": ["windows_id", "arch_id"], "server": ["host", "port"]}
    defaults = {"auth": {"jwt_expiry_hours": 24, "max_attempts": 5, "lockout_minutes": 15}, "server": {"cert": "certs/cert.pem", "key": "certs/key.pem"}, "security": {"allowed_macs": []}, "boot": {"arch_bcd_id": ""}}
    errors = []
    for section, fields in required.items():
        if section not in config:
            errors.append(f"Falta seccion: {section}")
            continue
        for field in fields:
            if field not in config[section]:
                errors.append(f"Falta campo: {section}->{field}")
    if errors: raise ValueError("\n".join(errors))
    for section, fields in defaults.items():
        if section not in config: config[section] = fields
        else:
            for field, value in fields.items():
                if field not in config[section]: config[section][field] = value
    return config

def load_config():
    shared_path = get_config_path()
    private_path = get_private_config_path()
    
    config = {}
    
    # Cargar compartidos
    if shared_path and shared_path.exists():
        with open(shared_path, "r", encoding="utf-8") as f:
            config.update(yaml.safe_load(f) or {})
            
    # Cargar privados
    if private_path and private_path.exists():
        with open(private_path, "r", encoding="utf-8") as f:
            config.update(yaml.safe_load(f) or {})
            
    # Si no hay nada, cargar del default (posible primera ejecución)
    if not config:
        default_path = Path(__file__).parent.parent / "config.yaml"
        if default_path.exists():
            with open(default_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
    
    if not config:
        raise FileNotFoundError("No se encontró configuración válida.")

    validated = validate_config(config)
    
    # Migración automática si es necesario (primera vez que se aplica el split)
    if shared_path and shared_path.exists():
        # Si el shared_path todavía tiene secretos, moverlos y limpiar
        with open(shared_path, "r") as f:
            raw_shared = yaml.safe_load(f) or {}
            if any(k in raw_shared for k in PRIVATE_KEYS):
                logger.info("Migrando secretos de AURA a almacenamiento local seguro...")
                safe_write_config(validated, shared_path)

    return validated, shared_path

try:
    CONFIG, CONFIG_FILE_PATH = load_config()
    BASE_DIR = CONFIG_FILE_PATH.parent if CONFIG_FILE_PATH else Path(__file__).parent.parent
except Exception as e:
    logger.error(f"Error cargando configuración: {e}")
    CONFIG = {}
    CONFIG_FILE_PATH = None
    BASE_DIR = Path(__file__).parent.parent

def get_log_path():
    if CONFIG_FILE_PATH:
        log_dir = CONFIG_FILE_PATH.parent / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir
        except: pass
    if platform.system() == "Linux":
        p = Path("/var/log/auralink")
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except: pass
    p = BASE_DIR / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p
