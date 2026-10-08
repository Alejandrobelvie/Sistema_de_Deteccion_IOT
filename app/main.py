"""
Sistema de Control de Acceso Biométrico IoT
Punto de entrada principal de la aplicación FastAPI
"""
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.api import auth, users, access, dashboard, logs, management, camera_devices
from app.db.database import init_db
from app.db.database import get_db
from sqlalchemy import text
from sqlalchemy.orm import Session

# Configuración de logging estructurado
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y cierre de la aplicación"""
    # Startup
    logger.info("Iniciando sistema de control de acceso biométrico")
    init_db()
    logger.info("Base de datos encriptada inicializada")
    
    yield
    
    # Shutdown
    logger.info("Cerrando aplicación...")


app = FastAPI(
    title="Visor",
    description="Sistema IoT seguro con reconocimiento facial y detección de animales",
    version="1.0.0",
    lifespan=lifespan,
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusión de routers
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios"])
app.include_router(access.router, prefix="/api/access", tags=["Control de Acceso"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(logs.router, prefix="/api/logs", tags=["Auditoría"])


app.include_router(management.router, prefix="/api", tags=["Management"])
app.include_router(camera_devices.router, prefix="/api/cameras", tags=["Camera devices"])

WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/status", tags=["Root"])
async def root():
    """Endpoint de salud del sistema"""
    return {
        "status": "healthy",
        "system": "Visor",
        "version": "1.0.0",
        "security": {
            "encryption": "AES-256 (SQLCipher)",
            "auth": "JWT + bcrypt",
            "liveness": settings.LIVENESS_ENABLED,
        }
    }


@app.get("/health", tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Verificación de estado para monitoreo"""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    return {"status": "ok", "database": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        workers=settings.WORKERS,
        ssl_keyfile=settings.TLS_KEY_PATH if settings.TLS_ENABLED else None,
        ssl_certfile=settings.TLS_CERT_PATH if settings.TLS_ENABLED else None,
    )
