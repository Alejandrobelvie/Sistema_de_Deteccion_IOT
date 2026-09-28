"""Bounded Linux device discovery. Discovery never opens a video stream."""
import ipaddress
import re
import shutil
import socket
import struct
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

from app.core.config import settings


def validate_source(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r'/dev/video[0-9]+', value):
        return value
    if any(ord(c) < 32 for c in value):
        raise ValueError('Control characters are not permitted')
    parsed = urlsplit(value)
    if parsed.scheme not in {'rtsp', 'http', 'https'} or not parsed.hostname:
        raise ValueError('Use /dev/videoN, an RTSP URL, or an HTTP JPEG snapshot URL')
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Camera URLs must not contain credentials or fragments')
    try:
        address = ipaddress.ip_address(parsed.hostname)
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Use a literal private camera IP address and a valid port') from exc
    if not any(address in ipaddress.ip_network(network) for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7')):
        raise ValueError('Only private camera IP addresses are accepted')
    if port == 0:
        raise ValueError('Invalid port')
    return value


def capture_source(source: str) -> str:
    source = validate_source(source)
    if source.startswith('/dev/'):
        if source not in {item['source'] for item in discover_usb()['devices']}:
            raise ValueError('Camera is disconnected, inaccessible, or not a video capture device')
    else:
        allowed = {item.strip() for item in settings.CAMERA_ALLOWED_HOSTS.split(',') if item.strip()}
        if urlsplit(source).hostname not in allowed:
            raise ValueError('Camera IP is not approved. Add it to CAMERA_ALLOWED_HOSTS in the server .env and restart')
    return source


def discover_usb() -> dict:
    root = Path('/sys/class/video4linux')
    if not root.exists():
        return {'devices': [], 'message': 'No Linux video devices found. Check the driver and USB connection.'}
    import fcntl
    devices = []
    inaccessible = 0
    for entry in sorted(root.glob('video*'))[:64]:
        source = '/dev/' + entry.name
        try:
            with open(source, 'rb', buffering=0) as device:
                capability = bytearray(104)
                fcntl.ioctl(device, 0x80685600, capability)  # VIDIOC_QUERYCAP
            caps, device_caps = struct.unpack_from('II', capability, 84)
            caps = device_caps if caps & 0x80000000 else caps
            if not caps & (0x00000001 | 0x00001000):  # VIDEO_CAPTURE / MPLANE, not metadata
                continue
            name = (entry / 'name').read_text().strip()[:100]
            devices.append({'name': name, 'source': source, 'transport': 'local', 'status': 'available', 'can_register': True})
        except (OSError, ValueError):
            inaccessible += 1
    return {'devices': devices, 'message': f'{len(devices)} capture device(s) found; {inaccessible} inaccessible node(s). Local devices include USB and built-in cameras.'}


def parse_probe(data: bytes, peer: str, message_id: str) -> list[dict]:
    if len(data) > 32768 or b'<!' in data or b'\x00' in data:
        return []
    try:
        root = ElementTree.fromstring(data)
        if root.findtext('.//{http://schemas.xmlsoap.org/ws/2004/08/addressing}RelatesTo') != message_id:
            return []
        results = []
        for match in root.findall('.//{http://schemas.xmlsoap.org/ws/2005/04/discovery}ProbeMatch')[:32]:
            urls = (match.findtext('{http://schemas.xmlsoap.org/ws/2005/04/discovery}XAddrs') or '').split()
            for url in urls[:8]:
                parsed = urlsplit(url)
                if parsed.hostname != peer or parsed.scheme not in {'http', 'https'}:
                    continue
                validate_source(url)
                scopes = match.findtext('{http://schemas.xmlsoap.org/ws/2005/04/discovery}Scopes') or ''
                names = [unquote(s.rsplit('/', 1)[-1]) for s in scopes.split() if '/name/' in s]
                results.append({'name': (names[0] if names else 'ONVIF camera')[:100], 'source': '', 'address': peer, 'service_url': url, 'transport': 'network', 'status': 'discovered', 'can_register': True})
                break
        return results
    except (ElementTree.ParseError, ValueError):
        return []


def discover_network() -> dict:
    message_id = 'urn:uuid:' + str(uuid.uuid4())
    probe = f'''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing" xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" xmlns:dn="http://www.onvif.org/ver10/network/wsdl"><s:Header><a:MessageID>{message_id}</a:MessageID><a:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To><a:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action></s:Header><s:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></s:Body></s:Envelope>'''.encode()
    devices = {}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            sock.bind(('', 0))
            sock.sendto(probe, ('239.255.255.250', 3702))
            deadline = time.monotonic() + 3
            packets = 0
            while time.monotonic() < deadline and packets < 128:
                sock.settimeout(max(.01, deadline - time.monotonic()))
                try:
                    data, peer = sock.recvfrom(32769)
                except socket.timeout:
                    break
                packets += 1
                for item in parse_probe(data, peer[0], message_id):
                    devices[item['service_url']] = item
    except OSError:
        return {'devices': [], 'message': 'Network discovery unavailable. Check multicast permissions and the network interface.'}
    return {'devices': list(devices.values()), 'message': 'ONVIF discovery on the server network completed. Wi-Fi and Ethernet cameras must have discovery enabled. Enter the vendor RTSP or JPEG URL to capture video.'}


def discover_bluetooth() -> dict:
    if not shutil.which('bluetoothctl'):
        return {'devices': [], 'message': 'BlueZ bluetoothctl is not installed on this server.'}
    try:
        result = subprocess.run(['bluetoothctl', 'devices', 'Connected'], capture_output=True, text=True, timeout=4, check=False)
        devices = []
        for line in result.stdout.splitlines()[:64]:
            match = re.fullmatch(r'Device ([0-9A-Fa-f:]{17}) (.+)', line)
            if match:
                devices.append({'name': match[2][:100], 'address': match[1], 'source': '', 'transport': 'bluetooth', 'status': 'video_driver_required', 'can_register': False})
        return {'devices': devices, 'message': 'Connected Bluetooth devices only; these are not confirmed cameras. Pair devices in the operating system. Video requires a vendor driver exposing /dev/videoN or a Wi-Fi stream.' if result.returncode == 0 else 'Bluetooth unavailable. Check that the adapter and Bluetooth service are enabled.'}
    except (OSError, subprocess.TimeoutExpired):
        return {'devices': [], 'message': 'Bluetooth service did not respond within four seconds.'}
