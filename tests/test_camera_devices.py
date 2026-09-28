"""Camera discovery is tested without a network or actual camera capture."""
import subprocess
from types import SimpleNamespace

import pytest
from app.services import camera_devices as devices
from app.api import camera_devices as camera_api
from test_management import workspace


@pytest.mark.parametrize('source', [
    '/etc/passwd', '/dev/video0/../../etc/passwd', 'file:///etc/passwd',
    'http://127.0.0.1/private', 'http://169.254.169.254/latest',
    'rtsp://8.8.8.8/live', 'http://localhost/image', 'http://0.1.2.3/a',
    'rtsp://user:password@192.168.1.2/live', 'http://192.168.1.2:99999/a',
    'http://192.168.1.2/\nother',
])
def test_reject_unsafe_sources(source):
    with pytest.raises(ValueError):
        devices.validate_source(source)


def test_capture_requires_explicit_allowlist(monkeypatch):
    monkeypatch.setattr(devices.settings, 'CAMERA_ALLOWED_HOSTS', '')
    with pytest.raises(ValueError, match='not approved'):
        devices.capture_source('rtsp://192.168.1.3/live')
    monkeypatch.setattr(devices.settings, 'CAMERA_ALLOWED_HOSTS', '192.168.1.3')
    assert devices.capture_source('rtsp://192.168.1.3/live').startswith('rtsp:')
    monkeypatch.setattr(devices, 'discover_usb', lambda: {'devices': []})
    with pytest.raises(ValueError, match='disconnected'):
        devices.capture_source('/dev/video0')


def probe(url='http://192.168.1.3/onvif/device_service', message='request-id'):
    return f'''<Envelope xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing" xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"><a:RelatesTo>{message}</a:RelatesTo><d:ProbeMatch><d:XAddrs>{url}</d:XAddrs><d:Scopes>onvif://www.onvif.org/name/Front%20door</d:Scopes></d:ProbeMatch></Envelope>'''.encode()


def test_discovery_validates_sender_and_request():
    found = devices.parse_probe(probe(), '192.168.1.3', 'request-id')
    assert found[0]['name'] == 'Front door'
    assert found[0]['source'] == ''  # A management service is not a video stream.
    assert not devices.parse_probe(probe(), '192.168.1.4', 'request-id')
    assert not devices.parse_probe(probe(), '192.168.1.3', 'different-request')
    assert not devices.parse_probe(b'<!DOCTYPE foo><foo/>', '192.168.1.3', 'request-id')
    assert not devices.parse_probe(b'x' * 32769, '192.168.1.3', 'request-id')


def test_bluetooth_unavailable_and_timeout(monkeypatch):
    monkeypatch.setattr(devices.shutil, 'which', lambda _: None)
    assert devices.discover_bluetooth()['devices'] == []
    monkeypatch.setattr(devices.shutil, 'which', lambda _: '/usr/bin/bluetoothctl')
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('bluetoothctl', 4)
    monkeypatch.setattr(devices.subprocess, 'run', timeout)
    assert 'four seconds' in devices.discover_bluetooth()['message']


@pytest.mark.asyncio
async def test_discovery_and_snapshot_require_admin(workspace, monkeypatch):
    client, _, user = workspace
    user.role = 'user'
    assert (await client.post('/api/cameras/discovery/usb')).status_code == 403
    assert (await client.post('/api/cameras/1/snapshot')).status_code == 403
    assert (await client.delete('/api/cameras/1')).status_code == 403


@pytest.mark.asyncio
async def test_discovery_capture_lifecycle(workspace, monkeypatch):
    client, _, _ = workspace
    monkeypatch.setattr(devices, 'discover_usb', lambda: {'devices': [{'source': '/dev/video0'}], 'message': 'Found'})
    discovery = await client.post('/api/cameras/discovery/usb')
    assert discovery.json()['devices'][0]['source'] == '/dev/video0'
    created = await client.post('/api/cameras', json={'name': 'Laptop', 'zone': 'Office', 'source': '/dev/video0'})
    assert created.status_code == 201
    camera_id = created.json()['id']
    monkeypatch.setattr(camera_api.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout=b'\xff\xd8jpeg-test'))
    response = await client.post(f'/api/cameras/{camera_id}/snapshot')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['content-type'] == 'image/jpeg'
    camera_api.hardware_lock.acquire()
    try:
        assert (await client.post('/api/cameras/discovery/usb')).status_code == 409
    finally:
        camera_api.hardware_lock.release()
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('capture', 8)
    monkeypatch.setattr(camera_api.subprocess, 'run', timeout)
    assert (await client.post(f'/api/cameras/{camera_id}/snapshot')).status_code == 504
    assert not camera_api.hardware_lock.locked()
    await client.put(f'/api/cameras/{camera_id}', json={'name': 'Laptop', 'zone': 'Office', 'source': '/dev/video0', 'enabled': False})
    assert (await client.post(f'/api/cameras/{camera_id}/snapshot')).status_code == 409
    assert (await client.delete(f'/api/cameras/{camera_id}')).status_code == 204
    assert (await client.post(f'/api/cameras/{camera_id}/snapshot')).status_code == 404
