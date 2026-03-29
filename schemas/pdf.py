from pydantic import BaseModel


class EmbedRequest(BaseModel):
    pdf_id: str
    chapter_id: str
    gcs_path: str  # gs://bucket-name/path/to/file.pdf


class EmbedResponse(BaseModel):
    pdf_id: str
    total_pages: int
    chunks_stored: int


class DeleteEmbedResponse(BaseModel):
    pdf_id: str
    deactivated: bool


class ReactivateEmbedResponse(BaseModel):
    pdf_id: str
    reactivated: bool


class HardDeleteEmbedResponse(BaseModel):
    pdf_id: str
    deleted: bool
