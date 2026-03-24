from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GCP
    google_cloud_project: str = ""
    google_cloud_location_claude: str = "asia-southeast1"  # Claude in Vertex AI — Singapore (closest to India)
    google_cloud_location_gemini: str = "us-central1"      # Gemini 2.0 Flash available here

    # LLM models
    claude_model: str = "claude-sonnet-4-6"
    gemini_model: str = "gemini-2.0-flash"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "pdf_chunks"

    # Django callback (used by async flows if needed)
    django_callback_url: str = "http://localhost:8000/api/internal/ai-callback"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
