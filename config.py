from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GCP
    google_cloud_project: str = ""
    google_cloud_location_claude: str = "asia-southeast1"  # Claude in Vertex AI — Singapore (closest to India)
    google_cloud_location_gemini: str = "us-central1"      # Gemini 2.0 Flash available here

    # LLM models
    claude_model: str = "claude-sonnet-4-6"
    gemini_model: str = "gemini-2.0-flash"
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
    retrieve_top_k: int = 8  # final number of chunks returned from hybrid search

class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
