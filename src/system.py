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
        
        # Obtener MAC address de la interfaz que tiene mas trafico o esta activa
        mac_address = None
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        
        # Priorizar interfaces Ethernet y luego WiFi que esten 'up'
        best_interface = None
        for interface, is_up in {i: stats[i].isup for i in stats}.items():
            if is_up and interface in addrs:
                if "eth" in interface.lower() or "enp" in interface.lower() or "ethernet" in interface.lower():
                    best_interface = interface
                    break
                if not best_interface: best_interface = interface

        if best_interface:
            for addr in addrs[best_interface]:
                if IS_WINDOWS:
                    if "-" in addr.address or (":" in addr.address and len(addr.address) == 17):
                        mac_address = addr.address.replace("-", ":").upper()
                        break
                else:
                    if addr.family == psutil.AF_LINK:
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
            # Script de PowerShell que usa C# embebido para acceder a CoreAudio API (IAudioEndpointVolume)
            ps_script = """
            $code = @'
            using System;
            using System.Runtime.InteropServices;
            [Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
            interface IAudioEndpointVolume {
                int RegisterControlChangeNotify(IntPtr pNotify);
                int UnregisterControlChangeNotify(IntPtr pNotify);
                int GetChannelCount(out int pnChannelCount);
                int SetMasterVolumeLevel(float fLevelDB, Guid pguidEventContext);
                int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
                int GetMasterVolumeLevel(out float pfLevelDB);
                int GetMasterVolumeLevelScalar(out float pfLevel);
                int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext);
                int GetMute(out bool pbMute);
                int GetVolumeStepInfo(out uint pnStep, out uint pnStepCount);
                int VolumeStepUp(Guid pguidEventContext);
                int VolumeStepDown(Guid pguidEventContext);
                int QueryHardwareSupport(out uint pdwHardwareSupport);
                int GetVolumeRange(out float pfMinDB, out float pfMaxDB, out float pfIncrementDB);
            }
            [Guid("D6660639-165F-4E43-909D-9465955A0314"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
            interface IMMDevice {
                int Activate([MarshalAs(UnmanagedType.LPStruct)] Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
            }
            [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
            interface IMMDeviceEnumerator {
                int EnumAudioEndpoints(int dataFlow, int dwStateMask, out object ppDevices);
                int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
            }
            [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorComObject { }
            public class Audio {
                public static float GetVolume() {
                    IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
                    IMMDevice device;
                    enumerator.GetDefaultAudioEndpoint(0, 1, out device);
                    object obj;
                    device.Activate(typeof(IAudioEndpointVolume).GUID, 23, IntPtr.Zero, out obj);
                    IAudioEndpointVolume volume = (IAudioEndpointVolume)obj;
                    float v;
                    volume.GetMasterVolumeLevelScalar(out v);
                    return v;
                }
                public static bool GetMute() {
                    IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
                    IMMDevice device;
                    enumerator.GetDefaultAudioEndpoint(0, 1, out device);
                    object obj;
                    device.Activate(typeof(IAudioEndpointVolume).GUID, 23, IntPtr.Zero, out obj);
                    IAudioEndpointVolume volume = (IAudioEndpointVolume)obj;
                    bool m;
                    volume.GetMute(out m);
                    return m;
                }
                public static void SetVolume(float v) {
                    IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
                    IMMDevice device;
                    enumerator.GetDefaultAudioEndpoint(0, 1, out device);
                    object obj;
                    device.Activate(typeof(IAudioEndpointVolume).GUID, 23, IntPtr.Zero, out obj);
                    IAudioEndpointVolume volume = (IAudioEndpointVolume)obj;
                    volume.SetMasterVolumeLevelScalar(v, Guid.Empty);
                }
                public static void SetMute(bool m) {
                    IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
                    IMMDevice device;
                    enumerator.GetDefaultAudioEndpoint(0, 1, out device);
                    object obj;
                    device.Activate(typeof(IAudioEndpointVolume).GUID, 23, IntPtr.Zero, out obj);
                    IAudioEndpointVolume volume = (IAudioEndpointVolume)obj;
                    volume.SetMute(m, Guid.Empty);
                }
            }
            '@
            Add-Type -TypeDefinition $code
            Write-Output "$([Audio]::GetVolume())|$([Audio]::GetMute())"
            """
            result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                parts = result.stdout.strip().split("|")
                vol = int(float(parts[0].replace(',', '.')) * 100)
                muted = parts[1].lower() == "true"
                return {"status": "ok", "volume": vol, "muted": muted}
            return {"status": "error", "message": result.stderr}
        else:
            # Intentar obtener el control Master en tarjeta 0 (comun)
            result = subprocess.run(["amixer", "-c", "0", "sget", "Master"], capture_output=True, text=True)
            if result.returncode != 0 or not result.stdout:
                # Fallback: intentar sin especificar tarjeta (default)
                result = subprocess.run(["amixer", "sget", "Master"], capture_output=True, text=True)
            
            if result.returncode != 0 or not result.stdout:
                # Fallback: intentar con Speaker
                result = subprocess.run(["amixer", "sget", "Speaker"], capture_output=True, text=True)
            
            import re
            # Buscar el porcentaje [59%]
            match = re.search(r"\[(\d+)%\]", result.stdout)
            vol = int(match.group(1)) if match else 0
            
            # Mute status: buscar [off]
            muted = "[off]" in result.stdout
            return {"status": "ok", "volume": vol, "muted": muted}
    except Exception as e: return {"status": "error", "message": str(e)}

