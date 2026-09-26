# 1. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar .env
cp env.example.env .env
# Editar .env y agregar claves generadas con:
openssl rand -hex 32  # Para SECRET_KEY
openssl rand -hex 32  # Para BOOTSTRAP_TOKEN
openssl rand -hex 32  # Para DATABASE_ENCRYPTION_KEY

# 4. Inicializar DB
python -m app.db.init_db

# 5. Iniciar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
