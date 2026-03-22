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
            cmd = f"powershell -Command \"(Get-Volume -FileSystemLabel '{label}').DriveLetter\""
            res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            letter = res.stdout.strip()
            if letter: return Path(f"{letter}:/config.yaml")
        else:
            label_path = Path(f"/dev/disk/by-label/{label}")
            if label_path.exists():
                cmd = f"findmnt -n -o TARGET --source {label_path.resolve()}"
                res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
                mount = res.stdout.strip()
                if mount: return Path(mount) / "config.yaml"
    except Exception: pass
    return None
def get_config_path():
    env_path = os.environ.get("AURALINK_CONFIG_PATH")
    if env_path and Path(env_path).exists(): return Path(env_path)
    label_file = get_path_by_label()
    if label_file and label_file.exists(): return label_file
    system = platform.system()
    if system == "Windows":
        for letter in "CDEFGH":
            p = Path(f"{letter}:/AuraLink/config.yaml")
            if p.exists(): return p
    else:
        for p in [Path("/mnt/c/AuraLink/config.yaml"), Path("/run/media")]:
            if p.exists() and p.is_file(): return p
            if p.is_dir():
                try:
                    for d in p.rglob("AuraLink/config.yaml"): return d
                except Exception: pass
    return Path(__file__).parent.parent / "config.yaml"
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
    return BASE_DIR / "logs"
