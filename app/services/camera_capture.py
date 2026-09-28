"""Short-lived capture worker. No database, credentials, or frame files."""
import os
import sys
from urllib.parse import urlsplit

MAX_FRAME_BYTES = 4 * 1024 * 1024


def capture(source):
    import cv2
    if source.startswith(('http://', 'https://')):
        import httpx
        import numpy as np
        # Do not follow redirects or inherit proxy configuration.
        with httpx.stream('GET', source, timeout=3, follow_redirects=False, trust_env=False) as response:
            response.raise_for_status()
            if response.headers.get('content-type', '').split(';')[0] != 'image/jpeg':
                raise ValueError('HTTP source must provide a JPEG snapshot')
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_FRAME_BYTES:
                    raise ValueError('Frame too large')
        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    else:
        # RTSP hosts must be explicitly trusted by the server administrator.
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|protocol_whitelist;rtsp,tcp'
        if urlsplit(source).scheme == 'rtsp':
            device = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
        else:
            device = cv2.VideoCapture(source, cv2.CAP_V4L2)
        try:
            if not device.isOpened():
                raise ValueError('Camera could not be opened')
            ok, frame = device.read()
            if not ok:
                raise ValueError('No video frame received')
        finally:
            device.release()
    if frame is None:
        raise ValueError('Invalid image')
    height, width = frame.shape[:2]
    scale = min(1, 1280 / max(width, height))
    if scale < 1:
        frame = cv2.resize(frame, (int(width * scale), int(height * scale)))
    ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    if not ok or encoded.nbytes > MAX_FRAME_BYTES:
        raise ValueError('Frame encoding failed')
    return encoded.tobytes()


if __name__ == '__main__':
    try:
        sys.stdout.buffer.write(capture(sys.argv[1]))
    except Exception:
        # Never return vendor responses, network credentials, or raw internal errors.
        sys.exit(1)
