"""
PDF processing pipeline: GCS download → multimodal extraction → chunk + embed + store.

Extraction is multimodal per page:
  1. Plain text via PyMuPDF page.get_text()
  2. Tables via page.find_tables() → Markdown
  3. Embedded images via Gemini Flash vision → text description

The combined per-page text is fed into embed_and_store() unchanged.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("ai_service.pdf_processor")

_MIN_IMAGE_BYTES = 5_000   # images smaller than this are decorative — skip
_MIN_DESCRIPTION_WORDS = 10  # Gemini descriptions shorter than this are discarded

_VISION_PROMPT = (
    "You are analyzing a page from an educational textbook (CBSE, grade school).\n"
    "Describe the following figure or diagram for use in a question-answering system.\n"
    "Be specific: include all labels, measurements, values, arrows, and relationships shown.\n"
    "If geometric: state all labeled sides/angles and their values.\n"
    "If a graph: describe axes, units, and key data points.\n"
    "If a process or flow diagram: list all steps in order.\n"
    "Keep under 200 words. Output only the description — no preamble, no commentary."
)


def download_from_gcs(gcs_path: str) -> bytes:
    """
    Download PDF bytes from Google Cloud Storage.
    gcs_path must be in the form gs://bucket-name/path/to/file.pdf
    Uses Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS env var).
    """
    from google.cloud import storage

    if not gcs_path:
        raise ValueError("gcs_path is required")

    without_prefix = gcs_path.removeprefix("gs://")
    bucket_name, _, object_path = without_prefix.partition("/")

    if not bucket_name or not object_path:
        raise ValueError(f"Invalid GCS path: {gcs_path!r}. Expected gs://bucket/path format.")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)

    logger.info(f"Downloading gs://{bucket_name}/{object_path}")
    return blob.download_as_bytes()


def _table_to_markdown(table) -> str:
    """Convert a PyMuPDF Table object to a Markdown table string."""
    try:
        rows = table.extract()
        if not rows:
            return ""
        lines = []
        header = rows[0]
        lines.append("| " + " | ".join(str(c or "") for c in header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")
        for row in rows[1:]:
            lines.append("| " + " | ".join(str(c or "") for c in row) + " |")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning(f"Table extraction failed: {exc}")
        return ""


async def _describe_image(image_bytes: bytes, mime_type: str) -> str:
    """
    Call Gemini Flash vision to describe an educational figure.
    Returns empty string on failure or if description is too short (decorative image).
    """
    from config import settings
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part, Image

    vertexai.init(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location_gemini,
    )

    # Normalise mime type — PyMuPDF returns e.g. "jpeg", "png"
    if not mime_type.startswith("image/"):
        mime_type = f"image/{mime_type.lower()}"
    # Gemini only supports jpeg/png/gif/webp
    if mime_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime_type = "image/png"

    def _call():
        model = GenerativeModel(settings.gemini_model)
        image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
        response = model.generate_content([image_part, _VISION_PROMPT])
        return response.text.strip()

    try:
        description = await asyncio.get_event_loop().run_in_executor(None, _call)
        if len(description.split()) < _MIN_DESCRIPTION_WORDS:
            return ""  # too short — likely decorative
        return description
    except Exception as exc:
        logger.warning(f"Gemini vision failed for image: {exc}")
        return ""


def _overlaps_vertically(bbox_a, bbox_b) -> bool:
    """True if two bboxes share any vertical span."""
    return bbox_a[1] < bbox_b[3] and bbox_a[3] > bbox_b[1]


def _overlaps_horizontally(bbox_a, bbox_b) -> bool:
    """True if two bboxes share any horizontal span."""
    return bbox_a[0] < bbox_b[2] and bbox_a[2] > bbox_b[0]


def _effective_y0(block_bbox, floating_bboxes: list) -> float:
    """
    Return the effective sort key for a text block.

    If the block is beside a floating element — an image or a table — (same
    vertical band, different horizontal band) it is wrapped text. Push it to
    just after the element's bottom edge so the figure description or table
    Markdown always precedes the text that wraps around it.
    """
    by0 = block_bbox[1]
    for elem_bbox in floating_bboxes:
        if (
            _overlaps_vertically(block_bbox, elem_bbox)
            and not _overlaps_horizontally(block_bbox, elem_bbox)
        ):
            # Block is beside the floating element — sort it after element ends
            return elem_bbox[3] + 0.1   # elem_y1 + tiny epsilon
    return by0


async def extract_pages(doc) -> tuple[int, list[dict]]:
    """
    Position-aware multimodal extraction from an open PyMuPDF document.

    All content items (text blocks, tables, figures) are tagged with an
    effective y0 sort key, then sorted top-to-bottom before joining.

    Special cases handled:
    - Table cells: text inside table bboxes is skipped (captured in Markdown).
    - Wrapped text: text blocks beside an image (same y-band, different x-band)
      are pushed to sort after the image so the figure description always
      precedes the text that wraps around it.

    Returns (total_pages, [{page_number, text}, ...]) — only pages with content.
    """
    total_pages = doc.page_count
    pages: list[dict] = []

    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        # items = list of (effective_y0, content_string) — sorted at the end
        items: list[tuple[float, str]] = []

        # ── Step 1: Tables — collected first so we know which areas to skip ──
        table_bboxes: list[tuple] = []
        try:
            found_tables = page.find_tables()
            for table in found_tables.tables:
                md = _table_to_markdown(table)
                if md:
                    items.append((table.bbox[1], f"[TABLE]\n{md}"))
                    table_bboxes.append(table.bbox)
        except Exception as exc:
            logger.warning(f"Table detection failed on page {page_num + 1}: {exc}")

        def _inside_table(bbox) -> bool:
            bx0, by0, bx1, by1 = bbox
            for tx0, ty0, tx1, ty1 in table_bboxes:
                ox = max(0.0, min(bx1, tx1) - max(bx0, tx0))
                oy = max(0.0, min(by1, ty1) - max(by0, ty0))
                if ox > 0 and oy > 0:
                    return True
            return False

        # ── Step 2: Images — resolve positions first (needed for wrap detection) ─
        image_list = page.get_images(full=True)
        image_bboxes: list[tuple] = []   # (x0, y0, x1, y1) for each image on page
        image_pos: list[tuple[float, int, int]] = []  # (y0, xref, display_idx)

        for i, img in enumerate(image_list):
            xref = img[0]
            try:
                rects = page.get_image_rects(xref)
                if rects:
                    r = rects[0]
                    bbox = (r.x0, r.y0, r.x1, r.y1)
                    y0 = r.y0
                else:
                    bbox = (0, 0, 0, 0)
                    y0 = float("inf")
            except Exception:
                bbox = (0, 0, 0, 0)
                y0 = float("inf")
            image_bboxes.append(bbox)
            image_pos.append((y0, xref, i + 1))

        # ── Step 3: Text blocks — skip table cells, adjust y0 for wrapped text ─
        blocks = page.get_text("dict", flags=0)["blocks"]
        for block in blocks:
            if block["type"] != 0:
                continue
            if _inside_table(block["bbox"]):
                continue
            text = "\n".join(
                "".join(span["text"] for span in line.get("spans", []))
                for line in block.get("lines", [])
            ).strip()
            if text:
                eff_y0 = _effective_y0(block["bbox"], image_bboxes + table_bboxes)
                items.append((eff_y0, text))

        # ── Step 4: Describe images concurrently, insert at their y0 ────────
        if image_pos:
            async def _process_image(xref: int, idx: int) -> str:
                try:
                    img_info = doc.extract_image(xref)
                    img_bytes = img_info.get("image", b"")
                    if len(img_bytes) < _MIN_IMAGE_BYTES:
                        return ""
                    mime = img_info.get("ext", "png")
                    description = await _describe_image(img_bytes, mime)
                    if description:
                        return f"[FIGURE {idx}]\n{description}"
                except Exception as exc:
                    logger.warning(f"Image {idx} on page {page_num + 1} failed: {exc}")
                return ""

            descriptions = await asyncio.gather(*[
                _process_image(xref, idx) for _, xref, idx in image_pos
            ])
            for (y0, _, _), desc in zip(image_pos, descriptions):
                if desc:
                    items.append((y0, desc))

        # ── Sort by effective y0 (top → bottom) and join ─────────────────────
        items.sort(key=lambda x: x[0])
        combined = "\n\n".join(content for _, content in items).strip()
        if combined:
            pages.append({"page_number": page_num + 1, "text": combined})

    logger.info(f"Extracted content from {len(pages)}/{total_pages} pages")
    return total_pages, pages


async def process_pdf(pdf_id: str, chapter_id: str, gcs_path: str) -> dict:
    """
    Full pipeline: download from GCS → multimodal extraction → chunk + embed + store in Qdrant.
    Returns {"total_pages": int, "chunks_stored": int}.
    """
    import fitz  # PyMuPDF
    from services.vector_store import embed_and_store

    pdf_bytes = download_from_gcs(gcs_path)

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except fitz.FileDataError as exc:
        raise ValueError(f"Could not open PDF (file may be corrupted): {exc}") from exc

    if doc.needs_pass:
        doc.close()
        raise ValueError("PDF is password-protected — cannot extract content.")

    try:
        total_pages, pages = await extract_pages(doc)
    finally:
        doc.close()

    if not pages:
        logger.warning(f"No content extracted from PDF {pdf_id} — image-only with no Gemini descriptions?")
        return {"total_pages": total_pages, "chunks_stored": 0}

    chunks_stored = await embed_and_store(
        pdf_id=pdf_id,
        chapter_id=chapter_id,
        pages=pages,
    )
    logger.info(f"process_pdf: {pdf_id} → {total_pages} pages, {chunks_stored} chunks stored")
    return {"total_pages": total_pages, "chunks_stored": chunks_stored}
