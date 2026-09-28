# Facial Access IoT API

Secure biometric access-control backend built with FastAPI. It provides JWT authentication, encrypted biometric templates, facial recognition, access logs, dashboard metrics, and animal-detection services.

The repository currently contains the Python API only. There is no complete web frontend in this version; use FastAPI's interactive API documentation at `http://127.0.0.1:8000/docs`.

## Current requirements

- Python 3.12 recommended
- C/C++ build tools and CMake for `dlib`
- OpenBLAS and LAPACK
- SQLCipher development libraries
- A webcam is optional and is only needed for camera-based workflows

Python 3.14 is not recommended because some computer-vision and SQLCipher dependencies may not provide compatible builds yet.

## Quick start

The commands below assume that the system packages listed in [the installation guide](app/INSTALL_GUIDE.md) are already installed.

```bash
git clone <repository-url>
cd Sistema_de_Deteccion_IOT

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install email-validator

cp env.example.env .env
```

Generate three different secrets and place them in `.env`:

```bash
openssl rand -hex 32  # SECRET_KEY
openssl rand -hex 32  # BOOTSTRAP_TOKEN
openssl rand -hex 32  # DATABASE_ENCRYPTION_KEY
```

Set the SQLAlchemy SQLCipher dialect and local-development TLS mode in `.env`:

```env
DATABASE_URL=sqlite+pysqlcipher:///./secure.db
TLS_ENABLED=false
```

Initialize the database and start the development server:

```bash
python -m app.db.init_db
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open these URLs:

- API status: <http://127.0.0.1:8000/>
- Health check: <http://127.0.0.1:8000/health>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

## First administrator

In Swagger UI, call `POST /api/auth/register`. Supply the value of `BOOTSTRAP_TOKEN` through the `X-Bootstrap-Token` header and use a password containing at least 12 characters. The bootstrap endpoint closes after the first user is created.

Sign in through `POST /api/auth/login`. Its `username` form field accepts the administrator's email address. Use the returned bearer token with the **Authorize** button in Swagger UI.

## Implemented API routes

| Method | Route | Purpose | Access |
| --- | --- | --- | --- |
| `POST` | `/api/auth/register` | Create the first administrator | Bootstrap token |
| `POST` | `/api/auth/login` | Create access and refresh tokens | Public, rate limited |
| `POST` | `/api/auth/refresh` | Refresh authentication | Refresh token |
| `GET` | `/api/auth/me` | Return the current user | Authenticated user |
| `GET`, `POST` | `/api/users` | List or create users | Administrator |
| `PATCH` | `/api/users/{user_id}/active` | Enable or disable a user | Administrator |
| `POST` | `/api/access/enroll` | Create a facial template from 3–5 images | Administrator |
| `POST` | `/api/access/recognize` | Check a face and record the result | Authenticated user |
| `GET` | `/api/dashboard/summary` | Return metrics for the last 24 hours | Authenticated user |
| `GET` | `/api/logs/access` | List access events | Administrator |
| `GET` | `/api/logs/audit` | List audit events | Administrator |

Uploaded enrollment and recognition images must be JPEG or PNG and no larger than 8 MB. Enrollment requires explicit consent. Raw enrollment images are not stored; the application stores an encrypted facial template.

## Project structure

```text
Sistema_de_Deteccion_IOT/
├── app/
│   ├── api/          # Authentication, users, access, metrics, and logs
│   ├── core/         # Configuration and security helpers
│   ├── db/           # SQLAlchemy models and SQLCipher setup
│   ├── services/     # Face recognition and animal detection
│   └── main.py       # FastAPI application
├── tests/
├── env.example.env
├── requirements.txt
└── README.md
```

## Tests

With the virtual environment active and `.env` configured:

```bash
python -m pytest tests -v
```

## Platform-specific installation

See [app/INSTALL_GUIDE.md](app/INSTALL_GUIDE.md) for Fedora, Ubuntu/Debian, and Windows instructions, plus common installation problems.

## Security notes

- Keep `.env`, database files, generated models, and logs out of version control.
- Use different random values for all three secrets.
- The development command serves HTTP. Configure a reverse proxy and trusted TLS certificates before exposing the API to a network.
- This application handles biometric data. Obtain informed consent and follow the privacy and retention laws that apply in your jurisdiction.

## Authors

- Esteban Ramirez
- Andy Rodriguez
- Alejandro Belvie
