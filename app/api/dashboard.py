"""Métricas básicas del sistema."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(hours=24)
    recent = db.query(models.AccessLog).filter(models.AccessLog.timestamp >= since)
    return {
        "authorized_people": db.query(func.count(models.AuthorizedPerson.id)).filter(
            models.AuthorizedPerson.is_active.is_(True)
        ).scalar(),
        "access_attempts_24h": recent.count(),
        "granted_24h": recent.filter(models.AccessLog.access_granted.is_(True)).count(),
        "denied_24h": recent.filter(models.AccessLog.access_granted.is_(False)).count(),
        "unresolved_alerts": db.query(func.count(models.SecurityAlert.id)).filter(
            models.SecurityAlert.is_resolved.is_(False)
        ).scalar(),
    }
