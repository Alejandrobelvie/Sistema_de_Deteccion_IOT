"""Camera inventory and biometric access permissions."""
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.database import get_db
from app.db.models import AuthorizedPerson, Camera

router = APIRouter()


class CameraSettings(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    zone: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=500)
    enabled: bool = True
    detection: Literal["face", "animal", "both"] = "both"

    @field_validator("source")
    @classmethod
    def validate_source(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in {"rtsp", "https", "http"} or not parsed.hostname:
            raise ValueError("Use a valid RTSP or HTTP camera URL")
        if parsed.username or parsed.password:
            raise ValueError("Do not include credentials in the camera URL")
        return value


class CameraResponse(CameraSettings):
    id: int
    model_config = {"from_attributes": True}


@router.get("/cameras", response_model=list[CameraResponse], dependencies=[Depends(get_current_user)])
def cameras(db: Session = Depends(get_db)):
    return db.query(Camera).order_by(Camera.id).all()


@router.post("/cameras", response_model=CameraResponse, status_code=201, dependencies=[Depends(require_admin)])
def create_camera(data: CameraSettings, db: Session = Depends(get_db)):
    camera = Camera(**data.model_dump())
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.put("/cameras/{camera_id}", response_model=CameraResponse, dependencies=[Depends(require_admin)])
def update_camera(camera_id: int, data: CameraSettings, db: Session = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(404, "Camera not found")
    for key, value in data.model_dump().items():
        setattr(camera, key, value)
    db.commit()
    db.refresh(camera)
    return camera


class PermissionSettings(BaseModel):
    authorized_zones: str = Field(max_length=500)
    is_active: bool


class PersonResponse(PermissionSettings):
    id: int
    full_name: str
    employee_id: str
    department: str | None
    consent_given: bool
    model_config = {"from_attributes": True}


@router.get("/permissions", response_model=list[PersonResponse], dependencies=[Depends(require_admin)])
def permissions(db: Session = Depends(get_db)):
    return db.query(AuthorizedPerson).order_by(AuthorizedPerson.full_name).all()


@router.put("/permissions/{person_id}", response_model=PersonResponse, dependencies=[Depends(require_admin)])
def update_permissions(person_id: int, data: PermissionSettings, db: Session = Depends(get_db)):
    person = db.get(AuthorizedPerson, person_id)
    if person is None:
        raise HTTPException(404, "Person not found")
    if data.is_active and not person.consent_given:
        raise HTTPException(422, "Biometric consent is required before granting access")
    person.authorized_zones = data.authorized_zones
    person.is_active = data.is_active
    db.commit()
    db.refresh(person)
    return person
