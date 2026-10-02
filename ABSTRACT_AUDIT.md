# VeriRAG Abstract Compliance Audit

## Original uploaded folder assessment

The uploaded folder was **not research-grade complete**.

Major mismatches found:

| Abstract requirement | Original state | Result after upgrade |
|---|---|---|
| OCR for scanned PDFs/images | Missing | Implemented with PyMuPDF + Tesseract |
| Sentence-transformer embeddings | Missing | Implemented |
| FAISS semantic retrieval | Missing | Implemented |
| BM25 hybrid retrieval | Missing | Implemented |
| Evidence reranking | Missing | Implemented with transparent reranker |
| Persistent claims | Missing; JSON only | SQLAlchemy model |
| Persistent evidence | Missing | SQLAlchemy model |
| Persistent temporal relations | Empty endpoint | SQLAlchemy model + detection |
| Full LLM generation | Hardcoded/extractive logic | Ollama/OpenAI-compatible provider |
| Claim decomposition | Claims were document snippets | LLM decomposition + safe fallback |
| Claim contradiction verification | Keyword heuristic | Per-claim evidence verification |
| Temporal conflict resolution | Missing | Version/effective-date logic + relations |
| Semantic knowledge-gap clustering | Exact topic grouping | Sentence-transformer + DBSCAN |
| WebSocket/SSE | Missing | WebSocket event bus |
| Production database | JSON files | SQLAlchemy; PostgreSQL-ready |
| Object storage | No storage layer | Local/S3-compatible abstraction |
| Server authentication | localStorage flag | Backend JWT + hashed passwords |
| Dashboard charts | Static/hardcoded UI | Persisted analytics + Recharts |
| Global search | Visual input only | Functional API + result dropdown |
| Mobile navigation | Missing | Functional responsive menu |

## Important implementation boundary

The application is now architected so that research-grade services are real components, but some external capabilities still require local configuration:

- Tesseract must be installed for OCR.
- The sentence-transformer model is downloaded on first use.
- FAISS is built from persisted chunks.
- Ollama or an OpenAI-compatible endpoint is required for actual LLM generation.
- PostgreSQL/S3 are production configuration choices; local SQLite/local storage are the development defaults.

The system has a safe extractive fallback when an LLM provider is unavailable. That fallback is explicitly not presented as LLM generation and does not fabricate unsupported facts.

## Original folder's biggest issue

The original backend was a lightweight Express/JSON prototype. It calculated keyword matches against document text and returned hardcoded/heuristic claims, trust factors, temporal relations and knowledge-gap groupings. Therefore it did **not** satisfy the research abstract.

This package replaces that prototype backend with a FastAPI research-grade backend while retaining the React/Vite frontend design.

## Verification performed

- Python backend source compiled successfully with `compileall`.
- Project structure was inspected after upgrade.
- The final package contains setup instructions and sample research documents.
- A full browser/production environment test cannot be honestly claimed from this isolated build environment because Node/Python dependencies, Tesseract, FAISS model download and an LLM service are external runtime dependencies.

Run the test matrix in README.md after installing dependencies and starting the services.
