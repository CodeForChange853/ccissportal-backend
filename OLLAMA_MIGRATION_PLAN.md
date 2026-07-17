# Ollama Migration Plan
> Status: DEFERRED — Current development uses Gemini API. Implement this after the system is stable and ready for Docker containerization + JMeter load testing.

---

## Goal
Remove the Gemini API key dependency and replace all cloud AI calls with a fully local, free Ollama instance. Target: 2,000-student CCIS load on a 16GB RAM machine.

---

## What Gets Replaced

| Current | Replacement | Model |
|---|---|---|
| `gemini_vision.py` → GeminiVisionService | `ollama_vision.py` → OllamaVisionService | `llava:7b` (vision) |
| `gemini_narrator.py` → generate_narrative | `ollama_narrator.py` → generate_narrative | `llama3.2` (text) |
| Support triage sklearn `.pkl` | See triage decision below | `llama3.2` or removed |

---

## New Environment Variables (.env additions)

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TRIAGE_MODEL=llama3.2
OLLAMA_VISION_MODEL=llava
OLLAMA_NARRATOR_MODEL=llama3.2
REDIS_URL=redis://localhost:6379/0
```

---

## Files to Create

| File | Purpose |
|---|---|
| `src/core/ollama_client.py` | httpx wrapper — `call_ollama_text()` and `call_ollama_vision()` using Ollama native `/api/chat` with `format` (JSON schema) + `temperature: 0` |
| `src/core/celery_app.py` | Celery configured with Redis broker/backend, `worker_prefetch_multiplier=1` (protects RAM) |
| `src/tasks.py` | 3 Celery tasks: `task_scan_document`, `task_generate_audit_narrative`, `task_classify_support_ticket` |
| `src/modules/document_processing/ollama_vision.py` | Same interface as GeminiVisionService. Converts image to base64, sends to llava with Pydantic JSON schema enforcement. Reuses all existing confidence scoring logic. |
| `src/modules/audit/ollama_narrator.py` | Same function signature as gemini_narrator. Same prompt, routed through Ollama llama3.2 at temperature=0.3. |
| `src/modules/support/ml/ollama_triage_engine.py` | Optional Ollama-based ticket classifier with strict JSON output and temperature=0. Only relevant if triage is kept. |

---

## Files to Modify

| File | Change |
|---|---|
| `src/core/config.py` | Add 5 new Ollama + Redis settings |
| `src/modules/document_processing/service.py` | Import OllamaVisionService instead of GeminiVisionService. Replace BackgroundTasks with `task_scan_document.delay()`. Remove tenacity/ResourceExhausted retry. |
| `src/modules/document_processing/router.py` | Remove BackgroundTasks param. Use Celery task. |
| `src/modules/audit/service.py` | One-line import change: `gemini_narrator` → `ollama_narrator` |
| `requirements.txt` | Add: `httpx`, `celery[redis]`, `redis`. Remove: `google-genai`, `google-api-core`, `tenacity`. |

---

## Old Gemini Files
`gemini_vision.py` and `gemini_narrator.py` become dead code after migration. Leave in place until migration is verified, then delete.

---

## Worker Startup (for Docker prep)

```bash
# Terminal 1 — FastAPI
uvicorn src.main:app --reload

# Terminal 2 — Celery worker (Windows: --pool=solo avoids multiprocessing issues)
celery -A src.celery_app worker --loglevel=info --pool=solo

# Redis (Docker)
docker run -d -p 6379:6379 redis:alpine
```

---

## Support Ticket Triage Decision
See separate section in main conversation — triage system may be removed and replaced with a student-facing department dropdown. Confirm before implementing.

---

## Architecture: Fast 200 OK Flow (after migration)

```
Student Action (e.g., submit ticket or scan document)
     │
     ▼
FastAPI Router
  ├── Validate request (sync, fast)
  ├── Save DB record with status = PENDING
  ├── Push job → Redis Queue
  └── Return 200 OK immediately (milliseconds)

Celery Worker (background, separate process)
  └── Picks up job → calls Ollama → updates DB record
```
