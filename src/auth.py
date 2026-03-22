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
        max_attempts = CONFIG["auth"]["max_attempts"]
        lockout_minutes = CONFIG["auth"]["lockout_minutes"]
        if success:
            self.attempts[identifier] = []
            return False
        now = time.time()
        self.attempts[identifier] = [t for t in self.attempts[identifier] if now - t < 600]
        self.attempts[identifier].append(now)
        if len(self.attempts[identifier]) >= max_attempts:
            self.locked[identifier] = now + (lockout_minutes * 60)
            return True
        return False

rate_limiter = RateLimiter()

def verify_pin(pin: str) -> bool:
    try:
        stored_hash = CONFIG["auth"]["pin_hash"].encode('utf-8')
        return bcrypt.checkpw(pin.encode('utf-8'), stored_hash)
    except Exception: return False

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
    allowed = CONFIG["security"].get("allowed_macs", [])
    if not allowed: return True
    if not mac: return False
    return mac.lower() in [m.lower() for m in allowed]
