# Instalación desde la terminal en Raspberry Pi con Ubuntu

Esta guía explica cómo instalar y arrancar la aplicación desde una terminal de Ubuntu en una Raspberry Pi después de clonar el repositorio.

## 1. Entrar al repositorio

Si el repositorio fue clonado en la carpeta personal:

```bash
cd ~/Sistema_de_Deteccion_IOT
```

Si está en otra ubicación, sustituye la ruta anterior por la ruta correspondiente.

## 2. Instalar las dependencias del sistema

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

Comprueba la versión de Python:

```bash
python3 --version
```

Python 3.12 es la versión recomendada. Python 3.14 no es recomendable porque algunas dependencias de visión computacional y SQLCipher podrían no ser compatibles.

## 3. Crear y activar el entorno virtual

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Cuando el entorno esté activo, normalmente aparecerá `(.venv)` al comienzo de la línea de la terminal.

## 4. Instalar las dependencias de Python

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

En una Raspberry Pi esta instalación puede tardar varios minutos, especialmente si `dlib` debe compilarse localmente.

## 5. Configurar las variables de entorno

Si todavía no existe el archivo `.env`, créalo a partir del ejemplo:

```bash
cp env.example.env .env
```

Genera tres secretos distintos:

```bash
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
```

Edita la configuración:

```bash
nano .env
```

Asigna un valor diferente a cada secreto y comprueba que las siguientes variables estén configuradas:

```env
SECRET_KEY=primer_valor_generado
BOOTSTRAP_TOKEN=segundo_valor_generado
DATABASE_ENCRYPTION_KEY=tercer_valor_generado

DATABASE_URL=sqlite+pysqlcipher:///./secure.db
TLS_ENABLED=false
```

Cada valor generado por `openssl rand -hex 32` contiene 64 caracteres hexadecimales. Para guardar el archivo en Nano, presiona `Ctrl+O`, Enter y luego `Ctrl+X`.

## 6. Inicializar la base de datos

Con el entorno virtual activo y desde la raíz del repositorio:

```bash
python -m app.db.init_db
```

Una inicialización correcta muestra la versión de SQLCipher y crea el archivo `secure.db`.

## 7. Arrancar la aplicación

Para permitir el acceso desde otros dispositivos conectados a la misma red:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

La terminal debe permanecer abierta mientras la aplicación está funcionando. Para detenerla, presiona `Ctrl+C`.

## 8. Abrir la aplicación desde la red local

Consulta la dirección IP de la Raspberry Pi:

```bash
hostname -I
```

Si la dirección obtenida es, por ejemplo, `192.168.1.50`, abre las siguientes direcciones desde un navegador conectado a la misma red:

- Aplicación web: `http://192.168.1.50:8000/`
- Estado de la API: `http://192.168.1.50:8000/api/status`
- Comprobación de salud: `http://192.168.1.50:8000/health`
- Swagger UI: `http://192.168.1.50:8000/docs`

También puedes comprobar el servicio desde la propia Raspberry Pi:

```bash
curl http://127.0.0.1:8000/health
```

La respuesta esperada es:

```json
{"status":"ok","database":"ok"}
```

## Arranques posteriores

Después de completar la instalación, solamente necesitas entrar al repositorio, activar el entorno y ejecutar el servidor:

```bash
cd ~/Sistema_de_Deteccion_IOT
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Consideraciones para Raspberry Pi

- Se recomienda utilizar Ubuntu de 64 bits.
- La aplicación incluye `torch`, `ultralytics`, `dlib` y reconocimiento facial, por lo que requiere bastante memoria y capacidad de procesamiento.
- La instalación inicial puede ser lenta debido a la compilación de dependencias nativas.
- Una cámara USB es opcional para arrancar la aplicación, pero es necesaria para las funciones que capturan imágenes localmente.
- No expongas directamente el puerto `8000` a Internet. La configuración anterior está pensada para desarrollo dentro de una red local.

## Solución de problemas básicos

Si el entorno virtual no se creó correctamente:

```bash
mv .venv .venv-incomplete
python3 -m venv .venv
source .venv/bin/activate
```

Si falla la instalación de `dlib`:

```bash
python -m pip install --no-cache-dir dlib
python -m pip install --no-cache-dir face_recognition
python -m pip install -r requirements.txt
```

Si aparece `NoSuchModuleError: sqlite.sqlcipher`, revisa que `.env` contenga exactamente:

```env
DATABASE_URL=sqlite+pysqlcipher:///./secure.db
```

Si la cámara existe pero el usuario no tiene acceso:

```bash
ls -l /dev/video*
sudo usermod -aG video "$USER"
```

Después del último comando, cierra la sesión de Ubuntu y vuelve a iniciarla para aplicar el cambio de grupo.
