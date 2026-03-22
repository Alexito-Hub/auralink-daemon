import yaml
import os
import platform
import logging
import shutil
import subprocess
from pathlib import Path
logger = logging.getLogger("auralink.config")
def get_path_by_label(label="AURA"):
    system = platform.system()
    try:
        if system == "Windows":
            cmd = ["powershell", "-Command", f"Get-Volume -FileSystemLabel '{label}' | Select-Object -ExpandProperty DriveLetter"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            letter = res.stdout.strip()
            if letter: return Path(f"{letter}:/AuraLink/config.yaml")
        else:
            label_path = Path(f"/dev/disk/by-label/{label}")
            if label_path.exists():
                with open("/proc/mounts", "r") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2 and (parts[0] == str(label_path.resolve()) or f"LABEL={label}" in parts[0]):
                            return Path(parts[1]) / "AuraLink/config.yaml"
    except Exception: pass
    return None
def get_config_path():
    env_path = os.environ.get("AURALINK_CONFIG_PATH")
    if env_path and Path(env_path).exists(): return Path(env_path)
    label_file = get_path_by_label()
    if label_file and label_file.exists(): return label_file
    system = platform.system()
    if system == "Windows":
        program_data = os.environ.get("ProgramData")
        paths = [
            Path(program_data) / "AuraLink" / "config.yaml" if program_data else None,
            Path("C:/AuraLink/config.yaml"),
            Path("D:/AuraLink/config.yaml"),
            Path(__file__).parent.parent / "config.yaml"
        ]
    else:
        paths = [
            Path("/mnt/data/AuraLink/config.yaml"),
            Path("/etc/auralink/config.yaml"),
            Path("/opt/auralink-control/config.yaml"),
            Path("/mnt/c/AuraLink/config.yaml"),
            Path(__file__).parent.parent / "config.yaml"
        ]
    for p in paths:
        if p and p.exists(): return p
    return None
def attempt_migration(current_path: Path):
    shared_file = get_path_by_label()
    if shared_file:
        shared_dir = shared_file.parent
        if shared_dir.exists() and not shared_file.exists() and current_path.resolve() != shared_file.resolve():
            try:
                shutil.copy2(current_path, shared_file)
                return shared_file
            except Exception: pass
    return current_path
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
    path = get_config_path()
    if not path:
        path = Path(__file__).parent.parent / "config.yaml"
        if not path.exists(): raise FileNotFoundError("config.yaml not found")
    path = attempt_migration(path)
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
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
    if platform.system() == "Linux":
        p = Path("/var/log/auralink")
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except: pass
    p = BASE_DIR / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p
