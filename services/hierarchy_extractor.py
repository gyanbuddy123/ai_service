"""
Chapter hierarchy extraction for "Create Chapter with PDF".

Pipeline: GCS download (PDF or ZIP of PDFs) -> per-PDF text extraction ->
OpenAI hierarchy inference (Module/Chapter pairs) -> structured JSON result.

Ports the extraction logic from the reference tool (Yash-TextBook-Auto-Indexer,
Textbook mode only) into a plain, callable service — no Streamlit, no Excel
writing. Django consumes the returned rows directly and reuses Import Excel's
persistence logic.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
import zipfile

logger = logging.getLogger("ai_service.hierarchy_extractor")

_MIN_TEXT_CHARS = 50  # shorter than this is likely a scanned/image-only page — skip


def _natural_sort_key(s: str):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def _build_disk_queue_from_bytes(raw_bytes: bytes, original_filename: str, temp_dir: str) -> list[str]:
    """
    Writes the uploaded PDF or ZIP-of-PDFs to disk and returns a naturally-sorted
    list of PDF file paths ready for text extraction. Mirrors the reference
    tool's build_disk_queue, adapted for in-memory bytes instead of Streamlit's
    UploadedFile objects.
    """
    queue: list[str] = []
    lower_name = original_filename.lower()

    if lower_name.endswith(".zip"):
        zip_path = os.path.join(temp_dir, "_upload.zip")
        with open(zip_path, "wb") as f:
            f.write(raw_bytes)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                valid_pdf_names = [
                    name for name in zf.namelist()
                    if name.lower().endswith(".pdf")
                    and not name.startswith("__MACOSX/")
                    and not name.split("/")[-1].startswith("._")
                ]
                valid_pdf_names.sort(key=_natural_sort_key)
                for name in valid_pdf_names:
                    extracted_path = zf.extract(name, temp_dir)
                    queue.append(extracted_path)
        except Exception as exc:
            logger.error(f"Error extracting ZIP file {original_filename}: {exc}")
        finally:
            try:
                os.remove(zip_path)
            except OSError:
                pass
    elif lower_name.endswith(".pdf"):
        pdf_path = os.path.join(temp_dir, original_filename)
        with open(pdf_path, "wb") as f:
            f.write(raw_bytes)
        queue.append(pdf_path)

    queue.sort(key=lambda p: _natural_sort_key(os.path.basename(p)))
    return queue


def _extract_text_from_pdf(pdf_path: str) -> str:
    """Reads a single PDF directly from disk, page-marked plain text."""
    import fitz  # PyMuPDF

    full_text = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text")
            if text:
                full_text.append(f"--- PAGE {i + 1} ---\n" + text)
    return "\n\n".join(full_text)


def _build_hierarchy_prompt(raw_text: str, filename: str) -> str:
    return f"""
    You are an expert curriculum and textbook indexing system. I am providing you with the text of a document.
    Source File Name: {filename}
    Your task is to extract the structural hierarchy into a clean JSON array formatted for an educational database.
    CRITICAL INSTRUCTIONS:
    1. DYNAMIC HIERARCHY:
       - If the text is an ENTIRE BOOK, set the broad section (like "Part I") as the "MODULE", and chapters as "CHAPTER".
       - If the text is a SINGLE CHAPTER, set the main Chapter Title as the "MODULE", and subtopics as "CHAPTER".
    2. NEVER leave "CHAPTER" blank.
    3. STRICTLY IGNORE introductory outlines (like "CHAPTER FOCUS", "Learning Objectives"), page headers, and activity boxes.

    Output STRICTLY a valid JSON array of objects. Format exactly like this:
    [
      {{
        "MODULE": "PART I - What should I eat?",
        "CHAPTER": "Chapter 1 - Eat food."
      }}
    ]
    Textbook Content:
    {raw_text}
    """


async def _process_text_with_openai(raw_text: str, filename: str, max_retries: int = 3) -> list[dict]:
    """Calls OpenAI to infer the Module/Chapter hierarchy for one PDF's text."""
    from config import settings
    from openai import OpenAI

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured on the ai-service.")

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = _build_hierarchy_prompt(raw_text, filename)

    def _call():
        response = client.chat.completions.create(
            model=settings.openai_hierarchy_model,
            messages=[
                {"role": "system", "content": "You are a precise data extraction assistant. Output clean JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=8192,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "", 1)
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content.strip())

    loop = asyncio.get_event_loop()
    for attempt in range(1, max_retries + 1):
        try:
            return await loop.run_in_executor(None, _call)
        except Exception as exc:
            logger.warning(f"OpenAI hierarchy extraction attempt {attempt}/{max_retries} failed for {filename}: {exc}")
            if attempt == max_retries:
                return []
            await asyncio.sleep(3 * attempt)
    return []


async def extract_hierarchy(job_id: str, gcs_path: str, subject_name: str) -> dict:
    """
    Downloads the job's uploaded PDF/ZIP from GCS, extracts text per PDF, and
    infers a Module/Chapter hierarchy for each via OpenAI. Also generates one
    icon per file (using that file's first inferred MODULE name) and uploads
    it to GCS, so the Import Excel "Icon" column concept (Module.logo_url) can
    be populated automatically instead of left blank.

    Each file result also carries pdf_gcs_path + pdf_sha256 so Django can
    register the same PDF as a RAG source (PdfReference) without the teacher
    having to upload it a second time via the per-chapter upload button.

    Returns {"job_id": ..., "files": [{"filename", "module_chapter_pairs", "icon_url",
             "pdf_gcs_path", "pdf_sha256", "skipped", "skip_reason"}, ...]}
    """
    import time

    from config import settings
    from services.pdf_processor import download_from_gcs

    started = time.monotonic()
    raw_bytes = download_from_gcs(gcs_path)
    original_filename = gcs_path.rsplit("/", 1)[-1]
    is_zip = original_filename.lower().endswith(".zip")

    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_paths = _build_disk_queue_from_bytes(raw_bytes, original_filename, temp_dir)
        if not pdf_paths:
            raise ValueError("No PDF files found in the uploaded file.")

        # Files are processed concurrently — nearly all of the per-file cost is
        # waiting on OpenAI, so a ZIP of N chapters takes about as long as its
        # slowest file rather than the sum of all of them. The semaphore keeps
        # that from turning into an OpenAI rate-limit burst or N simultaneous
        # rembg inferences on a small VM.
        semaphore = asyncio.Semaphore(settings.hierarchy_max_concurrent_files)
        results = await asyncio.gather(*[
            _process_one_pdf(
                pdf_path, semaphore, job_id, gcs_path, is_zip,
                subject_name, settings.gcs_bucket_name,
            )
            for pdf_path in pdf_paths
        ])

    elapsed = time.monotonic() - started
    logger.info(
        f"extract_hierarchy: job {job_id} ({subject_name}) — "
        f"{len(results)} file(s) in {elapsed:.1f}s "
        f"(concurrency={settings.hierarchy_max_concurrent_files})"
    )
    return {"job_id": job_id, "files": results}


async def _process_one_pdf(pdf_path, semaphore, job_id, source_gcs_path, is_zip, subject_name, bucket_name):
    """
    Full per-file pipeline: text -> hierarchy -> icon -> persist for RAG reuse.
    Blocking work (PyMuPDF parsing, GCS upload) is pushed to the executor so it
    doesn't stall the event loop and serialise the other files.
    """
    loop = asyncio.get_event_loop()
    fname = os.path.basename(pdf_path)

    async with semaphore:
        text = await loop.run_in_executor(None, _extract_text_from_pdf, pdf_path)

        if len(text.strip()) < _MIN_TEXT_CHARS:
            return {
                "filename": fname, "module_chapter_pairs": [], "icon_url": None,
                "pdf_gcs_path": None, "pdf_sha256": None,
                "skipped": True, "skip_reason": "No extractable text (likely scanned/image-only).",
            }

        pairs = await _process_text_with_openai(text, fname)

        icon_url = None
        pdf_gcs_path = None
        pdf_sha256 = None
        if pairs:
            module_name = (pairs[0].get("MODULE") or "").strip()
            if module_name:
                icon_url = await _generate_module_icon(subject_name, module_name, fname)
            pdf_gcs_path, pdf_sha256 = await loop.run_in_executor(
                None, _persist_pdf_for_reuse,
                pdf_path, fname, job_id, source_gcs_path, is_zip, bucket_name,
            )

        return {
            "filename": fname,
            "module_chapter_pairs": pairs,
            "icon_url": icon_url,
            "pdf_gcs_path": pdf_gcs_path,
            "pdf_sha256": pdf_sha256,
            "skipped": len(pairs) == 0,
            "skip_reason": None if pairs else "AI extraction returned no results after retries.",
        }


def _persist_pdf_for_reuse(pdf_path, fname, job_id, source_gcs_path, is_zip, bucket_name):
    """
    Make one PDF individually addressable in GCS so it can be reused as a RAG
    source, and hash it for PdfReference's dedup check.

    A single-PDF upload already sits at its own GCS path, so only ZIP entries
    need uploading. Returns (gs:// path, sha256) or (None, None) on failure —
    never raises, since a reuse failure must not abort hierarchy extraction.
    """
    from services.pdf_processor import upload_bytes_to_gcs

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()

        if not is_zip:
            return source_gcs_path, sha256

        destination = f"hierarchy_imports/{job_id}/pdfs/{fname}"
        upload_bytes_to_gcs(pdf_bytes, bucket_name, destination, content_type="application/pdf")
        return f"gs://{bucket_name}/{destination}", sha256
    except Exception as exc:
        logger.warning(f"Could not persist '{fname}' for RAG reuse: {exc}")
        return None, None


# ── Icon generation ──────────────────────────────────────────────────────────
# Ports the icon-design pipeline from the newer reference tool: GPT-4o-mini
# writes a style-guided image prompt (subject color system, audience-adaptive
# styling), gpt-image-2 renders it, rembg strips the background, and the
# result is uploaded to GCS at module_icons/{name}.png — same path convention
# already used for manually-supplied Excel icon URLs.

_ICON_SYSTEM_DESIGN_PROMPT = """
You are a **world-class 3D icon designer** creating icons for an educational platform (classes 4–12).

Your job is to generate **minimal, high-quality 3D icons** that act as **visual learning anchors**.

---
## 🎯 OBJECTIVE
For every input (Subject + Chapter), you must:
* Convert the chapter into **one clear visual concept**
* Design a **simple, recognizable 3D icon**
* Maintain **strict color consistency**
* Ensure icons are **visually lively (not monotone)**
* Remove background **there should be no background**

---
## 🎨 SUBJECT COLOR SYSTEM (PRIMARY – STRICT)
Use ONLY the assigned base color:
* Maths → #1A3FC4
* Science → #7B5EA7
* English → #22C55E
* Geography → #2E7D32
* Economics → #FF8C00
* Civics → #C62828
* History → #800000
* Computer / IT → #1FB7EB
* Commerce → #3D2DB5
* EVS → #6B8E23
* Psychology → #FF6B35
❗ Do NOT mix subject colors
❗ Base color must dominate (80–85%)

---
## 🎨 ACCENT COLOR SYSTEM (MANDATORY)
Each subject MUST use its predefined accent color (10–15%):
* Maths → #FFD54F (Warm Amber)
* Science → #4FC3F7 (Sky Cyan)
* English → #FFC107 (Golden Yellow)
* Geography → #FDD835 (Sun Yellow)
* Economics → #42A5F5 (Cool Blue)
* Civics → #E0E0E0 (Soft Silver)
* History → #D4AF37 (Antique Gold)
* Computer → #7E57C2 (Soft Violet)
* Commerce → #26C6DA (Aqua Cyan)
* EVS → #81D4FA (Light Sky)
* Psychology → #BA68C8 (Soft Purple)

### Accent Rules:
* Use only ONE accent color
* Use on small details only (edges, highlights, secondary elements)
* Must NOT overpower base color

---
## 🎨 BRAND CONSISTENCY (SUBTLE – 5%)
Add a very subtle tint using:
* #00167A OR
* #1B00AD

Use as:
* soft shadow tint OR
* slight edge highlight
❗ Must be barely noticeable
❗ Must NOT compete with main colors

---
## 🧱 DESIGN STYLE
* ADAPT THE STYLE based on the provided Target Audience (Playful/Chunky for younger classes, Sleek/Mature for older classes).
* Rounded edges
* Smooth matte finish
* Minimal (1–2 objects only)

---
## 💡 LIGHTING
* Soft light from top-left
* Gentle shadow below
* No harsh contrast

---
## 📐 COMPOSITION
* Centered
* Less spacing
* Fill the frame
* No clutter
* No background elements

---
## 🎨 BACKGROUND
* Light neutral (#E8EDF8 or off-white)

---
## 🧠 CONCEPT RULE
Before generating, decide:
"What is the ONE visual that represents this chapter?"

Then:
* Use symbols, not scenes
* Avoid storytelling
* Keep it instantly understandable

---
## ✍️ TEXT RULE
* Avoid text inside icons
* Only if absolutely necessary (max 1–2 words)

---
## ❌ DO NOT
* Use multiple subject colors
* Add unnecessary elements
* Create complex scenes
* Use flat design
* Break consistency

---
## 📦 OUTPUT FORMAT
Concept:
[One-line explanation]

Icon Prompt:
"A clean 3D icon of [main object], representing [concept], primarily in [base color hex] with subtle [accent color hex] highlights, [Insert exact adaptive styling details here based on the target audience], centered composition, fill frame, light neutral background, modern educational app style"
"""


def _audience_style_for_filename(filename: str) -> str:
    class_match = re.search(r'(?:class|grade|std)[\s_-]*(\d+)', filename, re.IGNORECASE)
    if class_match:
        class_num = int(class_match.group(1))
        if class_num <= 7:
            return (
                "Target Audience: Young students (Class 4-7). Style Rules: Make it a cute miniature diorama. "
                "Use thick, chunky, toy-like exaggerated proportions. Materials should resemble soft clay or "
                "vibrant plastic. Keep it playful and highly approachable."
            )
        return (
            "Target Audience: Older students (Class 8-12). Style Rules: Make it mature, sophisticated, and sleek. "
            "Use precision geometric forms, frosted glass, and premium matte materials inspired by high-end "
            "macOS/iOS app icons. Avoid making it look like a toy."
        )
    return "Target Audience: General students. Style Rules: Balanced modern 3D geometry, premium and polished."


def _generate_icon_prompt_sync(client, model: str, subject: str, chapter: str, filename: str) -> str:
    """Uses the LLM as a design agent to craft the image prompt for one chapter/module."""
    audience_style = _audience_style_for_filename(filename)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _ICON_SYSTEM_DESIGN_PROMPT},
            {"role": "user", "content": f"Subject: {subject}\nChapter: {chapter}\n{audience_style}"},
        ],
        temperature=0.3,
    )
    output_text = response.choices[0].message.content.strip()
    prompt_match = re.search(r"Icon Prompt:\s*(.*)", output_text, re.DOTALL | re.IGNORECASE)
    return prompt_match.group(1).strip().strip('"').strip("'") if prompt_match else output_text.strip()


