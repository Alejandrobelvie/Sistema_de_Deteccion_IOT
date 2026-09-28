# Laptop, Wi-Fi, and phone cameras

Restart FastAPI after updating the application. Open **Cameras** in the web workspace. Server-side discovery, configuration, deletion, and snapshots require an administrator account. Standard users can use the camera attached to their own browser with **Use this device’s camera**.

## Laptop camera

There are two independent options:

1. **Use this device’s camera** opens the browser permission prompt and displays live video locally. Choose another camera in the selector if available. Closing the dialog, navigating away, or signing out stops its tracks. Frames are not uploaded or saved. This also works for USB webcams connected to the browser device.
2. As an administrator, choose **Discover devices → USB / local**, then **Add camera**, enter a zone, and save. Select **Test & preview** to capture one frame through the Python server. On this laptop discovery identified **HP Wide Vision HD Camera** at `/dev/video0`. Metadata-only nodes are excluded.

Server-side local discovery uses Linux V4L2. The server account needs read/write camera permissions; check `/dev/video*` permissions and the desktop session's device access. A camera already in use by another application can fail to open. Device numbering can change after reconnecting; rediscover and update the source if necessary. Browser capture can also be used on other operating systems.

## Wi-Fi camera or phone acting as an IP camera

1. Connect the camera/phone and server to the same network. Enable ONVIF discovery on cameras that support it. Guest-network isolation or blocked multicast can prevent discovery.
2. Choose **Discover devices → Wi-Fi / network**. Discovery runs for three seconds using ONVIF WS-Discovery and does not scan arbitrary ports. Wi-Fi and wired cameras are both network cameras; discovery cannot determine their physical connection type.
3. Choose **Set stream URL** and supply the actual RTSP stream or HTTP JPEG snapshot URL provided by the device. ONVIF's management-service URL is not a video URL. Cameras without ONVIF, including many phone camera apps, can be added manually.
4. Approve the exact camera IP on the server by adding it to `.env`, then restart:

   ```env
   CAMERA_ALLOWED_HOSTS=192.168.1.50,192.168.1.51
   ```

5. Save and select **Test & preview**. Examples of URL formats (the actual path depends on the device):

   ```text
   rtsp://192.168.1.50:554/vendor-stream-path
   http://192.168.1.51:8080/vendor-snapshot-path
   ```

A phone must run software that actually exposes an RTSP stream or JPEG snapshot endpoint to use this path. An MJPEG multipart URL, camera web page, ONVIF service URL, or cloud-app link is not an HTTP JPEG snapshot endpoint. Authenticated camera streams with embedded credentials are not supported by this implementation; use a trusted local gateway that provides an appropriate endpoint. The app does not disable or change camera authentication.

## Phone camera directly in the browser

Open this workspace from the phone using a **trusted HTTPS address**, sign in, go to **Cameras**, and select **Use this device’s camera**. Allow camera access and use the selector to switch between available lenses.

`http://localhost:8000` works for development on the laptop itself. A phone opening `http://<laptop-IP>:8000` is not a secure context and normally cannot request camera access. Serve the app with a trusted TLS certificate or HTTPS reverse proxy; do not disable browser security. For an existing certificate trusted by the phone:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --ssl-certfile /path/to/trusted-server.crt \
  --ssl-keyfile /path/to/server.key --workers 1
```

The certificate must cover the hostname used by the phone. Browser video stays on that phone; this option does not relay live video to the laptop. Use the IP-camera option above for remote phone capture.

## Bluetooth

**Discover devices → Bluetooth** lists connected BlueZ devices, not confirmed video cameras. Pairing happens in the operating system. Generic Bluetooth discovery does not supply a usable video stream. A camera needs a vendor driver exposing a V4L2 device or a separate Wi-Fi video endpoint. Laptop and Wi-Fi capture do not require Bluetooth.

## Capture behavior and safeguards

- Only administrators can ask the server to inspect hardware or capture images. Existing JWT authorization is enforced server-side.
- Local paths are restricted to discovered `/dev/videoN` capture devices. Network sources require literal private IPs; loopback, link-local/metadata, public addresses, DNS hostnames, and URL credentials are rejected.
- Network capture is denied until the exact IP is in the operator-controlled allowlist. Trust only camera endpoints, especially RTSP servers that control the media session. HTTP redirects and environment proxies are disabled; HTTPS certificate verification remains enabled.
- Each capture runs in a separate subprocess, killed after eight seconds. Output is resized to at most 1280 pixels on its longest edge. HTTP JPEG downloads and returned snapshots are limited to 4 MiB. Frames are not saved, and responses use `Cache-Control: no-store`.
- One hardware operation runs per worker at a time. Use `--workers 1` on a laptop; multiple workers have separate locks and can contend for the same physical camera.
- Browser preview requires an explicit browser permission grant and requests no microphone access.
- Discovery is not proof of video connectivity. Preview is a one-frame test, not recording, continuous streaming, biometric recognition, or animal detection. The existing recognition API remains a separate workflow.

## Verification

Run `python -m pytest tests -q`. Tests simulate capture and discovery, covering authorization, disconnected/disabled devices, unsafe addresses, explicit network approval, XML validation, timeouts, snapshots, and deletion. Laptop discovery was verified on the actual device; Wi-Fi/phone frame capture requires your hardware and URL.

Protocol references: [ONVIF specifications](https://www.onvif.org/profiles/specifications/), [OpenCV capture timeouts](https://docs.opencv.org/4.7.0/d4/d15/group__videoio__flags__base.html), and [BlueZ profiles](https://www.bluez.org/profiles/).
