import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    _BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    _DB_PATH = os.path.join(_BASE_DIR, "instance", "furniture_mover.db")
    os.makedirs(os.path.join(_BASE_DIR, "instance"), exist_ok=True)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", f"sqlite:///{_DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_CREATE_DB = os.environ.get("AUTO_CREATE_DB", "True") in ("True", "true", "1")
    ADMIN_REG_CODE = os.environ.get("ADMIN_REG_CODE")
