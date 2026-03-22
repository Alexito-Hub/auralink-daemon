import yaml
import os
import platform
import logging
import shutil
from pathlib import Path
logger = logging.getLogger("auralink.config")
def get_shared_path():
    system = platform.system()
    if system == "Windows":
        return Path("C:/AuraLink/config.yaml")
    mount_points = ["/mnt/c", "/run/media", "/media", "/mnt/windows", "/mnt/data"]
    for base in mount_points:
        base_path = Path(base)
        if not base_path.exists(): continue
        direct_target = base_path / "AuraLink/config.yaml"
        if direct_target.exists(): return direct_target
        try:
            for user_dir in base_path.iterdir():
                if user_dir.is_dir():
                    for drive_dir in user_dir.iterdir():
                        if drive_dir.is_dir():
                            potential = drive_dir / "AuraLink/config.yaml"
                            if potential.exists(): return potential
        except PermissionError: continue
    return Path("/etc/auralink/config.yaml")
def get_config_path():
    env_path = os.environ.get("AURALINK_CONFIG_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    shared_file = get_shared_path()
    if shared_file and shared_file.exists():
        return shared_file
    local_path = Path(__file__).parent.parent / "config.yaml"
    if local_path.exists():
        return local_path
    system = platform.system()
    if system == "Windows":
        program_data = os.environ.get("ProgramData")
        if program_data:
            p = Path(program_data) / "AuraLink/config.yaml"
            if p.exists(): return p
    return local_path
def attempt_migration(current_path: Path):
    shared_file = get_shared_path()
    shared_dir = shared_file.parent
    if shared_dir.exists() and not shared_file.exists() and current_path.resolve() != shared_file.resolve():
        try:
            shared_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current_path, shared_file)
            return shared_file
        except Exception: pass
    return current_path
def validate_config(config: dict):
    required = {"auth": ["pin_hash", "jwt_secret"], "boot": ["windows_id", "arch_id"], "server": ["host", "port"]}
    defaults = {"auth": {"jwt_expiry_hours": 24, "max_attempts": 5, "lockout_minutes": 15}, "server": {"cert": "certs/cert.pem", "key": "certs/key.pem"}, "security": {"allowed_macs": []}, "boot": {"arch_bcd_id": ""}}
    for section, fields in required.items():
        if section not in config: config[section] = {}
    for section, fields in defaults.items():
        if section not in config: config[section] = fields
        else:
            for field, value in fields.items():
                if field not in config[section]: config[section][field] = value
    return config
def load_config():
    path = get_config_path()
    if not path.exists():
        path = Path(__file__).parent.parent / "config.yaml"
    path = attempt_migration(path)
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        if not config: config = {}
        return validate_config(config), path
try:
    CONFIG, CONFIG_FILE_PATH = load_config()
    BASE_DIR = CONFIG_FILE_PATH.parent
except Exception:
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
    return BASE_DIR / "logs"
