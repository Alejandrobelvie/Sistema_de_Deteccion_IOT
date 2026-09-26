# Guía de Instalación Detallada

## Paso 1: Preparar el Sistema

### Ubuntu/Debian

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias del sistema
sudo apt install -y python3.10 python3.10-venv python3-pip \
    cmake build-essential git curl \
    libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev \
    libboost-python-dev libsqlcipher-dev sqlcipher \
    libjpeg-dev libpng-dev libtiff-dev

# Verificar versiones
python3 --version  # Debe ser 3.10+
cmake --version
```

### Fedora

```bash
sudo dnf install -y python3.10 python3.10-devel cmake gcc gcc-c++ \
    git curl openblas-devel lapack-devel libX11-devel gtk3-devel \
    boost-devel sqlcipher-devel sqlcipher \
    libjpeg-turbo-devel libpng-devel libtiff-devel
```

### Windows

1. **Instalar Python 3.10+** desde [python.org](https://www.python.org/downloads/)
2. **Instalar Visual Studio Build Tools**:
   - Descargar desde [Microsoft](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   - Seleccionar "Desktop Development with C++"
3. **Instalar CMake**:
   - Descargar desde [cmake.org](https://cmake.org/download/)
   - Agregar al PATH del sistema
4. **Instalar Git** desde [git-scm.com](https://git-scm.com/)

---

## Paso 2: Clonar el Proyecto

```bash
# Crear directorio de proyecto
mkdir -p ~/projects/facial-access-iot
cd ~/projects/facial-access-iot

# Clonar repositorio (o copiar archivos)
git clone <tu-repositorio> .
# O copiar archivos manualmente
```

---

## Paso 3: Configurar Entorno Virtual

```bash
# Crear entorno virtual
python3 -m venv venv

# Activar entorno
# Linux/Mac:
source venv/bin/activate

# Windows:
venv\Scripts\activate

# Verificar que está activo
which python  # Linux/Mac
# o
where python  # Windows
```

---

## Paso 4: Instalar Dependencias de Python

```bash
# Actualizar pip
pip install --upgrade pip

# Instalar todas las dependencias
pip install -r requirements.txt

# Esto puede tomar 10-20 minutos la primera vez
# Se descargarán: OpenCV, dlib, face_recognition, YOLOv8, etc.
```

### Si hay errores con dlib:

```bash
# Asegurar tener CMake y compiladores
sudo apt install cmake build-essential

# Reintentar instalación de dlib
pip install dlib --no-cache-dir

# Luego el resto
pip install face_recognition --no-cache-dir
```

---

## Paso 5: Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp env.example.env .env

# Generar claves seguras
# SECRET_KEY (32 bytes = 64 caracteres hex)
openssl rand -hex 32

# DATABASE_ENCRYPTION_KEY (32 bytes = 64 caracteres hex)
openssl rand -hex 32

# Editar .env y pegar las claves generadas
nano .env  # o usa tu editor favorito
```

### .env mínimo requerido:

```env
SECRET_KEY=tu_clave_de_64_caracteres_hex_aqui
DATABASE_ENCRYPTION_KEY=tu_clave_de_64_caracteres_hex_aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite+sqlcipher:///./secure.db
CAMERA_INDEX=0
```

---

## Paso 6: Inicializar Base de Datos

```bash
# Asegurar que el entorno está activo
source venv/bin/activate

# Ejecutar script de inicialización
python -m app.db.init_db
```

**Deberías ver:**
```
============================================================
INICIALIZANDO BASE DE DATOS
============================================================
 Base de datos encriptada: 4.5.0
 Tablas creadas exitosamente
Registra el primer administrador mediante POST /api/auth/register
```

---

## Paso 7: Probar el Backend

```bash
# Iniciar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Deberías ver:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Aplicación iniciada correctamente
```

### Verificar que funciona:

Abre tu navegador en: `http://localhost:8000`

Deberías ver la documentación Swagger de FastAPI.

Prueba el endpoint de salud:
```bash
curl http://localhost:8000/health
# Response: {"status":"ok"}
```

---

## Paso 8: Probar Reconocimiento Facial

```bash
# Script de prueba de cámara
python scripts/test_camera.py
```

**Deberías ver:**
- Ventana con feed de cámara
- Detección de rostros en tiempo real
- Mensajes en consola cuando detecta rostros

**Si no funciona:**
```bash
# Verificar que la cámara está disponible
ls /dev/video*  # Linux
# o
python -c "import cv2; print(cv2.getBuildInformation())"

# Probar con diferente índice de cámara
# Cambiar CAMERA_INDEX=1 en .env
```

---

## Paso 9: Instalar Frontend (Opcional)

```bash
# Navegar a directorio frontend
cd frontend

# Instalar Node.js 18+ si no lo tienes
# Ubuntu:
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev

# Deberías ver:
# ➜  Local:   http://localhost:3000/
```

---

## Paso 10: Crear el administrador y probar login

1. Abre `http://localhost:8000/docs` (Swagger UI)
2. Usa `/api/auth/register` con el header `X-Bootstrap-Token` configurado en `.env`.
3. El endpoint solo permite crear el primer usuario; los siguientes se crean desde `/api/users` por un administrador.
4. Inicia sesión en `/api/auth/login` con el email y contraseña recién creados.
5. Deberías recibir tokens JWT de acceso y renovación.

---

## Solución de Problemas Comunes

### Error: "No module named 'face_recognition'"

```bash
pip install face_recognition --no-cache-dir
```

### Error: "dlib failed to build"

```bash
# Asegurar dependencias de sistema
sudo apt install cmake build-essential libboost-python-dev

# Limpiar cache
pip cache purge

# Reintentar
pip install dlib --no-cache-dir
```

### Error: "SQLCipher no disponible"

```bash
# Instalar SQLCipher
sudo apt install libsqlcipher-dev sqlcipher

# Reinstalar sqlcipher3
pip uninstall sqlcipher3
pip install sqlcipher3 --no-cache-dir
```

### Error: "Cámara no detectada"

```bash
# Linux: verificar permisos
ls -l /dev/video*
sudo usermod -a -G video $USER
# Reiniciar sesión

# Probar con OpenCV directamente
python -c "import cv2; cap = cv2.VideoCapture(0); ret, frame = cap.read(); print('Cámara OK:', ret)"
```

### Error: "JWT decode failed"

Verificar que `SECRET_KEY` en `.env` tenga exactamente 64 caracteres hex.

---

## Verificación Final

Ejecuta este script de verificación:

```bash
python scripts/verify_installation.py
```

**Checklist:**
- Python 3.10+ instalado
- Entorno virtual activo
- Todas las dependencias instaladas
- Base de datos encriptada creada
- Usuario admin creado
- Cámara detectada
- Servidor inicia sin errores
- Login funciona con JWT

---

## Siguientes Pasos

1. **Cambiar contraseña de admin** inmediatamente
2. **Configurar HTTPS** para producción
3. **Enroll de usuarios** desde el dashboard
4. **Configurar zonas de acceso**
5. **Probar detección de animales**
6. **Configurar alertas** (email, webhook)

---

## Soporte

Si tienes problemas:
1. Revisa los logs en `logs/audit.log`
2. Verifica el archivo `.env`
3. Asegúrate de tener el entorno virtual activo
4. Consulta la documentación en `/docs` del servidor

**Recursos:**
- [Documentación FastAPI](https://fastapi.tiangolo.com/)
- [face_recognition docs](https://github.com/ageitgey/face_recognition)
- [YOLOv8 docs](https://docs.ultralytics.com/)
