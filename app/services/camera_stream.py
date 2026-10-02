"""Shared, bounded camera streams for authenticated browser viewers."""
import atexit
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path


class SharedStream:
    def __init__(self, source: str):
        worker = Path(__file__).with_name('camera_stream_worker.py')
        self.process = subprocess.Popen(
            [sys.executable, str(worker), source], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0,
        )
        self.condition = threading.Condition()
        self.frame = None
        self.sequence = 0
        self.error = False
        self.viewers = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read_exact(self, size: int):
        data = bytearray()
        while len(data) < size:
            chunk = self.process.stdout.read(size - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    def _read(self):
        try:
            while True:
                header = self._read_exact(4)
                if header is None:
                    break
                size = struct.unpack('!I', header)[0]
                if not 2 <= size <= 4 * 1024 * 1024:
                    break
                frame = self._read_exact(size)
                if frame is None or not frame.startswith(b'\xff\xd8'):
                    break
                with self.condition:
                    self.frame = frame
                    self.sequence += 1
                    self.condition.notify_all()
        finally:
            with self.condition:
                self.error = True
                self.condition.notify_all()

    def frames(self):
        with self.condition:
            self.viewers += 1
        sequence = 0
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.sequence != sequence or self.error, timeout=10)
                    if self.error and self.sequence == sequence:
                        return
                    if self.sequence == sequence:
                        continue
                    sequence = self.sequence
                    frame = self.frame
                yield struct.pack('!I', len(frame)) + frame
        finally:
            with self.condition:
                self.viewers -= 1

    def latest(self, timeout=2.0):
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.frame is None and not self.error:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(remaining)
            return self.frame

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self.process.stdout:
            self.process.stdout.close()


class CameraStreamHub:
    def __init__(self):
        self.lock = threading.Lock()
        self.streams = {}

    def stream(self, source: str):
        with self.lock:
            shared = self.streams.get(source)
            if shared is None or shared.error:
                if shared:
                    shared.stop()
                shared = self.streams[source] = SharedStream(source)
        def managed_frames():
            try:
                yield from shared.frames()
            finally:
                threading.Timer(5, self._retire, args=(source, shared)).start()
        return managed_frames()

    def _retire(self, source: str, shared: SharedStream):
        with self.lock:
            if self.streams.get(source) is not shared or shared.viewers:
                return
            self.streams.pop(source, None)
        shared.stop()

    def latest(self, source: str):
        with self.lock:
            shared = self.streams.get(source)
        return shared.latest() if shared and not shared.error else None

    def stop_all(self):
        with self.lock:
            streams, self.streams = list(self.streams.values()), {}
        for stream in streams:
            stream.stop()


camera_stream_hub = CameraStreamHub()
atexit.register(camera_stream_hub.stop_all)
