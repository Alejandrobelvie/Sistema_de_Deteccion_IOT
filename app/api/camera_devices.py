"""Administrator-only hardware discovery and bounded, on-demand previews."""
import subprocess
import sys
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.database import get_db
from app.db.models import Camera
from app.services import camera_devices as devices

router = APIRouter(dependencies=[Depends(require_admin)])
# Bound simultaneous hardware operations per server worker; captures are never continuous.
hardware_lock = Lock()


@router.post('/discovery/{transport}')
def discover(transport: Literal['usb', 'network', 'bluetooth']):
    if not hardware_lock.acquire(blocking=False):
        raise HTTPException(409, 'Another hardware operation is running. Try again shortly.')
    try:
        return {'transport': transport, **getattr(devices, 'discover_' + transport)()}
    finally:
        hardware_lock.release()


@router.post('/{camera_id}/snapshot')
def snapshot(camera_id: int, db: Session = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(404, 'Camera not found')
    if not camera.enabled:
        raise HTTPException(409, 'Camera is disabled')
    try:
        source = devices.capture_source(camera.source)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not hardware_lock.acquire(blocking=False):
        raise HTTPException(409, 'Another hardware operation is running. Try again shortly.')
    try:
        worker = Path(__file__).resolve().parents[1] / 'services' / 'camera_capture.py'
        try:
            result = subprocess.run([sys.executable, str(worker), source], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8, check=False)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, 'Camera timed out. Check the connection and stream URL.')
        except OSError:
            raise HTTPException(503, 'Capture worker could not start')
        if result.returncode or len(result.stdout) > 4 * 1024 * 1024 or not result.stdout.startswith(b'\xff\xd8'):
            raise HTTPException(502, 'No frame received. Check device permissions, camera availability, and the stream URL. HTTP sources must return JPEG snapshots.')
        return Response(result.stdout, media_type='image/jpeg', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    finally:
        hardware_lock.release()
