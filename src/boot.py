import subprocess
import yaml
import logging
import re
import os
import platform
from pathlib import Path

logger = logging.getLogger("auralink.boot")

def load_config():
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists(): config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f: return yaml.safe_load(f)

def get_boot_entries() -> dict:
    try:
        result = subprocess.run(["efibootmgr"], capture_output=True, text=True, timeout=5)
        output = result.stdout
        entries = []
        current, next_boot = None, None
        for line in output.splitlines():
            match_current = re.match(r"BootCurrent: ([0-9A-F]+)", line)
            if match_current: current = match_current.group(1)
            match_next = re.match(r"BootNext: ([0-9A-F]+)", line)
            if match_next: next_boot = match_next.group(1)
            match_entry = re.match(r"Boot([0-9A-F]+)(\*?)\s+(.+)", line)
            if match_entry:
                boot_id = match_entry.group(1)
                active = match_entry.group(2) == "*"
                name = match_entry.group(3).strip()
                entries.append({"id": boot_id, "name": name, "active": active, "is_current": boot_id == current})
        return {"current": current, "next_boot": next_boot, "entries": entries, "status": "ok"}
    except Exception as e: return {"status": "error", "message": str(e)}

def set_next_boot(target: str) -> dict:
    config = load_config()
    boot_config = config["boot"]
    if target == "windows": boot_id, name = boot_config["windows_id"], "Windows 11"
    elif target == "arch": boot_id, name = boot_config["arch_id"], "Arch Linux"
    else: return {"status": "error", "message": "Target inválido"}
    if not re.match(r"^[0-9A-Fa-f]{4}$", boot_id): return {"status": "error", "message": "ID inválido"}
    try:
        result = subprocess.run(["sudo", "efibootmgr", "--bootnext", boot_id], capture_output=True, text=True, timeout=10)
        if result.returncode != 0: return {"status": "error", "message": result.stderr.strip()}
        return {"status": "ok", "message": f"Próximo boot: {name}", "boot_id": boot_id, "target": target}
    except Exception as e: return {"status": "error", "message": str(e)}

def get_current_os() -> str:
    system = platform.system().lower()
    if system == "windows": return "windows"
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                content = f.read().lower()
                if "arch" in content: return "arch"
        return "linux"
    except Exception: return "unknown"
