import subprocess
import yaml
import logging
import re
import os
import platform
from pathlib import Path

logger = logging.getLogger("auralink.boot")

from config import CONFIG

logger = logging.getLogger("auralink.boot")

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
    boot_config = CONFIG["boot"]
    
    if platform.system() == "Windows":
        if target == "windows": return {"status": "ok", "message": "Windows ya es el sistema actual"}
        elif target == "arch": 
            boot_id = boot_config.get("arch_bcd_id") or boot_config.get("arch_id")
            name = "Arch Linux"
        else: return {"status": "error", "message": "Target inválido"}
        
        if not boot_id: return {"status": "error", "message": "ID de Arch no configurado en config.yaml (arch_bcd_id)"}
        
        try:
            # Validar si el ID existe en bcdedit antes de intentar aplicarlo
            check = subprocess.run(["bcdedit", "/enum", "firmware"], capture_output=True, text=True, timeout=5)
            if boot_id.lower() not in check.stdout.lower():
                return {"status": "error", "message": f"El ID {boot_id} no fue encontrado en el BCD de Windows. Verifica config.yaml."}

            result = subprocess.run(["bcdedit", "/bootnext", boot_id], capture_output=True, text=True, timeout=10)
            if result.returncode != 0: 
                return {"status": "error", "message": f"Fallo bcdedit: {result.stderr.strip() or 'Acceso denegado (¿eres Admin?)'}"}
            return {"status": "ok", "message": f"Próximo boot: {name} (vía BCD)", "boot_id": boot_id, "target": target}
        except Exception as e: return {"status": "error", "message": str(e)}
    
    else:
        # Lógica para Linux usando efibootmgr
        if target == "windows": boot_id, name = boot_config["windows_id"], "Windows"
        elif target == "arch": boot_id, name = boot_config["arch_id"], "Arch Linux"
        else: return {"status": "error", "message": "Target inválido"}
        
        if not re.match(r"^[0-9A-Fa-f]{4}$", boot_id): return {"status": "error", "message": "ID inválido para efibootmgr"}
        
        try:
            # Verificar si el ID existe en efibootmgr
            check = subprocess.run(["efibootmgr"], capture_output=True, text=True)
            if f"Boot{boot_id}" not in check.stdout:
                return {"status": "error", "message": f"ID {boot_id} no encontrado en EFI. Ejecuta 'efibootmgr' para verificar."}

            # Intentar con sudo si no somos root, o directo si lo somos
            cmd = ["efibootmgr", "--bootnext", boot_id]
            if os.getuid() != 0: cmd.insert(0, "sudo")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0: return {"status": "error", "message": result.stderr.strip() or "Error de permisos en efibootmgr"}
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
