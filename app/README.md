# Sistema de Control de Acceso Biométrico con Reconocimiento Facial

Sistema IoT seguro para control de acceso mediante reconocimiento facial, detección de animales y monitoreo en tiempo real. Diseñado con enfoque en ciberseguridad y privacidad de datos biométricos.

## Características Principales

- **Reconocimiento facial** con rechazo seguro mientras no exista prueba de vida temporal
- **Detección de animales** usando YOLOv8
- **Base de datos encriptada** con SQLCipher (AES-256)
- **Autenticación JWT** con bcrypt para contraseñas
- **Logs inmutables** con hash de integridad
- **Dashboard web** con métricas en tiempo real
- **Seguridad IoT**: TLS, encriptación en reposo y tránsito, rate limiting

## Arquitectura

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Cámara IP     │────▶│  Backend Python  │────▶│  SQLite +       │
│   (OpenCV)      │     │  (FastAPI)       │     │  SQLCipher      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌──────────────────┐
                        │  Dashboard React │
                        │  (Frontend)      │
                        └──────────────────┘
```

## Requisitos Previos

### Sistema Operativo
- **Recomendado**: Ubuntu 22.04+, Fedora 38+, o Windows 10/11
- **RAM mínima**: 8 GB (16 GB recomendado para ML)
- **GPU**: Opcional (acelera inferencia de YOLO)

### Dependencias del Sistema

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3.10 python3.10-venv cmake build-essential \
    libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev \
    libboost-python-dev libsqlcipher-dev sqlcipher
```

**Fedora:**
```bash
sudo dnf install -y python3.10 python3.10-devel cmake gcc gcc-c++ \
    openblas-devel lapack-devel libX11-devel gtk3-devel \
    boost-devel sqlcipher-devel sqlcipher
```

**Windows:**
1. Instalar [Microsoft Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Seleccionar "Desktop Development with C++"
3. Instalar [CMake](https://cmake.org/download/) y agregar al PATH

## Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/facial-access-iot.git
cd facial-access-iot
```

### 2. Crear entorno virtual
```bash
python3 -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Instalar dependencias de Python
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
cp env.example.env .env
```

Editar `.env` y configurar:
```env
# Seguridad
SECRET_KEY=tu_clave_secreta_de_32_caracteres_minimo
BOOTSTRAP_TOKEN=token_aleatorio_para_el_primer_administrador
DATABASE_ENCRYPTION_KEY=tu_clave_de_encriptacion_64_hex
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Base de datos
DATABASE_URL=sqlite+sqlcipher:///./secure.db

# Cámara
CAMERA_INDEX=0
CAMERA_RESOLUTION=1280x720

# Seguridad IoT
TLS_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
```

### 5. Inicializar base de datos encriptada
```bash
python -m app.db.init_db
```

### 6. Ejecutar migraciones
```bash
alembic upgrade head
```

### 7. Iniciar la aplicación
```bash
# Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (en otra terminal)
cd frontend
npm install
npm run dev
```

## Estructura del Proyecto

```
facial-access-iot/
├── app/
│   ├── api/              # Endpoints REST
│   │   ├── auth.py       # Login, registro, JWT
│   │   ├── users.py      # Gestión de usuarios
│   │   ├── access.py     # Control de acceso
│   │   └── dashboard.py  # Métricas y reportes
│   ├── core/
│   │   ├── security.py   # JWT, bcrypt, encriptación
│   │   ├── config.py     # Variables de entorno
│   │   └── liveness.py   # Detección de liveness
│   ├── db/
│   │   ├── database.py   # Conexión SQLCipher
│   │   ├── models.py     # Modelos SQLAlchemy
│   │   └── init_db.py    # Inicialización DB
│   ├── services/
│   │   ├── face_recognition.py  # Reconocimiento facial
│   │   ├── animal_detection.py  # YOLOv8 animales
│   │   └── access_control.py    # Lógica de acceso
│   ├── schemas/          # Pydantic schemas
│   └── main.py           # Punto de entrada
├── frontend/
│   ├── src/
│   │   ├── components/   # Componentes React
│   │   ├── pages/        # Login, Dashboard
│   │   └── services/     # API calls
│   └── package.json
├── tests/
│   ├── test_auth.py
│   ├── test_face_rec.py
│   └── test_security.py
├── env.example.env
├── requirements.txt
├── alembic.ini
└── README.md
```

## Medidas de Seguridad Implementadas

### 1. Autenticación y Autorización
- JWT con expiración (30 min access, 7 días refresh)
- Contraseñas hasheadas con bcrypt (12 rounds)
- Rate limiting en endpoints de login
- Validación de input con Pydantic

### 2. Base de Datos
- SQLCipher con AES-256
- Encriptación en reposo
- Claves en variables de entorno (no en código)
- Logs inmutables con hash SHA-256

### 3. Biometría
- No se almacenan imágenes faciales crudas
- Solo plantillas biométricas encriptadas
- Detección de liveness (parpadeo, movimiento 3D)
- Anti-spoofing (fotos, videos, máscaras)

### 4. IoT Security
- TLS 1.3 para comunicaciones
- Certificate pinning (opcional)
- VLAN separada para dispositivos IoT
- Firmware signing para edge devices

### 5. Auditoría
- Logs inmutables con cadena de hashes
- Cada acceso registrado con timestamp
- Alertas por intentos fallidos
- Exportación forense de logs

## Endpoints Principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login de usuario |
| POST | `/api/auth/register` | Registro de administrador |
| POST | `/api/users/enroll` | Enrollment facial de usuario |
| POST | `/api/access/verify` | Verificación de acceso |
| GET | `/api/dashboard/metrics` | Métricas en tiempo real |
| GET | `/api/logs` | Logs de auditoría (solo lectura) |
| DELETE | `/api/users/{id}` | Eliminación de datos biométricos |

## Pruebas

```bash
# Ejecutar tests unitarios
pytest tests/ -v

# Tests de seguridad
pytest tests/test_security.py -v

# Tests de integración
pytest tests/test_integration.py -v
```

## Uso del Dashboard

1. Acceder a `http://localhost:3000`
2. Login con credenciales de administrador
3. Visualizar:
   - Accesos exitosos/fallidos
   - Detección de animales
   - Estado de sensores
   - Logs de auditoría

## Solución de Problemas

### Error: "dlib no se puede compilar"
```bash
# Asegurar tener CMake y build tools
sudo apt install cmake build-essential
pip install dlib --no-cache-dir
```

### Error: "SQLCipher no disponible"
```bash
# Instalar SQLCipher
sudo apt install libsqlcipher-dev sqlcipher
pip install sqlcipher3 --no-cache-dir
```

### Error: "Cámara no detectada"
```bash
# Verificar índice de cámara
ls /dev/video*
# Cambiar CAMERA_INDEX en .env si es necesario
```

## Recursos Adicionales

- [Documentación FastAPI](https://fastapi.tiangolo.com/)
- [face_recognition library](https://github.com/ageitgey/face_recognition)
- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [SQLCipher Security Guide](https://www.zetetic.net/sqlcipher/)

## Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Fork el repositorio
2. Crear branch de feature (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request



## Autores

- **Esteban Ramirez**
- **Andy Rodriguez**
- **Alejandro Belvie**


## Agradecimientos

- Biblioteca `face_recognition` de ageitgey
- Ultralytics YOLOv8
- FastAPI community

---

** Advertencia de Seguridad**: Este sistema maneja datos biométricos sensibles. Asegúrate de cumplir con regulaciones locales de privacidad (GDPR, LGPD, etc.) y obtener consentimiento explícito de los usuarios antes de almacenar sus datos faciales.
