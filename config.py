from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # NOTE: this was previously a module-level `class Config`, which pydantic
    # never saw — so .env was silently ignored and every value had to come from
    # exported shell env vars. Real environment variables still take precedence
    # over .env, so existing exports keep working unchanged.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GCP
    google_cloud_project: str = ""
    google_cloud_location_gemini: str = "asia-southeast1"

    # LLM models
    gemini_model: str = "gemini-2.5-flash"
    image_model_api: str = "gemini"
    image_model: str = "gemini-3.1-flash-image"
    image_model_location: str = "global"  # global endpoint works for all regions
    embedding_model: str = "text-multilingual-embedding-002"  # handles Hindi/English code-switching in CBSE content

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "pdf_chunks"
    qdrant_api_key: str = ""  # leave empty for unauthenticated (local dev)

    # Chunking
    chunk_size_chars: int = 2400   # ~600 tokens; multilingual embedding model supports 2048 tokens
    chunk_overlap_chars: int = 200  # seed next chunk with last N chars to avoid boundary gaps

    # Retrieval
    retrieve_top_k: int = 5  # final number of chunks returned from hybrid search

    # Chapter hierarchy extraction ("Create Chapter with PDF")
    openai_api_key: str = ""
    openai_hierarchy_model: str = "gpt-4o-mini"
    openai_icon_model: str = "gpt-image-2"
    gcs_bucket_name: str = "gyaanbuddy-media"

settings = Settings()
