"""
Script de inicialización de base de datos
Crear tablas y usuario admin por defecto
"""
import sys
import os

# Agregar root del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine, Base, SessionLocal
from app.db import models
from app.core.security import hash_password
from app.core.config import settings
import structlog

# Configurar logging
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


def create_tables():
    """Crea todas las tablas en la DB encriptada"""
    logger.info("Creando tablas...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas exitosamente")


def create_admin_user():
    """Crea usuario administrador por defecto si no existe"""
    db = SessionLocal()
    
    try:
        # Verificar si ya existe admin
        admin = db.query(models.User).filter(
            models.User.role == "admin"
        ).first()
        
        if admin:
            logger.info("Usuario admin ya existe", email=admin.email)
            return
        
        # Crear admin por defecto
        # NOTA: En producción, forzar cambio de password en primer login
        admin_user = models.User(
            email="admin@empresa.com",
            username="admin",
            hashed_password=hash_password("Admin123!@#"),  # CAMBIAR INMEDIATAMENTE
            full_name="Administrador del Sistema",
            role="admin",
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        logger.warning(
            "Usuario admin creado - CAMBIAR CONTRASEÑA INMEDIATAMENTE",
            user_id=admin_user.id,
            email=admin_user.email
        )
        
        print("\n" + "="*60)
        print("⚠️  USUARIO ADMIN CREADO")
        print("="*60)
        print(f"Email: admin@empresa.com")
        print(f"Password: Admin123!@#")
        print("\n⚠️  CAMBIA LA CONTRASEÑA INMEDIATAMENTE DESPUÉS DEL PRIMER LOGIN")
        print("="*60 + "\n")
        
    finally:
        db.close()


def verify_encryption():
    """Verifica que la DB esté encriptada"""
    db = SessionLocal()
    
    try:
        result = db.execute("PRAGMA cipher_version")
        version = result.fetchone()[0]
        
        if version:
            logger.info("✅ Base de datos encriptada con SQLCipher", version=version)
            print(f"✅ Base de datos encriptada: {version}")
            return True
        else:
            logger.error("❌ La base de datos NO está encriptada")
            print("❌ ERROR: La base de datos NO está encriptada")
            return False
            
    except Exception as e:
        logger.error("Error verificando encriptación", error=str(e))
        print(f"❌ Error: {e}")
        return False
        
    finally:
        db.close()


def main():
    """Función principal"""
    print("\n" + "="*60)
    print("INICIALIZANDO BASE DE DATOS")
    print("="*60 + "\n")
    
    # Verificar encriptación
    if not verify_encryption():
        print("\n❌ La base de datos no está encriptada. Verifica DATABASE_ENCRYPTION_KEY")
        sys.exit(1)
    
    # Crear tablas
    create_tables()
    
    # Crear admin
    create_admin_user()
    
    print("\n✅ Base de datos inicializada correctamente\n")


if __name__ == "__main__":
    main()