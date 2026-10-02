"""Management workflows use an isolated in-memory database."""
import numpy as np
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import access, management, users, camera_devices
from app.api.dependencies import get_current_user
from app.db.database import Base, get_db
from app.db.models import User, AuthorizedPerson


@pytest_asyncio.fixture
async def workspace():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        administrator = User(email='admin@example.com', username='admin', full_name='Admin', role='admin', hashed_password='unused', is_active=True)
        db.add(administrator)
        db.commit()
        app = FastAPI()
        app.include_router(management.router, prefix='/api')
        app.include_router(camera_devices.router, prefix='/api/cameras')
        app.include_router(users.router, prefix='/api/users')
        app.include_router(access.router, prefix='/api/access')
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: administrator
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, db, administrator
    engine.dispose()


@pytest.mark.asyncio
async def test_camera_settings_persist_and_validate(workspace):
    client, _, _ = workspace
    settings = dict(name='Entrance', zone='Lobby', source='rtsp://192.168.1.10/stream', enabled=True, detection='both')
    result = await client.post('/api/cameras', json=settings)
    assert result.status_code == 201
    camera_id = result.json()['id']
    settings['enabled'] = False
    assert ((await client.put(f'/api/cameras/{camera_id}', json=settings))).status_code == 200
    assert (await client.get('/api/cameras')).json()[0]['enabled'] is False
    settings['source'] = 'rtsp://admin:secret@192.168.1.10/stream'
    assert (await client.post('/api/cameras', json=settings)).status_code == 422


@pytest.mark.asyncio
async def test_regular_user_cannot_change_management_settings(workspace):
    client, _, administrator = workspace
    administrator.role = 'user'
    assert (await client.get('/api/cameras')).status_code == 200
    assert (await client.get('/api/permissions')).status_code == 403
    assert (await client.get('/api/users')).status_code == 403
    assert (await client.post('/api/cameras', json={})).status_code == 403


@pytest.mark.asyncio
async def test_permissions_require_consent_and_do_not_expose_biometrics(workspace):
    client, db, _ = workspace
    person = AuthorizedPerson(employee_id='E1', full_name='Person', biometric_template_encrypted='private-template', consent_given=False, is_active=False)
    db.add(person)
    db.commit()
    payload = dict(authorized_zones='Lobby', is_active=True)
    assert (await client.put(f'/api/permissions/{person.id}', json=payload)).status_code == 422
    person.consent_given = True
    db.commit()
    result = await client.put(f'/api/permissions/{person.id}', json=payload)
    assert result.status_code == 200
    assert result.json()['authorized_zones'] == 'Lobby'
    assert 'biometric_template_encrypted' not in (await client.get('/api/permissions')).text


@pytest.mark.asyncio
async def test_admin_cannot_demote_self(workspace):
    client, _, administrator = workspace
    result = await client.put(f'/api/users/{administrator.id}', json=dict(email=administrator.email, full_name='Admin', role='user', is_active=True))
    assert result.status_code == 422


@pytest.mark.asyncio
async def test_admin_can_enroll_biometric_profile(workspace, monkeypatch):
    client, _, _ = workspace

    async def decoded(_):
        return object()

    monkeypatch.setattr(access, 'decode_image', decoded)
    monkeypatch.setattr(access.face_service, 'generate_template_from_images', lambda images: object())
    monkeypatch.setattr(access.face_service, 'save_biometric_template', lambda template: 'encrypted-template')
    data = {
        'employee_id': '  EMP-001  ', 'full_name': '  Test Person  ',
        'department': 'Security', 'authorized_zones': 'Entrance', 'consent_given': 'true',
    }
    files = [('images', (f'face-{index}.jpg', b'image', 'image/jpeg')) for index in range(3)]
    result = await client.post('/api/access/enroll', data=data, files=files)
    assert result.status_code == 201
    assert result.json() == {'id': 1, 'employee_id': 'EMP-001', 'full_name': 'Test Person'}
    duplicate = await client.post('/api/access/enroll', data=data, files=files)
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_enrollment_requires_admin_and_consent(workspace):
    client, _, administrator = workspace
    files = [('images', (f'face-{index}.jpg', b'image', 'image/jpeg')) for index in range(3)]
    data = {'employee_id': 'EMP-002', 'full_name': 'Person', 'consent_given': 'false'}
    assert (await client.post('/api/access/enroll', data=data, files=files)).status_code == 422
    administrator.role = 'user'
    data['consent_given'] = 'true'
    assert (await client.post('/api/access/enroll', data=data, files=files)).status_code == 403


@pytest.mark.asyncio
async def test_camera_analysis_marks_allowed_denied_and_unregistered(workspace, monkeypatch):
    client, db, _ = workspace
    db.add_all([
        AuthorizedPerson(employee_id='A1', full_name='Allowed', biometric_template_encrypted='allowed', consent_given=True, authorized_zones='Entrance', is_active=True),
        AuthorizedPerson(employee_id='D1', full_name='Denied', biometric_template_encrypted='denied', consent_given=True, authorized_zones='Office', is_active=True),
    ])
    db.commit()

    async def decoded(_):
        return np.zeros((100, 100, 3), dtype=np.uint8)

    locations = [(1, 10, 10, 1), (20, 30, 30, 20), (40, 50, 50, 40)]
    monkeypatch.setattr(access, 'decode_image', decoded)
    monkeypatch.setattr(access.face_service, 'detect_faces', lambda frame: locations)
    monkeypatch.setattr(access.face_service, 'load_biometric_template', lambda value: np.zeros(128) if value == 'allowed' else np.full(128, .2))
    monkeypatch.setattr(access.face_service, 'encode_face', lambda frame, location: np.zeros(128) if location[3] == 1 else np.full(128, .2) if location[3] == 20 else np.ones(128))
    result = await client.post('/api/access/analyze', data={'zone': 'Entrance'}, files={'image': ('frame.jpg', b'image', 'image/jpeg')})
    assert result.status_code == 200
    assert [face['status'] for face in result.json()['faces']] == ['allowed', 'denied', 'unregistered']
    assert result.json()['faces'][0]['label'] == 'Allowed'
