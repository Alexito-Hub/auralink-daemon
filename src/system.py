import subprocess
import psutil
import logging
import time
import os
import platform

logger = logging.getLogger("auralink.system")
IS_WINDOWS = platform.system() == "Windows"

def get_system_info() -> dict:
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        battery_info = None
        if battery:
            battery_info = {"percent": round(battery.percent, 1), "plugged": battery.power_plugged, "time_left": int(battery.secsleft) if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1}
        
        # Obtener MAC address de la interfaz activa
        mac_address = None
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == (psutil.AF_LINK if not IS_WINDOWS else -1): # -1 is a placeholder, psutil.AF_LINK is what we want
                    # On Windows, psutil.AF_LINK is not always available as a constant in the same way
                    pass 
            # Simplified approach for MAC
            if interface in psutil.net_if_stats() and psutil.net_if_stats()[interface].isup:
                for addr in addrs:
                    if platform.system() == "Windows":
                        if len(addr.address) == 17 and ":" in addr.address or "-" in addr.address:
                            mac_address = addr.address
                            break
                    else:
                        if addr.family == psutil.AF_LINK:
                            mac_address = addr.address
                            break
            if mac_address: break

        temps = {}
        if not IS_WINDOWS:
            try:
                sensors = psutil.sensors_temperatures()
                for key in ["coretemp", "acpitz", "cpu_thermal"]:
                    if key in sensors:
                        temps["cpu"] = round(sensors[key][0].current, 1)
                        break
            except Exception: pass
        lid_closed = False
        if not IS_WINDOWS:
            try:
                lid_path = "/proc/acpi/button/lid"
                if os.path.exists(lid_path):
                    for lid in os.listdir(lid_path):
                        with open(f"{lid_path}/{lid}/state") as f:
                            if "closed" in f.read().lower():
                                lid_closed = True
                                break
            except Exception: pass
        disk = psutil.disk_usage("C:\\" if IS_WINDOWS else "/")
        return {
            "status": "ok", 
            "os": platform.system().lower(), 
            "cpu": {"percent": round(cpu_percent, 1), "cores": psutil.cpu_count()}, 
            "ram": {"percent": round(ram.percent, 1), "used_gb": round(ram.used / 1e9, 2)}, 
            "battery": battery_info, 
            "mac": mac_address,
            "lid_closed": lid_closed, 
            "temps": temps, 
            "disk": {"percent": round(disk.percent, 1)}, 
            "uptime_seconds": int(time.time() - psutil.boot_time())
        }
    except Exception as e: return {"status": "error", "message": str(e)}

def get_volume() -> dict:
    try:
        if IS_WINDOWS:
            # Usar un método de PowerShell que no dependa de módulos externos para el volumen
            cmd = ["powershell", "-Command", "$obj = (New-Object -ComObject SAPI.SpVoice); $obj.Volume"]
            # Nota: SAPI.SpVoice.Volume no es el volumen maestro, es el de la voz. 
            # El volumen maestro en Windows es difícil sin librerías. 
            # Intentaremos usar el comando que ya estaba pero con un fallback.
            cmd_main = ["powershell", "-Command", "(Get-AudioDevice -Playback).Volume"]
            try:
                result = subprocess.run(cmd_main, capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    vol = int(float(result.stdout.strip()))
                    return {"status": "ok", "volume": vol, "muted": False}
            except: pass
            return {"status": "ok", "volume": 50, "muted": False, "note": "requires_audiodevice_module"}
        else:
            result = subprocess.run(["amixer", "sget", "Master"], capture_output=True, text=True)
            import re
            match = re.search(r"\[(\d+)%\]", result.stdout)
            vol = int(match.group(1)) if match else 0
            muted = "[off]" in result.stdout
            return {"status": "ok", "volume": vol, "muted": muted}
    except Exception as e: return {"status": "error", "message": str(e)}

def set_volume(action: str, value: int = 10) -> dict:
    try:
        if IS_WINDOWS and action == "set":
            subprocess.run(["powershell", "-Command", f"(Get-AudioDevice -Playback).Volume = {max(0, min(100, value))}"], timeout=3)
        elif not IS_WINDOWS:
            if action == "set": subprocess.run(["amixer", "sset", "Master", f"{value}%"], timeout=3)
            elif action == "mute": subprocess.run(["amixer", "sset", "Master", "mute"], timeout=3)
            elif action == "unmute": subprocess.run(["amixer", "sset", "Master", "unmute"], timeout=3)
        return {"status": "ok", **get_volume()}
    except Exception as e: return {"status": "error", "message": str(e)}

def get_brightness() -> dict:
    try:
        if IS_WINDOWS:
            cmd = ["powershell", "-Command", "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {"status": "ok", "brightness": int(result.stdout.strip())}
        else:
            result = subprocess.run(["brightnessctl", "g"], capture_output=True, text=True)
            max_b = subprocess.run(["brightnessctl", "m"], capture_output=True, text=True)
            return {"status": "ok", "brightness": int((int(result.stdout.strip()) / int(max_b.stdout.strip())) * 100)}
    except Exception: return {"status": "error", "message": "no_brightness_control"}

def set_brightness(value: int) -> dict:
    v = max(0, min(100, value))
    try:
        if IS_WINDOWS: subprocess.run(["powershell", "-Command", f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {v})"])
        else: subprocess.run(["brightnessctl", "s", f"{v}%"])
        return {"status": "ok", "brightness": v}
    except Exception as e: return {"status": "error", "message": str(e)}

def shutdown_system() -> dict:
    if IS_WINDOWS: os.system("shutdown /s /t 5")
    else: subprocess.Popen(["systemctl", "poweroff"])
    return {"status": "ok"}

def reboot_system() -> dict:
    if IS_WINDOWS: os.system("shutdown /r /t 5")
    else: subprocess.Popen(["systemctl", "reboot"])
    return {"status": "ok"}

def sleep_system() -> dict:
    try:
        if IS_WINDOWS: os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        else: subprocess.Popen(["systemctl", "suspend"])
        return {"status": "ok"}
    except Exception as e: return {"status": "error", "message": str(e)}
