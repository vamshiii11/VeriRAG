# VeriRAG Research-Grade Completion

This package upgrades the supplied VeriRAG UI prototype into a real two-service application:

- React/Vite frontend
- FastAPI backend
- SQLite locally / PostgreSQL-ready
- local filesystem / S3-compatible object storage
- server-side JWT authentication
- OCR for scanned PDF/image input
- sentence-transformer embeddings
- FAISS semantic retrieval
- BM25 keyword retrieval
- hybrid retrieval + transparent reranking
- LLM generation via Ollama or OpenAI-compatible API
- persistent query/claim/evidence/temporal/knowledge-gap models
- temporal policy relationships
- semantic knowledge-gap clustering foundation
- WebSocket processing events
- persisted analytics
- global search API
- responsive/mobile navigation

## Run on Windows

### 1. Install prerequisites

Install:
- Node.js 20+
- pnpm
- Python 3.11+
- Tesseract OCR (required for scanned documents)
- Ollama (recommended for local LLM generation)

For Tesseract, after installing it, put its executable path in `backend/.env`:
`TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`

### 2. Frontend

From the project root:

```powershell
pnpm install
pnpm dev
```

Frontend: http://localhost:5173

### 3. Backend

Open a second terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Backend: http://localhost:8000
API docs: http://localhost:8000/docs

### Docker Compose deployment

Install Docker Desktop, copy `backend/.env.example` to `backend/.env`, set a strong
`JWT_SECRET`, and start both services from the project root:

```powershell
docker compose up --build
```

Open http://localhost:8080. The Nginx container serves the built React application
and proxies `/api` and WebSocket traffic to FastAPI. Uploaded documents, indexes,
and the SQLite database are persisted under `backend/storage` and `backend`.

To stop the deployment:

```powershell
docker compose down
```

For managed hosting, deploy the `backend` container as a Python service and the
root frontend image as a web service. Netlify can host the static frontend, but
its included Node function is only a legacy adapter and does not replace the
FastAPI document-processing service or its persistent storage.

### 4. LLM

Recommended local setup:

```powershell
ollama pull llama3.2
```

Keep:

`LLM_PROVIDER=ollama`
`LLM_MODEL=llama3.2`
`LLM_BASE_URL=http://localhost:11434`

Or configure an OpenAI-compatible endpoint in `.env`.

If no LLM server is available, the API uses a clearly labelled extractive safety fallback; it never invents unsupported facts.

## First login

Open the frontend. Enter an email and a password of at least 8 characters. The application registers the account automatically if it does not exist, then returns a server-issued JWT.

Authentication is enforced by the backend; documents and queries are scoped to the authenticated user.

## Research test workflow

Upload the supplied sample documents from `sample_docs/`.

Try:
1. `What is the current remote work allowance?`
2. `Can employees work remotely 3 days per week without manager approval?`
3. `What was the WFH policy in 2023?`
4. `What is the penalty for violating the WFH policy?`
5. `How many annual leave days do employees receive?`

The first three exercise temporal/evidence retrieval. The fourth should produce insufficient evidence rather than a fabricated penalty. The fifth demonstrates conflict handling when the conflicting sample policies are loaded.

## Important implementation note

FAISS and sentence-transformers download/load models locally on first use. This can take time and disk space. Tesseract must be installed separately because it is an OS executable.

For production, set:
- `DATABASE_URL` to PostgreSQL
- `STORAGE_PROVIDER=s3`
- S3 credentials and bucket
- a strong random `JWT_SECRET`
- HTTPS/reverse proxy
- an authenticated LLM endpoint

## Architecture

Browser
→ Vite React
→ `/api` proxy
→ FastAPI
→ auth
→ document extraction/OCR
→ chunking
→ sentence-transformer
→ FAISS + BM25
→ reranking
→ LLM
→ claim verification
→ temporal reasoning
→ evidence graph
→ trust score
→ semantic knowledge-gap analysis
→ SQL database



## Verified VS Code setup

### Windows prerequisites
- Python 3.11+
- Node.js 20+
- pnpm 10+ (or install the package manager version shown in package.json)
- Tesseract OCR installed and added to PATH for scanned documents
- Ollama installed with a chat model (default: llama3.2), or configure an OpenAI-compatible provider

### Terminal 1 — backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Terminal 2 — frontend
```powershell
pnpm install
pnpm dev
```
Open http://localhost:5173. The Vite proxy sends /api requests to http://127.0.0.1:8000.

### First test
1. Register/login with an email and an 8+ character password.
2. Upload the sample WFH 2023/2024/2025 PDFs from `sample_docs`.
3. Ask: `What is the current remote work allowance?`
4. Ask: `Can employees work remotely 3 days per week without manager approval?`
5. Ask: `What is the penalty for violating the remote work policy?`
6. Open Evidence Graph, Knowledge Gaps and Analytics.

The backend must have a reachable LLM provider for generated answers. If Ollama is used, start it and pull the configured model before querying.

## Reproducible research workflow

The default retrieval weights are `SEMANTIC_WEIGHT=0.65` and `BM25_WEIGHT=0.35`; they must sum to `1.0`. Configure them in `backend/.env` together with `RETRIEVAL_CANDIDATE_MULTIPLIER` when running an experiment.

Run deterministic backend checks with the project virtual environment:

```powershell
cd backend
..\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from tests.test_research_logic import *; print('Use pytest when installed, or call the test functions directly.')"
```

The Basic RAG comparator is exposed at `/api/baseline-query`. To run the measured comparison against the supplied cases:

```powershell
python scripts/run_evaluation.py --email <account> --password <password>
```

The runner writes raw answers, source hits, trust details, and expectation checks to `evaluation-results.json`; it does not manufacture aggregate benchmark scores.
