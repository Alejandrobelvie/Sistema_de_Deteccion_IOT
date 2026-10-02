"""Persistent isolated capture worker; emits length-prefixed JPEG frames."""
import os
import signal
import struct
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

running = True


def stop(_signum, _frame):
    global running
    running = False


def output(frame):
    import cv2
    height, width = frame.shape[:2]
    scale = min(1, 1280 / max(width, height))
    if scale < 1:
        frame = cv2.resize(frame, (int(width * scale), int(height * scale)))
    ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
    if not ok or encoded.nbytes > 4 * 1024 * 1024:
        return
    data = encoded.tobytes()
    sys.stdout.buffer.write(struct.pack('!I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def run(source):
    import cv2
    if source.startswith(('http://', 'https://')):
        from app.services.camera_capture import capture
        while running:
            data = capture(source)
            sys.stdout.buffer.write(struct.pack('!I', len(data)) + data)
            sys.stdout.buffer.flush()
            time.sleep(.5)
        return
    os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|protocol_whitelist;rtsp,tcp'
    if urlsplit(source).scheme == 'rtsp':
        camera = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
    else:
        camera = cv2.VideoCapture(int(source.removeprefix('/dev/video')), cv2.CAP_V4L2)
    try:
        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not camera.isOpened():
            raise RuntimeError('camera unavailable')
        interval = 1 / 12
        while running:
            started = time.monotonic()
            ok, frame = camera.read()
            if not ok:
                break
            output(frame)
            time.sleep(max(0, interval - (time.monotonic() - started)))
    finally:
        camera.release()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        run(sys.argv[1])
    except Exception:
        sys.exit(1)