def _render_image_sync(client, model: str, prompt_text: str) -> bytes:
    """Renders the icon via OpenAI image generation. Network-bound — safe to run concurrently."""
    import base64

    response = client.images.generate(model=model, prompt=prompt_text, n=1, size="1024x1024")
    return base64.b64decode(response.data[0].b64_json)


def _strip_background_sync(image_bytes: bytes) -> bytes:
    """
    Removes the icon's background via rembg. CPU-bound — onnxruntime inference,
    NOT network wait. Callers must serialise this (see _rembg_gate): running
    several at once saturates every core, and because this service shares a VM
    with nginx/gunicorn/celery/postgres, that takes the whole site down.
    """
    from io import BytesIO

    from PIL import Image
    from rembg import remove

    raw_image = Image.open(BytesIO(image_bytes))
    transparent_icon = remove(raw_image)
    out = BytesIO()
    transparent_icon.save(out, format="PNG")
    return out.getvalue()


_rembg_semaphore = None


def _rembg_gate():
    """Lazily-created semaphore so background removal never runs more than one
    at a time, regardless of how many files are being processed concurrently."""
    global _rembg_semaphore
    if _rembg_semaphore is None:
        _rembg_semaphore = asyncio.Semaphore(1)
    return _rembg_semaphore


async def _generate_module_icon(subject_name: str, module_name: str, filename: str) -> str | None:
    """
    Generates a 3D icon for one module and uploads it to GCS, returning the
    public URL — or None if generation fails (never blocks the rest of
    hierarchy extraction; matches how image-generation failures are handled
    elsewhere in this service).
    """
    from config import settings
    from openai import OpenAI

    if not settings.openai_api_key:
        logger.warning(f"Skipping icon generation for '{module_name}' — OPENAI_API_KEY not configured.")
        return None

    client = OpenAI(api_key=settings.openai_api_key)
    loop = asyncio.get_event_loop()

    try:
        icon_prompt = await loop.run_in_executor(
            None, _generate_icon_prompt_sync, client, settings.openai_hierarchy_model, subject_name, module_name, filename,
        )
        # Rendering is a network call — fine to overlap with other files.
        raw_image_bytes = await loop.run_in_executor(
            None, _render_image_sync, client, settings.openai_icon_model, icon_prompt,
        )
        # Background removal is CPU-bound, so it goes through the gate one at a time.
        async with _rembg_gate():
            png_bytes = await loop.run_in_executor(None, _strip_background_sync, raw_image_bytes)

        from services.pdf_processor import upload_bytes_to_gcs
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', module_name).upper()
        gcs_path = f"module_icons/{safe_name}.png"
        return upload_bytes_to_gcs(png_bytes, settings.gcs_bucket_name, gcs_path, content_type="image/png")
    except Exception as exc:
        logger.warning(f"Icon generation failed for module '{module_name}': {exc}")
        return None
