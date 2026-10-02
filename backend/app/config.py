from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def resolve_backend_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BACKEND_ROOT / path


class Settings(BaseSettings):
    app_name: str = "VeriRAG API"
    database_url: str = "sqlite:///./verirag.db"
    jwt_secret: str = "change-this-in-production"
    jwt_expire_minutes: int = 1440
    storage_provider: str = "local"
    storage_path: str = "./storage/documents"
    s3_bucket: str = ""
    s3_endpoint: str = ""
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_provider: str = "ollama"
    llm_model: str = "llama3.2"
    llm_base_url: str = "http://localhost:11434"
    llm_api_key: str = ""
    cors_origins: str = "http://localhost:5173"
    ocr_enabled: bool = True
    tesseract_cmd: str = ""
    semantic_weight: float = 0.65
    bm25_weight: float = 0.35
    retrieval_candidate_multiplier: int = 3
    temporal_default_authority: float = 50
    model_config = SettingsConfigDict(env_file=str(Path(__file__).resolve().parents[1] / ".env"), extra="ignore")

settings = Settings()
