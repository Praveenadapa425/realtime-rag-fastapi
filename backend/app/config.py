import logging
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    VECTOR_DB_PATH: str = "./chroma_data"
    MODEL_NAME: str = "llama3"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    LOG_LEVEL: str = "INFO"

settings = Settings()