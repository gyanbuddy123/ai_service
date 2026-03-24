# MCQ Generation Service

A FastAPI microservice for AI-powered multiple-choice question generation, modification, and PDF ingestion. Uses Claude Sonnet (via Vertex AI) as the primary model, with Gemini 2.0 Flash as an automatic fallback.

## Features

- **MCQ generation** — generates high-quality questions from PDF/theory content using Bloom's Taxonomy and Item Response Theory
- **RAG-based context** — PDFs are chunked, embedded, and stored in Qdrant; relevant chunks are retrieved per topic at generation time
- **Dual model support** — Claude Sonnet (primary) with tool-use schema enforcement; Gemini 2.0 Flash (fallback) with structured JSON output
- **Question modification** — rephrase, change difficulty, rewrite distractors, or custom edits via Claude
- **Built-in validation** — rejects questions with missing fields, no correct answer, duplicate stems, or hints that leak the answer
- **Mobile-safe output** — enforces Unicode symbols instead of LaTeX across all fields

## Architecture

```
Client (Django backend)
        │
        ▼
  FastAPI Service
  ├── POST /ai/generate     — generate MCQs for a topic
  ├── POST /ai/modify       — modify a single question
  ├── POST /ai/embed        — ingest a PDF into Qdrant
  └── GET  /health          — liveness + Qdrant readiness
        │
        ├── Claude Sonnet (Vertex AI) ──── primary LLM
        ├── Gemini 2.0 Flash (Vertex AI) ─ fallback LLM
        └── Qdrant ──────────────────────── vector store
```

## Requirements

- Python 3.11+
- Google Cloud project with Vertex AI API enabled
- GCP service account with `Vertex AI User` role
- Qdrant instance (local or cloud)

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd mcq-generation-service
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root. All settings are defined in `config.py` — set any you need to override:

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
DJANGO_CALLBACK_URL=http://localhost:8000/api/internal/ai-callback
```

See `config.py` for the full list of available settings and their defaults.

### 3. Start Qdrant

```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 4. Run the service

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## API

### `POST /ai/generate`

Generate MCQs for a topic.

**Request:**
```json
{
  "session_id": "uuid",
  "chapter_id": "uuid",
  "subject": "Physics",
  "chapter": "Light",
  "topic": "Refraction",
  "num_questions": 10,
  "grade_level": 9,
  "context_text": "Fallback theory text if no PDF indexed",
  "existing_question_stems": ["What is reflection?"]
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "questions": [
    {
      "id": "q_abc123",
      "question_text": "...",
      "question_type": "mcq_single",
      "options": [
        {"option_text": "...", "is_correct": false},
        {"option_text": "...", "is_correct": true},
        {"option_text": "...", "is_correct": false},
        {"option_text": "...", "is_correct": false}
      ],
      "hint": "...",
      "explanation": "...",
      "difficulty_level": 3,
      "bloom_category": "APPLY",
      "topic_tag": "refraction",
      "exp_points": 10,
      "question_order": 1
    }
  ],
  "total_generated": 10,
  "total_rejected": 0,
  "model_used": "claude-sonnet-4-6",
  "generation_time_ms": 4200
}
```

### `POST /ai/modify`

Modify a single question.

**Request:**
```json
{
  "question": { "question_text": "...", "options": [...] },
  "modification_type": "REPHRASE",
  "instruction": "",
  "grade_level": 9,
  "subject": "Physics",
  "chapter": "Light",
  "topic": "Refraction"
}
```

Supported `modification_type` values: `REPHRASE`, `CHANGE_DIFFICULTY`, `CHANGE_OPTIONS`, `REGENERATE`, `CUSTOM`.

### `POST /ai/embed`

Ingest a PDF for a chapter into Qdrant.

**Request (multipart/form-data):**
- `chapter_id` — UUID of the chapter
- `file` — PDF file

### `GET /health`

```json
{ "status": "ok", "qdrant_collection_ready": true }
```

## Project Structure

```
├── main.py                  # FastAPI app + lifespan
├── config.py                # Settings via pydantic-settings
├── requirements.txt
├── routers/
│   ├── generate.py          # /ai/generate endpoint
│   ├── modify.py            # /ai/modify endpoint
│   └── embed.py             # /ai/embed endpoint
├── services/
│   ├── llm_provider.py      # Claude + Gemini providers, MCQGenerationService
│   ├── prompt_builder.py    # System/user prompt builders + tool schema
│   ├── mcq_validator.py     # Schema validation, dedup, hint-leak detection
│   └── vector_store.py      # Qdrant client, PDF chunking, retrieval
└── schemas/
    ├── mcq.py               # GenerateRequest, GeneratedQuestion, GenerateResponse
    └── pdf.py               # EmbedResponse
```

## Difficulty Levels

| Level | Bloom's Category | Description |
|-------|-----------------|-------------|
| 1 | REMEMBER | Recall facts, definitions |
| 2 | UNDERSTAND | Explain concepts |
| 3 | APPLY | Use knowledge in new situations |
| 4 | ANALYZE | Compare, contrast, break down |
| 5 | EVALUATE / CREATE | Judge, design, propose |

The model assesses the topic's depth and decides the distribution — no hardcoded percentages.
