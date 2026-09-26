"""
Módulo de seguridad: JWT, bcrypt, encriptación
Implementa las mejores prácticas de seguridad para 2026
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import hashlib
import hmac
import base64
import secrets
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# --------------------------------------------
# Password Hashing (bcrypt)
# --------------------------------------------
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # OWASP recomienda 12+ para 2026
)


def hash_password(password: str) -> str:
    """
    Hashea una contraseña usando bcrypt con salt único
    Nunca almacenar contraseñas en texto plano
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña contra su hash
    """
    return pwd_context.verify(plain_password, hashed_password)


# --------------------------------------------
# JWT Token Management
# --------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Crea un JWT access token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access", "jti": secrets.token_urlsafe(16)})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    logger.info("Access token creado", exp=expire.isoformat())
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Crea un JWT refresh token (larga duración)
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_urlsafe(16)})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    logger.info("Refresh token creado", exp=expire.isoformat())
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decodifica y verifica un JWT token
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.warning("Token inválido", error=str(e))
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """
    Verifica que el token sea válido y del tipo correcto
    """
    payload = decode_token(token)
    
    if not payload:
        return None
    
    if payload.get("type") != token_type:
        logger.warning("Tipo de token incorrecto")
        return None
    
    return payload


# --------------------------------------------
# Encriptación de Datos Biométricos
# --------------------------------------------
class BiometricEncryption:
    """
    Encriptación AES-256 para plantillas biométricas
    Usa Fernet (symmetric encryption) con clave derivada
    """
    
    def __init__(self, encryption_key: str):
        """
        Inicializa con clave de encriptación (64 caracteres hex)
        """
        if len(encryption_key) != 64:
            raise ValueError("La clave de encriptación debe ser de 64 caracteres hex (256 bits)")
        try:
            bytes.fromhex(encryption_key)
        except ValueError as exc:
            raise ValueError("La clave de encriptación debe contener solo caracteres hexadecimales") from exc
        
        # Derivar clave Fernet desde la clave maestra
        key_material = hashlib.sha256(bytes.fromhex(encryption_key)).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(key_material))
        logger.info("Sistema de encriptación biométrica inicializado")
    
    def encrypt_biometric_template(self, template_bytes: bytes) -> str:
        """
        Encripta una plantilla biométrica
        """
        encrypted = self.cipher.encrypt(template_bytes)
        return encrypted.decode()
    
    def decrypt_biometric_template(self, encrypted_template: str) -> bytes:
        """
        Desencripta una plantilla biométrica
        """
        decrypted = self.cipher.decrypt(encrypted_template.encode())
        return decrypted
    
    def encrypt_image_data(self, image_bytes: bytes) -> str:
        """
        Encripta datos de imagen (uso temporal, antes de eliminar)
        """
        encrypted = self.cipher.encrypt(image_bytes)
        return encrypted.decode()


# --------------------------------------------
# Integridad de Logs (Hash Chain)
# --------------------------------------------
def compute_log_hash(log_entry: str, previous_hash: str = "") -> str:
    """
    Computa hash SHA-256 para integridad de logs
    Cada log incluye el hash del anterior (blockchain-like)
    """
    data = f"{previous_hash}{log_entry}"
    return hashlib.sha256(data.encode()).hexdigest()


def verify_log_integrity(log_entry: str, expected_hash: str, previous_hash: str) -> bool:
    """
    Verifica que un log no haya sido modificado
    """
    computed_hash = compute_log_hash(log_entry, previous_hash)
    return hmac.compare_digest(computed_hash, expected_hash)


# --------------------------------------------
# Rate Limiting Helper
# --------------------------------------------
from collections import defaultdict
import time

class RateLimiter:
    """
    Rate limiter simple en memoria para login attempts
    En producción usar Redis
    """
    
    def __init__(self, max_attempts: int = 5, lockout_minutes: int = 15):
        self.attempts = defaultdict(list)
        self.lockouts = {}
        self.max_attempts = max_attempts
        self.lockout_duration = timedelta(minutes=lockout_minutes).total_seconds()
    
    def is_locked_out(self, identifier: str) -> bool:
        """Verifica si un identifier está bloqueado"""
        if identifier in self.lockouts:
            if time.time() < self.lockouts[identifier]:
                return True
            else:
                del self.lockouts[identifier]
                del self.attempts[identifier]
        return False
    
    def record_attempt(self, identifier: str) -> bool:
        """
        Registra un intento y retorna True si está bloqueado
        """
        if self.is_locked_out(identifier):
            return True
        
        now = time.time()
        # Limpiar intentos viejos (más de 1 hora)
        self.attempts[identifier] = [
            t for t in self.attempts[identifier] 
            if now - t < 3600
        ]
        
        self.attempts[identifier].append(now)
        
        if len(self.attempts[identifier]) >= self.max_attempts:
            self.lockouts[identifier] = now + self.lockout_duration
            logger.warning(
                "Rate limit excedido, usuario bloqueado",
                identifier=identifier,
                lockout_minutes=self.lockout_duration / 60
            )
            return True
        
        return False

    def reset(self, identifier: str) -> None:
        """Limpia intentos después de una autenticación correcta."""
        self.attempts.pop(identifier, None)
        self.lockouts.pop(identifier, None)


# Instancia global de encriptación biometrica
biometric_cipher = BiometricEncryption(settings.DATABASE_ENCRYPTION_KEY)

# Instancia global de rate limiter
login_rate_limiter = RateLimiter(
    max_attempts=settings.MAX_LOGIN_ATTEMPTS,
    lockout_minutes=settings.LOCKOUT_DURATION_MINUTES
)
