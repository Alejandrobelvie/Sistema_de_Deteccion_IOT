"""Enrollment y decisiones de acceso biométrico."""
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db import models
from app.db.database import get_db
from app.services.face_recognition_service import face_service

router = APIRouter()
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}


async def decode_image(upload: UploadFile) -> np.ndarray:
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Solo se permiten imágenes JPEG o PNG")
    raw = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="La imagen supera 8 MB")
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail="Imagen inválida")
    return image


@router.post("/enroll", status_code=201, dependencies=[Depends(require_admin)])
async def enroll_person(
    employee_id: str = Form(...),
    full_name: str = Form(...),
    consent_given: bool = Form(...),
    images: list[UploadFile] = File(...),
    department: str | None = Form(None),
    authorized_zones: str = Form(""),
    db: Session = Depends(get_db),
):
    employee_id = employee_id.strip()
    full_name = full_name.strip()
    department = department.strip() if department else None
    authorized_zones = authorized_zones.strip()
    if not consent_given:
        raise HTTPException(status_code=422, detail="Se requiere consentimiento biométrico")
    if not employee_id or len(employee_id) > 50:
        raise HTTPException(status_code=422, detail="El identificador es obligatorio y admite hasta 50 caracteres")
    if not full_name or len(full_name) > 255:
        raise HTTPException(status_code=422, detail="El nombre es obligatorio y admite hasta 255 caracteres")
    if department and len(department) > 100:
        raise HTTPException(status_code=422, detail="El departamento admite hasta 100 caracteres")
    if len(authorized_zones) > 500:
        raise HTTPException(status_code=422, detail="Las zonas autorizadas admiten hasta 500 caracteres")
    if not 3 <= len(images) <= 5:
        raise HTTPException(status_code=422, detail="Se requieren entre 3 y 5 imágenes")
    if db.query(models.AuthorizedPerson).filter(
        models.AuthorizedPerson.employee_id == employee_id
    ).first():
        raise HTTPException(status_code=409, detail="El identificador ya existe")

    decoded = [await decode_image(image) for image in images]
    template = face_service.generate_template_from_images(decoded)
    if template is None:
        raise HTTPException(status_code=422, detail="No se pudo crear una plantilla facial válida")
    person = models.AuthorizedPerson(
        employee_id=employee_id,
        full_name=full_name,
        department=department,
        authorized_zones=authorized_zones,
        biometric_template_encrypted=face_service.save_biometric_template(template),
        consent_given=True,
        consent_date=datetime.utcnow(),
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return {"id": person.id, "employee_id": person.employee_id, "full_name": person.full_name}


@router.post("/recognize", dependencies=[Depends(get_current_user)])
async def recognize(
    image: UploadFile = File(...),
    camera_id: str = Form("default"),
    zone: str = Form("default"),
    db: Session = Depends(get_db),
):
    frame = await decode_image(image)
    people = db.query(models.AuthorizedPerson).filter(
        models.AuthorizedPerson.is_active.is_(True),
        models.AuthorizedPerson.consent_given.is_(True),
    ).all()
    valid_people = []
    encodings = []
    for person in people:
        encoding = face_service.load_biometric_template(person.biometric_template_encrypted)
        if encoding is not None and encoding.shape == (128,):
            valid_people.append(person)
            encodings.append(encoding)

    result = face_service.recognize_face(
        frame,
        encodings,
        [str(person.id) for person in valid_people],
    )
    person = None
    granted = False
    if result:
        person = next((item for item in valid_people if item.id == int(result["person_id"])), None)
        zones = {item.strip() for item in (person.authorized_zones or "").split(",") if item.strip()}
        granted = bool(person and (not zones or zone in zones))
        if granted:
            person.last_access = datetime.utcnow()

    log = models.AccessLog(
        person_id=person.id if person else None,
        access_granted=granted,
        confidence_score=result["confidence"] if result else None,
        camera_id=camera_id[:50],
        zone=zone[:100],
        unknown_person=person is None,
    )
    db.add(log)
    db.commit()
    return {
        "access_granted": granted,
        "person_id": person.id if person else None,
        "confidence": result["confidence"] if result else None,
        "reason": "granted" if granted else "not_recognized_or_liveness_failed",
    }


@router.post("/analyze", dependencies=[Depends(require_admin)])
async def analyze_faces(
    image: UploadFile = File(...),
    zone: str = Form("default"),
    db: Session = Depends(get_db),
):
    """Identify faces for the operator overlay; this does not grant physical access."""
    frame = await decode_image(image)
    height, width = frame.shape[:2]
    locations = face_service.detect_faces(frame)
    people = db.query(models.AuthorizedPerson).filter(
        models.AuthorizedPerson.consent_given.is_(True),
    ).all()
    known = []
    for person in people:
        encoding = face_service.load_biometric_template(person.biometric_template_encrypted)
        if encoding is not None and encoding.shape == (128,):
            known.append((person, encoding))

    results = []
    for location in locations[:20]:
        encoding = face_service.encode_face(frame, location)
        matched = None
        confidence = None
        if encoding is not None and known:
            distances = np.array([np.linalg.norm(item[1] - encoding) for item in known])
            index = int(np.argmin(distances))
            distance = float(distances[index])
            if distance < face_service.tolerance:
                matched = known[index][0]
                confidence = max(0.0, min(1.0, 1.0 - distance))

        if matched:
            zones = {item.strip() for item in (matched.authorized_zones or "").split(",") if item.strip()}
            allowed = bool(matched.is_active and (not zones or zone in zones))
            status = "allowed" if allowed else "denied"
            label = matched.full_name
        else:
            status, label = "unregistered", "Not registered"
        top, right, bottom, left = location
        results.append({
            "status": status,
            "label": label,
            "confidence": confidence,
            "box": {
                "top": max(0, min(height, int(top))),
                "right": max(0, min(width, int(right))),
                "bottom": max(0, min(height, int(bottom))),
                "left": max(0, min(width, int(left))),
            },
        })
    return {"width": width, "height": height, "faces": results}
