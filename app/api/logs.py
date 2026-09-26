"""Consulta protegida de eventos de acceso y auditoría."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db import models
from app.db.database import get_db

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/access")
def access_logs(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    rows = db.query(models.AccessLog).order_by(models.AccessLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "timestamp": row.timestamp,
            "person_id": row.person_id,
            "access_granted": row.access_granted,
            "confidence_score": row.confidence_score,
            "camera_id": row.camera_id,
            "zone": row.zone,
            "unknown_person": row.unknown_person,
        }
        for row in rows
    ]


@router.get("/audit")
def audit_logs(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(limit).all()
