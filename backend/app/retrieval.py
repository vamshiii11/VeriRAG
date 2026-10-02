import json, pickle, re, logging
from pathlib import Path
from collections import OrderedDict
from threading import Lock, RLock
import numpy as np
from rank_bm25 import BM25Okapi
from .config import resolve_backend_path, settings

logger=logging.getLogger(__name__)

class Retriever:
    def __init__(self):
        if abs((settings.semantic_weight + settings.bm25_weight) - 1.0) > 1e-6:
            raise ValueError("SEMANTIC_WEIGHT and BM25_WEIGHT must sum to 1.0")
        self.model = None
        self.root = resolve_backend_path(settings.storage_path).parent / "indexes"
        self.root.mkdir(parents=True, exist_ok=True)
        self.states = {}
        self._owner_locks = {}
        self._owner_locks_guard = Lock()
        self._model_lock = Lock()
        self._query_embeddings = OrderedDict()
        self._query_embedding_lock = Lock()

    def _owner_lock(self, owner_id):
        with self._owner_locks_guard:
            return self._owner_locks.setdefault(owner_id, RLock())

    def model_load(self):
        if self.model is None:
            with self._model_lock:
                if self.model is None:
                    from sentence_transformers import SentenceTransformer
                    self.model = SentenceTransformer(settings.embedding_model)

    def _encode_query(self, query):
        with self._query_embedding_lock:
            if query in self._query_embeddings:
                self._query_embeddings.move_to_end(query)
                return self._query_embeddings[query].copy()
        self.model_load()
        encoded=np.asarray(self.model.encode([query],normalize_embeddings=True),dtype="float32")
        with self._query_embedding_lock:
            self._query_embeddings[query]=encoded
            self._query_embeddings.move_to_end(query)
            while len(self._query_embeddings)>512:
                self._query_embeddings.popitem(last=False)
        return encoded.copy()

    def _paths(self, owner_id):
        root = self.root / str(owner_id)
        root.mkdir(parents=True, exist_ok=True)
        return root, root / "faiss.index", root / "chunk_ids.json", root / "bm25.pkl"

    def _load(self, owner_id):
        if owner_id in self.states:
            return self.states[owner_id]
        root, faiss_path, ids_path, bm_path = self._paths(owner_id)
        index = None; chunk_ids = []; bm25 = None; tokens = []
        try:
            import faiss
            if faiss_path.exists() and ids_path.exists():
                index = faiss.read_index(str(faiss_path))
                chunk_ids = json.loads(ids_path.read_text())
        except Exception as exc:
            logger.warning("FAISS index load failed for owner %s; rebuilding: %s",owner_id,exc)
            index = None; chunk_ids = []
        try:
            if bm_path.exists():
                data = pickle.loads(bm_path.read_bytes()); bm25 = data.get("bm25"); tokens = data.get("tokens", [])
        except Exception as exc:
            logger.warning("BM25 index load failed for owner %s; rebuilding: %s",owner_id,exc)
            bm25 = None; tokens = []
        state = {"index": index, "chunk_ids": chunk_ids, "bm25": bm25, "tokens": tokens}
        self.states[owner_id] = state
        return state

    def rebuild(self, db, owner_id):
        with self._owner_lock(owner_id):
            return self._rebuild(db, owner_id)

    def _rebuild(self, db, owner_id):
        from .models import Chunk, Document
        rows = (db.query(Chunk).join(Document, Chunk.document_id == Document.id)
                .filter(Document.owner_id == owner_id).order_by(Chunk.id).all())
        texts = [r.text for r in rows]
        if texts:
            self.model_load()
            emb = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            emb = np.asarray(emb, dtype="float32")
            dim = emb.shape[1]
        else:
            emb = np.empty((0, 384), dtype="float32"); dim = 384
        import faiss
        index = faiss.IndexFlatIP(dim)
        if len(emb): index.add(emb)
        root, faiss_path, ids_path, bm_path = self._paths(owner_id)
        faiss.write_index(index, str(faiss_path))
        ids = [r.id for r in rows]
        ids_path.write_text(json.dumps(ids))
        toks = [re.findall(r"\b\w+\b", t.lower()) for t in texts]
        bm25 = BM25Okapi(toks) if toks else None
        bm_path.write_bytes(pickle.dumps({"bm25": bm25, "tokens": toks}))
        state = {"index": index, "chunk_ids": ids, "bm25": bm25, "tokens": toks}
        self.states[owner_id] = state
        for row, pos in zip(rows, range(len(rows))):
            row.faiss_row = pos
        db.commit()
        return state

    def add_chunks(self, db, owner_id, chunks, reuse_from_ids=None):
        with self._owner_lock(owner_id):
            return self._add_chunks(db, owner_id, chunks, reuse_from_ids)

    def _add_chunks(self, db, owner_id, chunks, reuse_from_ids=None):
        from .models import Chunk, Document
        if not chunks:
            return self._load(owner_id)
        state = self._load(owner_id)
        if state["index"] is None or state["index"].ntotal != len(state["chunk_ids"]):
            return self.rebuild(db, owner_id)

        new_ids = {chunk.id for chunk in chunks}
        indexed_ids = {
            row[0]
            for row in db.query(Chunk.id)
            .join(Document, Chunk.document_id == Document.id)
            .filter(Document.owner_id == owner_id, Chunk.id.notin_(new_ids))
            .all()
        }
        if indexed_ids != set(state["chunk_ids"]) or len(state["tokens"]) != len(state["chunk_ids"]):
            return self.rebuild(db, owner_id)

        self.model_load()
        source_positions = {chunk_id: position for position, chunk_id in enumerate(state["chunk_ids"])}
        source_ids = reuse_from_ids or [None] * len(chunks)
        vectors = np.empty((len(chunks), state["index"].d), dtype="float32")
        missing = []
        missing_positions = []
        for position, (chunk, source_id) in enumerate(zip(chunks, source_ids)):
            source_position = source_positions.get(source_id)
            if source_position is None:
                missing.append(chunk.text)
                missing_positions.append(position)
            else:
                vectors[position] = state["index"].reconstruct(source_position)
        if missing:
            encoded = np.asarray(self.model.encode(missing, normalize_embeddings=True, show_progress_bar=False), dtype="float32")
            if encoded.shape[1] != state["index"].d:
                return self.rebuild(db, owner_id)
            vectors[missing_positions] = encoded

        start = len(state["chunk_ids"])
        state["index"].add(vectors)
        state["chunk_ids"].extend(chunk.id for chunk in chunks)
        state["tokens"].extend(re.findall(r"\b\w+\b", chunk.text.lower()) for chunk in chunks)
        state["bm25"] = BM25Okapi(state["tokens"])
        root, faiss_path, ids_path, bm_path = self._paths(owner_id)
        import faiss
        faiss.write_index(state["index"], str(faiss_path))
        ids_path.write_text(json.dumps(state["chunk_ids"]))
        bm_path.write_bytes(pickle.dumps({"bm25": state["bm25"], "tokens": state["tokens"]}))
        for position, chunk in enumerate(chunks, start):
            chunk.faiss_row = position
        db.commit()
        return state

    def search(self, db, owner_id, query, k=8):
        with self._owner_lock(owner_id):
            return self._search(db, owner_id, query, k)

    def _search(self, db, owner_id, query, k=8):
        from .models import Chunk, Document
        from sqlalchemy.orm import joinedload
        state = self._load(owner_id)
        if state["index"] is None:
            state = self.rebuild(db, owner_id)
        if not state["chunk_ids"]:
            return []
        if state["index"].ntotal:
            q = self._encode_query(query)
            sem_scores, idx = state["index"].search(q, min(k * settings.retrieval_candidate_multiplier, len(state["chunk_ids"])))
            sem = {state["chunk_ids"][i]: float(sem_scores[0][j]) for j, i in enumerate(idx[0]) if i >= 0}
        else:
            sem = {}
        qt = re.findall(r"\b\w+\b", query.lower())
        bm = state["bm25"].get_scores(qt) if state["bm25"] is not None else []
        bm_norm = {}
        if len(bm):
            mx, mn = max(bm), min(bm)
            for i, value in enumerate(bm):
                bm_norm[state["chunk_ids"][i]] = float((value - mn) / (mx - mn)) if mx != mn else 0.0
        ids = set(sem) | set(sorted(bm_norm, key=bm_norm.get, reverse=True)[:k * settings.retrieval_candidate_multiplier])
        rows = {c.id: c for c in db.query(Chunk).options(joinedload(Chunk.document)).join(Document).filter(Document.owner_id == owner_id, Chunk.id.in_(ids)).all()}
        out = []
        for cid in ids:
            c = rows.get(cid)
            if not c: continue
            semantic = max(0.0, min(1.0, (sem.get(cid, 0.0) + 1.0) / 2.0))
            bm_score = bm_norm.get(cid, 0.0)
            hybrid = settings.semantic_weight * semantic + settings.bm25_weight * bm_score
            # Transparent reranker: combines hybrid relevance with exact phrase and query-token coverage.
            qtokens = set(qt)
            ctokens = set(re.findall(r"\b\w+\b", c.text.lower()))
            coverage = len(qtokens & ctokens) / max(1, len(qtokens))
            phrase = 1.0 if query.lower() in c.text.lower() else 0.0
            rerank = 0.75 * hybrid + 0.15 * coverage + 0.10 * phrase
            out.append({"chunk": c, "semantic": semantic, "bm25": bm_score, "hybrid": hybrid, "rerank": rerank})
        ranked=sorted(out, key=lambda x: x["rerank"], reverse=True)
        selected=[]; seen_documents=set()
        for item in ranked:
            document=item["chunk"].document
            document_key=(document.filename,document.version,document.source) if document else item["chunk"].document_id
            if document_key in seen_documents:
                continue
            selected.append(item); seen_documents.add(document_key)
            if len(selected)>=k:
                break
        return selected or ranked[:k]

retriever = Retriever()
