"""
Configuración centralizada de la aplicación
Todas las variables de entorno se cargan desde aquí
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración de seguridad y aplicación"""
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
    
    # JWT y Autenticación
    SECRET_KEY: str
    BOOTSTRAP_TOKEN: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Base de Datos
    DATABASE_ENCRYPTION_KEY: str
    DATABASE_URL: str = "sqlite+sqlcipher:///./secure.db"
    
    # Cámara
    CAMERA_ALLOWED_HOSTS: str = ""  # Explicit trusted IPs for outbound video capture
    CAMERA_INDEX: int = 0
    CAMERA_WIDTH: int = 1280
    CAMERA_HEIGHT: int = 720
    CAMERA_FPS: int = 30
    FACE_DETECTION_MODEL: str = "hog"  # o "cnn"
    FACE_RECOGNITION_TOLERANCE: float = 0.6
    
    # YOLOv8
    YOLO_MODEL: str = "yolov8n.pt"
    ANIMAL_CONFIDENCE_THRESHOLD: float = 0.5
    ANIMAL_CLASSES: str = "dog,cat,bird,horse"
    
    # Seguridad IoT
    TLS_ENABLED: bool = True
    TLS_CERT_PATH: str = "./certs/server.crt"
    TLS_KEY_PATH: str = "./certs/server.key"
    RATE_LIMIT_PER_MINUTE: int = 60
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    
    # Liveness Detection
    LIVENESS_ENABLED: bool = True
    LIVENESS_BLINK_THRESHOLD: float = 0.3
    LIVENESS_HEAD_MOVEMENT_THRESHOLD: float = 0.5
    
    # Logs
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/audit.log"
    LOG_RETENTION_DAYS: int = 365
    LOG_INTEGRITY_HASH: bool = True
    
    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    # Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = False
    
    # Alertas
    ALERT_EMAIL: str = ""
    ALERT_WEBHOOK_URL: str = ""
    MAX_UNAUTHORIZED_ATTEMPTS: int = 3
    ALERT_ON_ANIMAL_DETECTION: bool = True
    
    @property
    def get_animal_classes(self) -> List[str]:
        """Retorna lista de clases de animales a detectar"""
        return [c.strip() for c in self.ANIMAL_CLASSES.split(",")]
    
    @property
    def get_cors_origins(self) -> List[str]:
        """Retorna lista de orígenes CORS permitidos"""
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]
    
    @field_validator("SECRET_KEY", "BOOTSTRAP_TOKEN")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("Los secretos de autenticación deben tener al menos 32 caracteres")
        return value

    @field_validator("DATABASE_ENCRYPTION_KEY")
    @classmethod
    def validate_database_key(cls, value: str) -> str:
        if len(value) != 64:
            raise ValueError("DATABASE_ENCRYPTION_KEY debe tener 64 caracteres hexadecimales")
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("DATABASE_ENCRYPTION_KEY debe ser hexadecimal") from exc
        return value

    @field_validator("ALGORITHM")
    @classmethod
    def validate_algorithm(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("Solo se admite HS256 con la configuración actual")
        return value


@lru_cache()
def get_settings() -> Settings:
    """Singleton de configuración"""
    return Settings()


settings = get_settings()
