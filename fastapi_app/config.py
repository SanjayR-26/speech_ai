from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # API Keys
    assemblyai_api_key: str
    openai_api_key: str
    
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    
    # App settings
    app_name: str = "Wainsk QA Call Solution"
    debug: bool = True
    
    # File upload settings
    max_file_size: int = 5 * 1024 * 1024 * 1024  # 5GB
    allowed_audio_formats: list[str] = [
        "audio/wav", "audio/mpeg", "audio/mp3", "audio/mp4", 
        "audio/x-m4a", "audio/ogg", "audio/flac"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings():
    return Settings()




