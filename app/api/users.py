"""Administración de usuarios del sistema."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.security import hash_password
from app.db import models
from app.db.database import get_db

router = APIRouter(dependencies=[Depends(require_admin)])


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = "security"


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str | None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.id).all()


@router.post("", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    if data.role not in {"admin", "security", "user"}:
        raise HTTPException(status_code=422, detail="Rol inválido")
    duplicate = db.query(models.User).filter(
        (models.User.email == data.email) | (models.User.username == data.username)
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Email o username ya registrado")
    user = models.User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/active", response_model=UserResponse)
def set_user_active(user_id: int, active: bool, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = active
    db.commit()
    db.refresh(user)
    return user
