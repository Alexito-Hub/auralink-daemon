import jwt
import bcrypt
import time
import yaml
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from config import CONFIG

logger = logging.getLogger("auralink.auth")

class RateLimiter:
    def __init__(self):
        self.attempts: dict = defaultdict(list)
        self.locked: dict = {}

    def is_locked(self, identifier: str) -> tuple[bool, int]:
        if identifier in self.locked:
            unlock_at = self.locked[identifier]
            remaining = int(unlock_at - time.time())
            if remaining > 0: return True, remaining
            else:
                del self.locked[identifier]
                self.attempts[identifier] = []
        return False, 0

    def register_attempt(self, identifier: str, success: bool) -> bool:
        max_attempts = CONFIG["auth"].get("max_attempts", 10)
        lockout_minutes = CONFIG["auth"].get("lockout_minutes", 5)
        if success:
            self.attempts[identifier] = []
            return False
        now = time.time()
        self.attempts[identifier] = [t for t in self.attempts[identifier] if now - t < 300]
        self.attempts[identifier].append(now)
        if len(self.attempts[identifier]) >= max_attempts:
            self.locked[identifier] = now + (lockout_minutes * 60)
            return True
        return False

rate_limiter = RateLimiter()

def verify_pin(pin: str) -> bool:
    try:
        stored_hash = CONFIG["auth"]["pin_hash"]
        if not stored_hash:
            logger.error("PIN_HASH no configurado en config.yaml")
            return False
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.strip().encode('utf-8')
        pin_bytes = pin.encode('utf-8')
        result = bcrypt.checkpw(pin_bytes, stored_hash)
        if not result:
            logger.warning(f"Fallo de autenticación: PIN incorrecto (longitud recibida: {len(pin)})")
        return result
    except Exception as e:
        logger.error(f"Error crítico en verify_pin: {e}")
        return False

def create_token(client_ip: str) -> str:
    secret = CONFIG["auth"]["jwt_secret"]
    expiry_hours = CONFIG["auth"]["jwt_expiry_hours"]
    payload = {
        "sub": client_ip,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expiry_hours),
        "iss": "auralink-control"
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def verify_token(token: str) -> dict | None:
    secret = CONFIG["auth"]["jwt_secret"]
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except Exception: return None

def is_mac_allowed(mac: str | None) -> bool:
    allowed = CONFIG.get("security", {}).get("allowed_macs", [])
    if not allowed: return True
    if not mac: return False
    return mac.lower() in [m.lower() for m in allowed]

def authorize_device(mac: str):
    from config import CONFIG_FILE_PATH, safe_write_config
    if not CONFIG_FILE_PATH: return
    try:
        if "security" not in CONFIG: CONFIG["security"] = {"allowed_macs": []}
        if mac not in CONFIG["security"]["allowed_macs"]:
            CONFIG["security"]["allowed_macs"].append(mac)
            if safe_write_config(CONFIG, CONFIG_FILE_PATH):
                logger.info(f"Dispositivo autorizado automaticamente y guardado: {mac}")
            else:
                logger.error(f"No se pudo guardar la autorización automática para: {mac}")
    except Exception as e:
        logger.error(f"Error al guardar autorizacion automatica: {e}")