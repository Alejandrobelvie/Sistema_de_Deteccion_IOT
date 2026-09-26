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
import structlog
from sqlalchemy import text

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


def verify_encryption():
    """Verifica que la DB esté encriptada"""
    db = SessionLocal()
    
    try:
        result = db.execute(text("PRAGMA cipher_version"))
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
    
    print("\n✅ Base de datos inicializada correctamente\n")
    print("Registra el primer administrador mediante POST /api/auth/register")


if __name__ == "__main__":
    main()
