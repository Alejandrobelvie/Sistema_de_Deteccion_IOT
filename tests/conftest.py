"""Valores seguros y aislados para importar la configuración en tests."""
import os

os.environ.setdefault("SECRET_KEY", "a" * 64)
os.environ.setdefault("BOOTSTRAP_TOKEN", "b" * 64)
os.environ.setdefault("DATABASE_ENCRYPTION_KEY", "c" * 64)
os.environ.setdefault("TLS_ENABLED", "false")
