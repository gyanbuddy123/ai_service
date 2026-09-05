from pydantic import BaseModel


class ExtractHierarchyRequest(BaseModel):
    job_id: str
    gcs_path: str          # gs://bucket-name/path/to/file.pdf-or-.zip
    subject_name: str


class FileHierarchyResult(BaseModel):
    filename: str
    module_chapter_pairs: list[dict]  # [{"MODULE": ..., "CHAPTER": ...}, ...]
    icon_url: str | None = None       # AI-generated module icon (GCS URL), or None on failure
    skipped: bool = False
    skip_reason: str | None = None


class ExtractHierarchyResponse(BaseModel):
    job_id: str
    files: list[FileHierarchyResult]
