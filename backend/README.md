# Consiva AI Chatbot

Production-ready multilingual RAG chatbot for Consiva. Answers are grounded strictly in
an approved Consiva knowledge base stored in Pinecone — the assistant never invents facts
outside that source of truth (see `backend/app/services/rag.py` for the enforced system
prompt and fallback rules).

## Stack

- **Backend:** FastAPI, SQLAlchemy (SQLite for dev, Postgres-ready), Pinecone, OpenAI-compatible
  chat + embedding models, JWT auth.
- **Frontend:** Vanilla HTML/CSS/JS, Web Speech API (voice in), SpeechSynthesis (voice out).

## 1. Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env       # then fill in your real API keys
```

Edit `backend/.env`:
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` — any OpenAI-compatible provider works.
- `PINECONE_API_KEY`, `PINECONE_INDEX_NAME` — the index is auto-created on first ingest
  with the right dimensionality if it doesn't exist yet.
- `JWT_SECRET_KEY` — replace with a long random value before deploying.

## 2. Ingest the Consiva knowledge base

Drop approved documents (PDF, DOCX, TXT, Markdown, HTML, CSV) into `backend/data/`, then:

```bash
python scripts/ingest_documents.py
```

This cleans, chunks (~650 tokens, ~100 overlap), embeds, and upserts to Pinecone with
deterministic chunk IDs (path + content hash) — re-running ingestion updates existing
vectors instead of duplicating them.

## 3. Run the backend

```bash
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## 4. Run the frontend

Any static file server works, e.g.:

```bash
cd frontend
python -m http.server 5500
```

Open http://localhost:5500. The frontend calls the API at `http://localhost:8000` by
default — override with `window.CONSIVA_API_BASE` (set before `app.js` loads) if you
deploy the API elsewhere. Make sure that origin is included in `ALLOWED_ORIGINS` in
`backend/.env`.

## Design notes

- **Auth:** full JWT register/login is implemented, plus a `/api/auth/guest` endpoint that
  issues a scoped JWT for an anonymous user so the chat widget works instantly without
  forcing signup — a common pattern for support widgets. All chat/history endpoints require
  a valid bearer token either way.
- **Knowledge restriction:** the system prompt (built from the approved Consiva spec) forces
  two fixed fallback strings — one for questions unrelated to Consiva, one for Consiva
  questions the knowledge base doesn't support — and instructs the model to treat retrieved
  context and user input as data, never as instructions (prompt-injection resistance).
- **Language:** the backend auto-detects the user's language (`langdetect`) unless the
  frontend passes an explicit code, and instructs the model to answer in that language,
  including translated fallback strings, without altering facts, names, or figures.
- **Sources:** every grounded answer returns structured citations (document, section, page,
  URL, relevance score) rendered as chips under the message.

## Voice (hands-free conversation)

Click the mic button to start a hands-free voice conversation:

1. **Silero VAD** (in the browser, loaded from jsDelivr only when voice mode starts) detects when
   the user starts and stops talking — no push-to-talk needed.
2. The utterance is sent to `POST /api/voice/transcribe` → **Groq Whisper** (`GROQ_STT_MODEL`),
   with a vocabulary hint so terms like Consiva, DPDP and ROPA are spelled correctly.
3. The chat request is sent with `voice_mode: true`, so the model answers in short spoken sentences.
4. `POST /api/voice/speak` streams **ElevenLabs** audio (`ELEVENLABS_MODEL_ID`, default
   `eleven_flash_v2_5`, 32 languages) and passes the reply language as `language_code`.
5. The mic stays open while the assistant speaks — the user can simply talk to interrupt it.

Config (`backend/.env`):
- `ELEVENLABS_API_KEY` — needs the Text to Speech permission.
- `ELEVENLABS_VOICE_ID` — free plans can only use ElevenLabs' default voices via the API;
  Voice Library voices need a paid plan.
- `ELEVENLABS_VOICE_OVERRIDES` — optional per-language voices, e.g. `hi:VOICE_ID,ar:VOICE_ID`.
- `TTS_DAILY_CHARS_PER_USER`, `TTS_DAILY_CHARS_GLOBAL`, `TTS_MAX_CHARS_PER_REQUEST` — credit guards.
  Generated audio is cached in `backend/voice_cache/`, and cached replies cost no credits.
