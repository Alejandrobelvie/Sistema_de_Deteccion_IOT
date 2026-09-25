"""
Endpoints de autenticación (login, registro, JWT)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel, EmailStr
import structlog

from app.db.database import get_db
from app.db import models
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    login_rate_limiter
)

logger = structlog.get_logger()

router = APIRouter()


# --------------------------------------------
# Schemas
# --------------------------------------------
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    role: str
    
    class Config:
        from_attributes = True


# --------------------------------------------
# Endpoints
# --------------------------------------------
@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Registro de nuevo usuario administrador
    """
    # Verificar si el email ya existe
    existing_user = db.query(models.User).filter(
        models.User.email == user_data.email
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # Verificar si el username ya existe
    existing_username = db.query(models.User).filter(
        models.User.username == user_data.username
    ).first()
    
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El username ya está en uso"
        )
    
    # Crear usuario con password hasheado
    hashed_pw = hash_password(user_data.password)
    
    db_user = models.User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_pw,
        full_name=user_data.full_name,
        role="admin"  # Primer usuario es admin por defecto
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    logger.info("Usuario registrado", user_id=db_user.id, email=db_user.email)
    
    return db_user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login de usuario con OAuth2 password flow
    Retorna access token y refresh token
    """
    # Rate limiting
    client_ip = request.client.host
    
    if login_rate_limiter.is_locked_out(client_ip):
        logger.warning("IP bloqueada por rate limiting", ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Intente más tarde."
        )
    
    # Buscar usuario
    user = db.query(models.User).filter(
        models.User.email == form_data.username
    ).first()
    
    if not user:
        # Registrar intento fallido (sin revelar si el usuario existe)
        login_rate_limiter.record_attempt(client_ip)
        logger.warning("Intento de login fallido", username=form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verificar contraseña
    if not verify_password(form_data.password, user.hashed_password):
        login_rate_limiter.record_attempt(client_ip)
        logger.warning("Contraseña incorrecta", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verificar que el usuario esté activo
    if not user.is_active:
        logger.warning("Usuario inactivo intentó login", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    # Crear tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "email": user.email}
    )
    
    logger.info("Login exitoso", user_id=user.id, email=user.email)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    Refresca access token usando refresh token
    """
    payload = verify_token(refresh_token, token_type="refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado"
        )
    
    user_id = int(payload["sub"])
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo"
        )
    
    # Crear nuevo access token
    new_access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    
    return {
        "access_token": new_access_token,
        "refresh_token": refresh_token,  # Mismo refresh token
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    token: str = Depends(OAuth2PasswordRequestForm),
    db: Session = Depends(get_db)
):
    """
    Obtiene información del usuario actual
    """
    payload = verify_token(token, token_type="access")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )
    
    user_id = int(payload["sub"])
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    return user