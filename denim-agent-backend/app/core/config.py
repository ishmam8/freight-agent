import os
from dotenv import load_dotenv
load_dotenv()

from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "cargoitai"
    
    # Optional DB configs, typically picked up from env or defaults
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL", "sqlite:///denim_leads.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # JWT Configs
    # In production, this should be generated via `openssl rand -hex 32` and kept secret.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "b649a2a7fe1b1eac1ecfa73de298816c4c9a3b8cd21acb0c4765d1d6a2f07ab9")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