def set_volume(action: str, value: int = 10) -> dict:
    try:
        logger.info(f"SET_VOLUME: action={action}, value={value}")
        if IS_WINDOWS:
            if action == "set":
                v = max(0.0, min(1.0, value / 100.0))
                # Reutilizar el Add-Type es lento, pero para un set individual es aceptable.
                # Una optimizacion futura seria tener un worker de powershell persistente.
                ps_cmd = f"Add-Type -TypeDefinition (New-Object System.Net.WebClient).DownloadString('not_needed_here_stub'); [Audio]::SetVolume({str(v).replace('.', ',')})"
                # Pero como no queremos descargar nada, repetimos el bloque minimo o usamos un comando directo:
                v_str = str(v).replace(',', '.')
                ps_set = f"""
                $code = @'
                using System;
                using System.Runtime.InteropServices;
                [Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                interface IAudioEndpointVolume {{
                    int RegisterControlChangeNotify(IntPtr pNotify);
                    int UnregisterControlChangeNotify(IntPtr pNotify);
                    int GetChannelCount(out int pnChannelCount);
                    int SetMasterVolumeLevel(float fLevelDB, Guid pguidEventContext);
                    int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
                    int GetMasterVolumeLevel(out float pfLevelDB);
                    int GetMasterVolumeLevelScalar(out float pfLevel);
                    int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext);
                    int GetMute(out bool pbMute);
                    int GetVolumeStepInfo(out uint pnStep, out uint pnStepCount);
                    int VolumeStepUp(Guid pguidEventContext);
                    int VolumeStepDown(Guid pguidEventContext);
                    int QueryHardwareSupport(out uint pdwHardwareSupport);
                    int GetVolumeRange(out float pfMinDB, out float pfMaxDB, out float pfIncrementDB);
                }}
                [Guid("D6660639-165F-4E43-909D-9465955A0314"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                interface IMMDevice {{
                    int Activate([MarshalAs(UnmanagedType.LPStruct)] Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
                }}
                [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                interface IMMDeviceEnumerator {{
                    int EnumAudioEndpoints(int dataFlow, int dwStateMask, out object ppDevices);
                    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
                }}
                [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorComObject {{ }}
                public class Audio {{
                    public static void SetVolume(float v) {{
                        IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
                        IMMDevice device;
                        enumerator.GetDefaultAudioEndpoint(0, 1, out device);
                        object obj;
                        device.Activate(typeof(IAudioEndpointVolume).GUID, 23, IntPtr.Zero, out obj);
                        ((IAudioEndpointVolume)obj).SetMasterVolumeLevelScalar(v, Guid.Empty);
                    }}
                    public static void SetMute(bool m) {{
                        IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
                        IMMDevice device;
                        enumerator.GetDefaultAudioEndpoint(0, 1, out device);
                        object obj;
                        device.Activate(typeof(IAudioEndpointVolume).GUID, 23, IntPtr.Zero, out obj);
                        ((IAudioEndpointVolume)obj).SetMute(m, Guid.Empty);
                    }}
                }}
                '@
                if (-not ([System.Management.Automation.PSTypeName]'Audio').Type) {{ Add-Type -TypeDefinition $code }}
                """
                if action == "set":
                    full_cmd = ps_set + f"[Audio]::SetVolume({v_str})"
                elif action == "mute":
                    full_cmd = ps_set + "[Audio]::SetMute($true)"
                elif action == "unmute":
                    full_cmd = ps_set + "[Audio]::SetMute($false)"
                
                subprocess.run(["powershell", "-Command", full_cmd], timeout=5)

        elif not IS_WINDOWS:
            # Intentar determinar la tarjeta y control activo
            control = "Master"
            card = "0"
            check = subprocess.run(["amixer", "-c", card, "sget", control], capture_output=True)
            if check.returncode != 0:
                # Fallback a default Master
                check = subprocess.run(["amixer", "sget", "Master"], capture_output=True)
                if check.returncode == 0:
                    card = None # Usar default
                else:
                    control = "Speaker" # Probar con Speaker
            
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
