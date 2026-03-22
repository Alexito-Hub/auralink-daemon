import subprocess
import psutil
import logging
import time
import os
import platform

logger = logging.getLogger("auralink.system")

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    import screen_brightness_control as sbc
    import winreg

def check_fast_startup_windows() -> bool:
    """Retorna True si Fast Startup está activo (peligroso para AURA)."""
    if not IS_WINDOWS: return False
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Power")
        val, _ = winreg.QueryValueEx(key, "HiberbootEnabled")
        return val == 1
    except Exception:
        return False

def get_system_info() -> dict:
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        
        battery_info = None
        if battery:
            battery_info = {"percent": round(battery.percent, 1), "plugged": battery.power_plugged, "time_left": int(battery.secsleft) if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1}
        
        mac_address = None
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        best_interface = None
        
        for interface, info in stats.items():
            if info.isup and interface in addrs:
                if any(kw in interface.lower() for kw in ["eth", "enp", "ethernet", "wifi", "wlan"]):
                    best_interface = interface
                    break
                if not best_interface: best_interface = interface
        
        if best_interface:
            for addr in addrs[best_interface]:
                if IS_WINDOWS:
                    if addr.family == -1 or "-" in addr.address or (":" in addr.address and len(addr.address) == 17):
                        mac_address = addr.address.replace("-", ":").upper()
                        if len(mac_address) == 17: break
                else:
                    if hasattr(psutil, 'AF_LINK') and addr.family == psutil.AF_LINK:
                        mac_address = addr.address.upper()
                        break
        
        temps = {}
        if not IS_WINDOWS:
            try:
                sensors = psutil.sensors_temperatures()
                for key in ["coretemp", "acpitz", "cpu_thermal", "k10temp"]:
                    if key in sensors:
                        temps["cpu"] = round(sensors[key][0].current, 1)
                        break
            except Exception: pass
            
        lid_closed = False
        disk_path = "C:\\" if IS_WINDOWS else "/"
        disk = psutil.disk_usage(disk_path)
        
        fast_startup = check_fast_startup_windows()
        
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
            "uptime_seconds": int(time.time() - psutil.boot_time()),
            "fast_startup_warning": fast_startup
        }
    except Exception as e: return {"status": "error", "message": str(e)}
def get_volume() -> dict:
    try:
        if IS_WINDOWS:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            return {"status": "ok", "volume": int(round(volume.GetMasterVolumeLevelScalar() * 100)), "muted": bool(volume.GetMute())}
        else:
            result = subprocess.run(["amixer", "-c", "0", "sget", "Master"], capture_output=True, text=True)
            if result.returncode != 0 or not result.stdout:
                result = subprocess.run(["amixer", "sget", "Master"], capture_output=True, text=True)
            if result.returncode != 0 or not result.stdout:
                result = subprocess.run(["amixer", "sget", "Speaker"], capture_output=True, text=True)
            import re
            match = re.search(r"\[(\d+)%\]", result.stdout)
            vol = int(match.group(1)) if match else 0
            muted = "[off]" in result.stdout
            return {"status": "ok", "volume": vol, "muted": muted}
    except Exception as e: return {"status": "error", "message": str(e)}
def set_volume(action: str, value: int = 10) -> dict:
    try:
        if IS_WINDOWS:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            if action == "set": volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, value / 100.0)), None)
            elif action == "mute": volume.SetMute(1, None)
            elif action == "unmute": volume.SetMute(0, None)
        else:
            control = "Master"
            card = "0"
            check = subprocess.run(["amixer", "-c", card, "sget", control], capture_output=True)
            if check.returncode != 0:
                check = subprocess.run(["amixer", "sget", "Master"], capture_output=True)
                if check.returncode == 0: card = None
                else: control = "Speaker"
            cmd_base = ["amixer"]
            if card: cmd_base += ["-c", card]
            cmd_base += ["sset", control]
            if action == "set": subprocess.run(cmd_base + [f"{value}%"], timeout=3)
            elif action == "mute": subprocess.run(cmd_base + ["mute"], timeout=3)
            elif action == "unmute": subprocess.run(cmd_base + ["unmute"], timeout=3)
        return {"status": "ok", **get_volume()}
    except Exception as e: return {"status": "error", "message": str(e)}
def get_brightness() -> dict:
    try:
        if IS_WINDOWS:
            brightness = sbc.get_brightness()
            if isinstance(brightness, list): brightness = brightness[0]
            return {"status": "ok", "brightness": int(brightness)}
        else:
            result = subprocess.run(["brightnessctl", "g"], capture_output=True, text=True)
            max_b = subprocess.run(["brightnessctl", "m"], capture_output=True, text=True)
            return {"status": "ok", "brightness": int((int(result.stdout.strip()) / int(max_b.stdout.strip())) * 100)}
    except Exception: return {"status": "error", "message": "no_brightness_control"}
def set_brightness(value: int) -> dict:
    v = max(0, min(100, value))
    try:
        if IS_WINDOWS: sbc.set_brightness(v)
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
