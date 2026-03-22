import logging
import uvicorn
import platform
import os
import ctypes
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from auth import verify_pin, create_token, verify_token, rate_limiter, is_mac_allowed
from boot import get_boot_entries, set_next_boot, get_current_os
from system import get_system_info, get_volume, set_volume, shutdown_system, reboot_system, get_brightness, set_brightness, sleep_system
from config import CONFIG, BASE_DIR
try:
    log_path = BASE_DIR / "logs"
    log_path.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(log_path / "daemon.log"), logging.StreamHandler()]
except Exception: handlers = [logging.StreamHandler()]
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s", handlers=handlers)
logger = logging.getLogger("auralink")
def is_admin():
    try:
        if platform.system() == "Windows": return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else: return os.getuid() == 0
    except Exception: return False
if not is_admin():
    logger.warning("¡ATENCION! Sin privilegios de Administrador/Root.")
app = FastAPI(title="AuraLink Control", version="1.0.0", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
security = HTTPBearer()
async def require_auth(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload: raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return payload
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded: return forwarded.split(",")[0].strip()
    return request.client.host
class LoginRequest(BaseModel):
    pin: str
    mac: str | None = None
@app.post("/auth/login")
async def login(body: LoginRequest, request: Request):
    ip = get_client_ip(request)
    locked, remaining = rate_limiter.is_locked(ip)
    if locked: raise HTTPException(status_code=429, detail=f"Esperar {remaining}s")
    if not is_mac_allowed(body.mac): raise HTTPException(status_code=403, detail="No autorizado")
    success = verify_pin(body.pin)
    blocked = rate_limiter.register_attempt(ip, success)
    if not success:
        if blocked: raise HTTPException(status_code=429, detail="Bloqueado")
        raise HTTPException(status_code=401, detail="PIN incorrecto")
    from auth import authorize_device
    if not CONFIG.get("security", {}).get("allowed_macs") and body.mac: authorize_device(body.mac)
    return {"token": create_token(ip), "expires_in_hours": CONFIG["auth"]["jwt_expiry_hours"]}
@app.get("/auth/verify")
async def verify(payload: dict = Depends(require_auth)): return {"valid": True, "sub": payload.get("sub")}
@app.get("/boot/status")
async def boot_status(_: dict = Depends(require_auth)):
    entries = get_boot_entries()
    entries["current_os"] = get_current_os()
    return entries
class BootSelectRequest(BaseModel):
    target: str
    reboot_after: bool = False
@app.post("/boot/select")
async def boot_select(body: BootSelectRequest, _: dict = Depends(require_auth)):
    if body.target not in ["windows", "arch"]: raise HTTPException(status_code=400, detail="Target inválido")
    result = set_next_boot(body.target)
    if result["status"] == "error": raise HTTPException(status_code=500, detail=result["message"])
    if body.reboot_after: reboot_system()
    return result
@app.get("/system/info")
async def system_info(_: dict = Depends(require_auth)): return get_system_info()
@app.get("/system/volume")
async def volume_get(_: dict = Depends(require_auth)): return get_volume()
class VolumeRequest(BaseModel):
    action: str
    value: int = 10
@app.post("/system/volume")
async def volume_set(body: VolumeRequest, _: dict = Depends(require_auth)): return set_volume(body.action, body.value)
@app.get("/system/brightness")
async def brightness_get(_: dict = Depends(require_auth)): return get_brightness()
class BrightnessRequest(BaseModel):
    value: int
@app.post("/system/brightness")
async def brightness_set(body: BrightnessRequest, _: dict = Depends(require_auth)): return set_brightness(body.value)
@app.post("/system/shutdown")
async def shutdown(_: dict = Depends(require_auth)): return shutdown_system()
@app.post("/system/reboot")
async def reboot(_: dict = Depends(require_auth)): return reboot_system()
@app.post("/system/sleep")
async def sleep(_: dict = Depends(require_auth)): return sleep_system()
@app.get("/ping")
async def ping(): return {"status": "alive", "service": "auralink-control"}
if __name__ == "__main__":
    host, port = CONFIG["server"]["host"], CONFIG["server"]["port"]
    cert_path, key_path = BASE_DIR / CONFIG["server"]["cert"], BASE_DIR / CONFIG["server"]["key"]
    if cert_path.exists() and key_path.exists():
        uvicorn.run(app, host=host, port=port, ssl_certfile=str(cert_path), ssl_keyfile=str(key_path), log_level="info")
    else: uvicorn.run(app, host=host, port=port, log_level="info")
