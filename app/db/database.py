"""
Configuración de base de datos encriptada con SQLCipher
SQLite + AES-256 encryption
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import structlog

logger = structlog.get_logger()

# --------------------------------------------
# Configuración de Motor SQLCipher
# --------------------------------------------
def get_db_engine():
    """
    Crea engine de SQLAlchemy con SQLCipher
    """
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False,  # Cambiar a True para debug
        pool_pre_ping=True,
        connect_args={
            "check_same_thread": False  # Necesario para SQLite multithread
        }
    )
    
    # Configurar encriptación SQLCipher al conectar
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        
        # Configurar SQLCipher
        cursor.execute(f"PRAGMA key = '{settings.DATABASE_ENCRYPTION_KEY}'")
        cursor.execute("PRAGMA cipher = 'AES-256'")
        cursor.execute("PRAGMA kdf_iter = 256000")  # OWASP recomienda 256k+
        cursor.execute("PRAGMA page_size = 4096")
        cursor.execute("PRAGMA journal_mode = WAL")
        
        # Verificar que la encriptación está activa
        cursor.execute("PRAGMA cipher_version")
        cipher_version = cursor.fetchone()[0]
        logger.info("SQLCipher activo", version=cipher_version)
        
        cursor.close()
    
    return engine


engine = get_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --------------------------------------------
# Dependency para obtener sesión de DB
# --------------------------------------------
def get_db():
    """
    Dependency de FastAPI para obtener sesión de DB
    Usar en endpoints: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------------------------
# Inicialización de Base de Datos
# --------------------------------------------
def init_db():
    """
    Inicializa la base de datos creando tablas
    """
    from app.db import models
    
    logger.info("Creando tablas en base de datos encriptada")
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas exitosamente")


def verify_db_encryption():
    """
    Verifica que la DB esté encriptada
    """
    db = SessionLocal()
    try:
        result = db.execute(text("PRAGMA cipher_version"))
        version = result.fetchone()[0]
        
        if version:
            logger.info("Base de datos encriptada verificada", cipher=version)
            return True
        else:
            logger.error("La base de datos NO está encriptada")
            return False
    except Exception as e:
        logger.error("Error verificando encriptación", error=str(e))
        return False
    finally:
        db.close()
