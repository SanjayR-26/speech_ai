"""
Application configuration using Pydantic settings
"""
from typing import Optional, List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "QA Platform API"
    app_version: str = "2.0.0"
    debug: bool = False
    
    # API
    api_prefix: str = "/api"
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    api_base_url: str = "http://localhost:8000"
    
    # Database
    database_url: str = "postgresql://qa_app:your_password@localhost:5432/qa_platform"
    database_echo: bool = False
    database_pool_size: int = 20
    database_max_overflow: int = 40
    
    # Keycloak
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "qa-default"
    keycloak_client_id: str = "qa-platform-backend"
    keycloak_client_secret: str = "390301b6-0499-4f72-9ed1-3479e0a6bade"
    keycloak_admin_username: str = "admin"
    keycloak_admin_password: str = "local_12345"
    
    # JWT
    jwt_algorithm: str = "RS256"
    jwt_issuer: str = "http://localhost:8080/realms/qa-default"
    jwt_audience: str = "account"
    
    # AssemblyAI
    assemblyai_api_key: str = "your_assemblyai_api_key"
    assemblyai_webhook_url: Optional[str] = None
    
    # OpenAI
    openai_api_key: str = "your_openai_api_key"
    openai_model: str = "gpt-5-mini-2025-08-07"
    openai_max_tokens: int = 4000
    
    # Storage
    storage_type: str = "local"  # 'local', 's3'
    storage_local_path: str = "./uploads"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_s3_bucket: Optional[str] = None
    aws_region: str = "us-east-1"
    
    # File Upload
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    allowed_audio_formats: List[str] = [
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/mp4",
        "audio/x-m4a",
        "audio/ogg",
        "audio/webm",
        "audio/flac"
    ]
    
    # Redis (optional)
    redis_url: Optional[str] = "redis://localhost:6379"
    cache_ttl: int = 3600  # 1 hour
    
    # Security
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:5000,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:5000"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to list"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds
    
    # Background Tasks
    task_queue_name: str = "qa-platform-tasks"
    
    # SSH Tunnel Configuration
    use_ssh_tunnel: bool = False
    ssh_host: Optional[str] = None
    ssh_port: int = 22
    ssh_username: Optional[str] = None
    ssh_key_path: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_local_port: int = 5432
    ssh_remote_host: str = "localhost"
    ssh_remote_port: int = 5432
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
