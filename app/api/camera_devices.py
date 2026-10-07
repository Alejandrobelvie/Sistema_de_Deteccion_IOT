"""Authenticated camera viewing and administrator-only hardware discovery."""
import subprocess
import sys
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.database import get_db
from app.db.models import Camera
from app.services import camera_devices as devices
from app.services.camera_stream import camera_stream_hub

router = APIRouter()
# Bound simultaneous hardware operations per server worker; captures are never continuous.
hardware_lock = Lock()


@router.post('/discovery/{transport}', dependencies=[Depends(require_admin)])
def discover(transport: Literal['usb', 'network', 'bluetooth']):
    if not hardware_lock.acquire(blocking=False):
        raise HTTPException(409, 'Hay otra operación de hardware en curso. Inténtalo de nuevo en unos instantes.')
    try:
        return {'transport': transport, **getattr(devices, 'discover_' + transport)()}
    finally:
        hardware_lock.release()


@router.post('/{camera_id}/snapshot', dependencies=[Depends(get_current_user)])
def snapshot(camera_id: int, db: Session = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(404, 'Cámara no encontrada')
    if not camera.enabled:
        raise HTTPException(409, 'La cámara está desactivada')
    try:
        source = devices.capture_source(camera.source)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    shared_frame = camera_stream_hub.latest(source)
    if shared_frame:
        return Response(shared_frame, media_type='image/jpeg', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    if not hardware_lock.acquire(blocking=False):
        raise HTTPException(409, 'Hay otra operación de hardware en curso. Inténtalo de nuevo en unos instantes.')
    try:
        worker = Path(__file__).resolve().parents[1] / 'services' / 'camera_capture.py'
        try:
            result = subprocess.run([sys.executable, str(worker), source], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8, check=False)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, 'La cámara agotó el tiempo de espera. Revisa la conexión y la URL de transmisión.')
        except OSError:
            raise HTTPException(503, 'No se pudo iniciar el proceso de captura')
        if result.returncode or len(result.stdout) > 4 * 1024 * 1024 or not result.stdout.startswith(b'\xff\xd8'):
            raise HTTPException(502, 'No se recibió ninguna imagen. Revisa los permisos, la disponibilidad de la cámara y la URL. Las fuentes HTTP deben devolver capturas JPEG.')
        return Response(result.stdout, media_type='image/jpeg', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    finally:
        hardware_lock.release()


@router.get('/{camera_id}/stream', dependencies=[Depends(get_current_user)])
def stream(camera_id: int, db: Session = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(404, 'Cámara no encontrada')
    if not camera.enabled:
        raise HTTPException(409, 'La cámara está desactivada')
    try:
        source = devices.capture_source(camera.source)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return StreamingResponse(
        camera_stream_hub.stream(source), media_type='application/octet-stream',
        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'},
    )
