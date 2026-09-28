# Installation Guide

This guide installs the current FastAPI backend on Fedora, Ubuntu/Debian, or Windows. Python 3.12 is recommended because the project depends on native packages such as `dlib`, `face_recognition`, and `sqlcipher3`.

The repository does not currently contain a complete web frontend. After installation, use the API through Swagger UI at `http://127.0.0.1:8000/docs`.

## Fedora

### Install system dependencies

```bash
sudo dnf install -y \
  python3.12 python3.12-devel \
  gcc gcc-c++ make cmake git openssl \
  openblas-devel lapack-devel \
  libX11-devel gtk3-devel boost-devel \
  sqlcipher sqlcipher-devel \
  libjpeg-turbo-devel libpng-devel libtiff-devel
```

Then, from the repository root:

```bash
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install email-validator
```

Package installation can take several minutes because `dlib` may compile locally.

## Ubuntu and Debian

Ubuntu 24.04 provides Python 3.12 as its default Python. On another release, install a supported Python 3.12 package for that release before continuing.

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git openssl pkg-config \
  libopenblas-dev liblapack-dev \
  libx11-dev libgtk-3-dev libboost-python-dev \
  libsqlcipher-dev sqlcipher \
  libjpeg-dev libpng-dev libtiff-dev
```

Confirm that `python3 --version` reports Python 3.12, then create the environment:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install email-validator
```

## Windows

WSL2 with Ubuntu is the recommended Windows setup. It provides the Linux development libraries expected by `sqlcipher3` and `dlib` and follows the same commands used in deployment.

### WSL2 with Ubuntu (recommended)

Open PowerShell as Administrator and run:

```powershell
wsl --install -d Ubuntu
```

Restart Windows if requested, open Ubuntu, and finish creation of the Linux user. Clone or copy the repository into the WSL filesystem—for example, under `~/projects`—for better build performance. Then follow the **Ubuntu and Debian** section above.

From Windows, the running API remains available at `http://127.0.0.1:8000/docs`.

### Native Windows (advanced)

Native installation is possible, but compilation of `dlib` and `sqlcipher3` depends on the available compiler and SQLCipher libraries.

Install:

1. 64-bit Python 3.12 from <https://www.python.org/downloads/> and enable **Add Python to PATH**.
2. Git from <https://git-scm.com/download/win>.
3. CMake from <https://cmake.org/download/> and add it to `PATH`.
4. Visual Studio Build Tools from <https://visualstudio.microsoft.com/visual-cpp-build-tools/> with **Desktop development with C++** and a Windows SDK.
5. A native SQLCipher development build discoverable by the compiler and linker.

In PowerShell, from the repository root:

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install email-validator
```

If `sqlcipher3` cannot compile or load its DLLs, use WSL2. Do not replace SQLCipher with ordinary SQLite for biometric production data.

## Configure the application

Perform these steps after completing the platform-specific installation.

### Create `.env`

Linux or WSL:

```bash
cp env.example.env .env
```

Windows PowerShell:

```powershell
Copy-Item env.example.env .env
```

Generate three independent 32-byte secrets.

Linux or WSL:

```bash
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
```

Native Windows PowerShell, if OpenSSL is unavailable:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_hex(32))"
```

Place a different generated value in each field:

```env
SECRET_KEY=<first-generated-value>
BOOTSTRAP_TOKEN=<second-generated-value>
DATABASE_ENCRYPTION_KEY=<third-generated-value>
```

Also update the database dialect and disable application-managed TLS for local development:

```env
DATABASE_URL=sqlite+pysqlcipher:///./secure.db
TLS_ENABLED=false
```

`DATABASE_ENCRYPTION_KEY` must contain exactly 64 hexadecimal characters. `SECRET_KEY` and `BOOTSTRAP_TOKEN` must contain at least 32 characters.

### Initialize SQLCipher

With the virtual environment active, run from the repository root:

```bash
python -m app.db.init_db
```

A successful result reports a SQLCipher version and creates `secure.db`.

### Start the API

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep that terminal open. Visit:

- <http://127.0.0.1:8000/> for application status
- <http://127.0.0.1:8000/health> for the database health check
- <http://127.0.0.1:8000/docs> for Swagger UI

The root URL returns JSON; the interactive documentation is at `/docs`.

### Create the first administrator

1. Open `http://127.0.0.1:8000/docs`.
2. Expand `POST /api/auth/register` and select **Try it out**.
3. Enter the `.env` value of `BOOTSTRAP_TOKEN` in `X-Bootstrap-Token`.
4. Enter the administrator details. The password must contain at least 12 characters.
5. Execute the request. Only the first user can be created through this endpoint.
6. Use `POST /api/auth/login`. Enter the administrator email in the OAuth `username` field.
7. Copy the access token and use Swagger UI's **Authorize** button for protected routes.

## Verify the installation

In a second terminal, activate the environment and run:

```bash
curl http://127.0.0.1:8000/health
python -m pytest tests -v
```

PowerShell can use:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
python -m pytest tests -v
```

The expected health response is:

```json
{"status":"ok","database":"ok"}
```

## Troubleshooting

### `.venv/bin/activate` does not exist

Environment creation did not finish, often because it was interrupted. Move the incomplete directory and recreate it:

```bash
mv .venv .venv-incomplete
python3.12 -m venv .venv
source .venv/bin/activate
```

### Python 3.14 was selected

Move the incomplete environment and explicitly invoke Python 3.12. After activation, confirm the result with `python --version`.

### `dlib` fails to build

Confirm that CMake, a C++ compiler, Python development headers, OpenBLAS, and LAPACK are installed. Then retry:

```bash
python -m pip install --no-cache-dir dlib
python -m pip install --no-cache-dir face_recognition
python -m pip install -r requirements.txt
```

### `NoSuchModuleError: sqlite.sqlcipher`

The obsolete dialect name is still present in `.env`. Change it to:

```env
DATABASE_URL=sqlite+pysqlcipher:///./secure.db
```

### SQLCipher is unavailable

Fedora:

```bash
sudo dnf install sqlcipher sqlcipher-devel
python -m pip install --force-reinstall --no-cache-dir sqlcipher3
```

Ubuntu/Debian:

```bash
sudo apt install libsqlcipher-dev sqlcipher
python -m pip install --force-reinstall --no-cache-dir sqlcipher3
```

On native Windows, verify the SQLCipher header, library, and DLL paths or switch to WSL2.

### `email-validator is not installed`

The authentication schemas use Pydantic's `EmailStr`:

```bash
python -m pip install email-validator
```

### Camera is unavailable on Linux

```bash
ls -l /dev/video*
python -c "import cv2; camera = cv2.VideoCapture(0); ok, _ = camera.read(); print('Camera available:', ok); camera.release()"
```

If access is denied, add the user to the `video` group and sign out and back in:

```bash
sudo usermod -aG video "$USER"
```

Change `CAMERA_INDEX` in `.env` if the desired camera uses another index.

### Missing TLS certificate files

For the documented local Uvicorn command, set `TLS_ENABLED=false`. For production, terminate HTTPS at a reverse proxy or provide valid certificate and key files in `.env`.

## Production notes

The `--reload` server is for development. Before exposing the service, use a production process manager, trusted HTTPS termination, restricted CORS origins, firewall rules, backups, log rotation, and a documented biometric-data retention policy.
