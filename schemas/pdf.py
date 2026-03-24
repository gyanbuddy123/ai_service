from pydantic import BaseModel


class PageText(BaseModel):
    page_number: int
    text: str


class EmbedRequest(BaseModel):
    pdf_id: str
    chapter_id: str
    pages: list[PageText]


class EmbedResponse(BaseModel):
    pdf_id: str
    chunks_stored: int


class DeleteEmbedResponse(BaseModel):
    pdf_id: str
    deleted: bool
