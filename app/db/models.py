"""
Modelos de base de datos (SQLAlchemy ORM)
Todos los datos sensibles están encriptados
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base
import hashlib


# --------------------------------------------
# Modelo de Usuario (Administradores del sistema)
# --------------------------------------------
class User(Base):
    """
    Usuarios del sistema (administradores, personal de seguridad)
    Las contraseñas están hasheadas con bcrypt
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="user")  # admin, security, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con logs
    logs = relationship("AuditLog", back_populates="user")


# --------------------------------------------
# Modelo de Personal Autorizado (Biometría)
# --------------------------------------------
class AuthorizedPerson(Base):
    """
    Personas autorizadas para acceso biométrico
    NO almacenar imágenes faciales crudas
    Solo plantillas biométricas encriptadas
    """
    __tablename__ = "authorized_persons"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    department = Column(String(100))
    position = Column(String(100))
    
    # Plantilla biométrica encriptada (NO imagen cruda)
    biometric_template_encrypted = Column(Text, nullable=False)
    
    # Niveles de acceso
    access_level = Column(Integer, default=1)  # 1-5, 5 = máximo
    authorized_zones = Column(String(500))  # JSON o comma-separated
    
    # Estado
    is_active = Column(Boolean, default=True)
    enrollment_date = Column(DateTime, default=datetime.utcnow)
    last_access = Column(DateTime)
    
    # Consentimiento
    consent_given = Column(Boolean, default=False)
    consent_date = Column(DateTime)
    
    # Relación con logs de acceso
    access_logs = relationship("AccessLog", back_populates="person")


# --------------------------------------------
# Modelo de Logs de Auditoría (Inmutables)
# --------------------------------------------
class AuditLog(Base):
    """
    Logs de auditoría inmutables
    Cada entrada tiene hash del anterior (blockchain-like)
    """
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String(50), nullable=False)  # login, access, enrollment, etc.
    
    # Datos del evento (encriptados si son sensibles)
    event_data = Column(Text)  # JSON
    
    # Integridad
    previous_hash = Column(String(64))  # Hash SHA-256 del log anterior
    current_hash = Column(String(64), nullable=False, index=True)  # Hash de este log
    
    # Usuario que generó el evento
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="logs")
    
    # IP y metadata
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    def compute_hash(self):
        """Computa hash de integridad"""
        data = f"{self.previous_hash or ''}{self.event_type}{self.event_data}{self.timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()


# --------------------------------------------
# Modelo de Logs de Acceso (Control de Acceso)
# --------------------------------------------
class AccessLog(Base):
    """
    Registro de intentos de acceso (exitosos y fallidos)
    """
    __tablename__ = "access_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Persona (si fue identificada)
    person_id = Column(Integer, ForeignKey("authorized_persons.id"))
    person = relationship("AuthorizedPerson", back_populates="access_logs")
    
    # Resultado
    access_granted = Column(Boolean, nullable=False)
    confidence_score = Column(Float)  # Score de reconocimiento facial
    
    # Metadata
    camera_id = Column(String(50))
    zone = Column(String(100))
    
    # Detecciones adicionales
    animal_detected = Column(Boolean, default=False)
    animal_type = Column(String(100))  # dog, cat, etc.
    unknown_person = Column(Boolean, default=False)
    
    # Imagen temporal encriptada (solo si falló, para auditoría)
    # Se elimina después de 24 horas por política de privacidad
    snapshot_encrypted = Column(LargeBinary)
    snapshot_expiry = Column(DateTime)


# --------------------------------------------
# Modelo de Alertas
# --------------------------------------------
class SecurityAlert(Base):
    """
    Alertas de seguridad generadas por el sistema
    """
    __tablename__ = "security_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    alert_type = Column(String(50), nullable=False)  # unauthorized, animal, zone_violation
    
    # Severidad
    severity = Column(String(20))  # low, medium, high, critical
    
    # Descripción
    description = Column(Text, nullable=False)
    
    # Metadata
    zone = Column(String(100))
    camera_id = Column(String(50))
    person_id = Column(Integer, ForeignKey("authorized_persons.id"))
    
    # Estado
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(100))
    
    # Notificaciones enviadas
    email_sent = Column(Boolean, default=False)
    webhook_sent = Column(Boolean, default=False)


# --------------------------------------------
# Modelo de Zonas de Acceso
# --------------------------------------------
class AccessZone(Base):
    """
    Zonas de acceso configurables
    """
    __tablename__ = "access_zones"
    
    id = Column(Integer, primary_key=True, index=True)
    zone_name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    
    # Configuración
    requires_biometric = Column(Boolean, default=True)
    requires_2fa = Column(Boolean, default=False)
    alert_on_unauthorized = Column(Boolean, default=True)
    
    # Estado
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)