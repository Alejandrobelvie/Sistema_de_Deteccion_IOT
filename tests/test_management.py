"""Management workflows use an isolated in-memory database."""
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import management, users
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
        app.include_router(users.router, prefix='/api/users')
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
