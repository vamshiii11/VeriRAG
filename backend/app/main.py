import base64, os, hashlib, logging
from uuid import uuid4
from datetime import datetime
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy import func
from .config import settings
from .db import Base,engine,get_db,upgrade_sqlite_schema
from .models import User,Document,Chunk,Query,Claim,Evidence,TemporalRelation,KnowledgeGap,ClaimEvidence
from .auth import create_user,verify_password,create_token,current_user
from .storage import storage
from .processing import extract_document,chunk_pages,infer_metadata
from .retrieval import retriever
from .query_engine import analyze,baseline_answer,temporal_relations,update_knowledge_gaps
from .events import bus

logger=logging.getLogger(__name__)
Base.metadata.create_all(bind=engine)
upgrade_sqlite_schema()
app=FastAPI(title=settings.app_name,version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

@app.get("/api/health")
def health(): return {"status":"ok","service":"verirag-api","features":{"ocr":True,"faiss":True,"sentence_transformers":True,"bm25":True,"reranking":True,"llm":True,"temporal":True,"knowledge_gaps":True,"realtime":True,"auth":True}}

@app.post("/api/auth/register")
def register(data:dict,db:Session=Depends(get_db)):
    email=str(data.get("email","")).lower().strip(); pw=str(data.get("password",""))
    if len(pw)<8: raise HTTPException(400,"Password must be at least 8 characters.")
    if db.query(User).filter(func.lower(User.email)==email).first(): raise HTTPException(409,"Email already registered.")
    u=create_user(db,email,pw); return {"token":create_token(u),"user":{"id":u.id,"email":u.email}}

@app.post("/api/auth/login")
def login(data:dict,db:Session=Depends(get_db)):
    email=str(data.get("email","")).lower().strip(); u=db.query(User).filter(func.lower(User.email)==email).first()
    if not u or not verify_password(str(data.get("password","")),u.password_hash): raise HTTPException(401,"Invalid email or password.")
    return {"token":create_token(u),"user":{"id":u.id,"email":u.email}}

@app.get("/api/auth/me")
def me(u:User=Depends(current_user)): return {"id":u.id,"email":u.email}

@app.post("/api/documents")
async def upload_document(file:UploadFile=File(...),metadata_json:str=Form("{}"),db:Session=Depends(get_db),u:User=Depends(current_user)):
    import json
    try:
        metadata=json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(400,"metadata_json must be valid JSON") from exc
    if not isinstance(metadata,dict):
        raise HTTPException(400,"metadata_json must be an object")
    try:
        authority=float(metadata.get("authority",50))
    except (TypeError,ValueError) as exc:
        raise HTTPException(400,"authority must be a number between 0 and 100") from exc
    if not 0 <= authority <= 100:
        raise HTTPException(400,"authority must be a number between 0 and 100")
    data=await file.read()
    if len(data)>50*1024*1024: raise HTTPException(413,"File exceeds 50 MB limit.")
    ext=os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".pdf",".docx",".txt",".png",".jpg",".jpeg",".webp"}: raise HTTPException(400,"Unsupported file type.")
    content_hash=hashlib.sha256(data).hexdigest()
    cached_document=(db.query(Document).filter_by(owner_id=u.id,content_hash=content_hash,status="INDEXED").order_by(Document.created_at.desc()).first())
    if not cached_document:
        legacy_candidates=db.query(Document).filter(Document.owner_id==u.id,Document.size==len(data),Document.content_hash.is_(None),Document.status=="INDEXED").all()
        for candidate in legacy_candidates:
            try:
                candidate_hash=hashlib.sha256(storage.load(candidate.storage_key)).hexdigest()
            except Exception as exc:
                logger.warning("Could not hash legacy document %s for upload reuse: %s",candidate.id,exc)
                continue
            if candidate_hash==content_hash:
                candidate.content_hash=content_hash
                db.commit()
                cached_document=candidate
                break
    did=str(uuid4()); safe_name=os.path.basename(file.filename or "upload.bin"); key=f"{u.id}/{did}/{safe_name}"
    await bus.emit(u.id,"UPLOAD_STARTED","upload","Upload received",5,did)
    storage.save(key,data)
    d=Document(id=did,owner_id=u.id,filename=safe_name,title=metadata.get("title") or os.path.splitext(safe_name)[0],mime_type=file.content_type or "",size=len(data),source=metadata.get("source","User upload"),authority=authority,version=metadata.get("version") or "unversioned",created_date=metadata.get("createdDate"),effective_date=metadata.get("effectiveDate"),expiry_date=metadata.get("expiryDate"),storage_key=key,content_hash=content_hash,status="PROCESSING")
    db.add(d); db.commit()
    try:
        await bus.emit(u.id,"EXTRACTION_STARTED","extraction","Extracting document text",20,did)
        if cached_document:
            cached_chunks=db.query(Chunk).filter_by(document_id=cached_document.id).all()
            pages_text=cached_document.extracted_text or ""
            method=cached_document.extraction_method
            count=cached_document.page_count
            reuse_from_ids=[chunk.id for chunk in cached_chunks]
            chunks=[(chunk.page,chunk.text) for chunk in cached_chunks]
        else:
            pages,method,count=await run_in_threadpool(extract_document,data,file.filename)
            pages_text="\n".join(text for _,text in pages)
            reuse_from_ids=[]
        inferred=infer_metadata(file.filename, pages_text)
        if d.version == "unversioned": d.version = inferred["version"]
        if not d.effective_date: d.effective_date = inferred["effective_date"]
        if not d.created_date: d.created_date = inferred["effective_date"]
        d.metadata_source="manual_and_inferred" if metadata else "inferred"
        d.metadata_uncertain=bool(inferred.get("metadata_uncertain"))
        await bus.emit(u.id,"OCR_COMPLETED" if method=="ocr" else "EXTRACTION_COMPLETED","ocr" if method=="ocr" else "extraction","Text extraction completed",35,did)
        if not cached_document:
            chunks=await run_in_threadpool(chunk_pages,pages)
        await bus.emit(u.id,"CHUNKING_COMPLETED","chunking",f"Created {len(chunks)} chunks",50,did)
        chunk_rows=[]
        for page,text in chunks:
            chunk=Chunk(id=str(uuid4()),document_id=did,page=page,text=text,token_count=len(text.split()))
            db.add(chunk); chunk_rows.append(chunk)
        d.extracted_text=pages_text; d.page_count=count; d.extraction_method=method; d.status="INDEXING"; db.commit()
        await run_in_threadpool(retriever.add_chunks,db,u.id,chunk_rows,reuse_from_ids or None)
        d.status="INDEXED"; db.commit()
        await bus.emit(u.id,"INDEXING_COMPLETED","indexing","FAISS and BM25 indexes updated",80,did)
        await run_in_threadpool(lambda:temporal_relations(db,u.id,db.query(Document).filter(Document.owner_id==u.id).all(),did))
        await bus.emit(u.id,"PROCESSING_COMPLETED","complete","Document indexed and ready",100,did)
    except Exception as e:
        d.status="FAILED"; db.commit(); await bus.emit(u.id,"PROCESSING_FAILED","error",str(e),100,did); raise HTTPException(422,str(e))
    return serialize_document(d)

def serialize_document(d,chunk_count=None):
    return {"id":d.id,"filename":d.filename,"title":d.title,"type":d.mime_type,"size":d.size,"source":d.source,"authority":d.authority,"version":d.version,"createdDate":d.created_date,"effectiveDate":d.effective_date,"expiryDate":d.expiry_date,"metadataSource":d.metadata_source,"metadataUncertain":d.metadata_uncertain,"supersedesDocumentId":d.supersedes_document_id,"chunks":chunk_count if chunk_count is not None else len(d.chunks),"pages":d.page_count,"status":d.status,"extractionMethod":d.extraction_method,"createdAt":d.created_at.isoformat()}

@app.get("/api/documents")
def documents(db:Session=Depends(get_db),u:User=Depends(current_user)):
    chunk_counts=db.query(Chunk.document_id,func.count(Chunk.id).label("chunk_count")).group_by(Chunk.document_id).subquery()
    rows=(db.query(Document,func.coalesce(chunk_counts.c.chunk_count,0)).outerjoin(chunk_counts,Document.id==chunk_counts.c.document_id).filter(Document.owner_id==u.id).order_by(Document.created_at.desc()).all())
    return [serialize_document(document,chunk_count) for document,chunk_count in rows]

@app.get("/api/documents/{id}")
def document(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    d=db.query(Document).filter_by(id=id,owner_id=u.id).first()
    if not d: raise HTTPException(404,"Document not found")
    return {**serialize_document(d),"text":d.extracted_text}

@app.delete("/api/documents/{id}")
def delete_document(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    d=db.query(Document).filter_by(id=id,owner_id=u.id).first()
    if not d: raise HTTPException(404,"Document not found")
    storage.delete(d.storage_key); db.delete(d); db.commit()
    retriever.rebuild(db, u.id)
    return {"deleted":True,"id":id}

@app.post("/api/query")
async def query(data:dict,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=str(data.get("question","")).strip()
    if not q: raise HTTPException(400,"question is required")
    await bus.emit(u.id,"QUERY_STARTED","query","Analyzing question",5)
    await bus.emit(u.id,"RETRIEVAL_STARTED","retrieval","Running semantic + BM25 retrieval",20)
    obj=await run_in_threadpool(analyze,db,u.id,q)
    await bus.emit(u.id,"RERANKING_COMPLETED","reranking","Evidence reranking completed",35,obj.id)
    await bus.emit(u.id,"GENERATION_COMPLETED","generation","Evidence-grounded generation completed",50,obj.id)
    await bus.emit(u.id,"CLAIM_VERIFICATION_COMPLETED","verification","Claim verification completed",70,obj.id)
    await bus.emit(u.id,"TEMPORAL_ANALYSIS_COMPLETED","temporal","Temporal analysis completed",82,obj.id)
    await bus.emit(u.id,"GRAPH_COMPLETED","graph","Evidence graph completed",92,obj.id)
    await bus.emit(u.id,"QUERY_COMPLETED","complete","Query analysis completed",100,obj.id)
    return query_response(db,obj)

@app.post("/api/baseline-query")
def baseline_query(data:dict,db:Session=Depends(get_db),u:User=Depends(current_user)):
    question=str(data.get("question","")).strip()
    if not question: raise HTTPException(400,"question is required")
    try:
        return baseline_answer(db,u.id,question)
    except RuntimeError as exc:
        raise HTTPException(503,str(exc)) from exc

def query_response(db,q):
    claims=[]
    for claim in q.claims:
        claim_evidence=[]
        for link in claim.links:
            evidence_row=db.get(Evidence,link.evidence_id)
            document=db.get(Document,evidence_row.document_id) if evidence_row else None
            if evidence_row:
                claim_evidence.append({"evidenceId":evidence_row.id,"documentId":evidence_row.document_id,"document":document.filename if document else "Deleted document","chunkId":evidence_row.chunk_id,"page":evidence_row.page,"version":document.version if document else "unknown","effectiveDate":document.effective_date if document else None,"temporalStatus":link.temporal_status or evidence_row.temporal_status,"relation":link.relation})
        claims.append({"id":claim.id,"text":claim.text,"status":claim.status,"confidence":claim.confidence,"reason":claim.verification_reason,"evidence":claim_evidence})
    evidence=[]
    for e in q.evidence:
        d=db.get(Document,e.document_id)
        evidence.append({"id":e.id,"document":d.filename if d else "Deleted document","version":d.version if d else "unknown","source":d.source if d else "unknown","page":e.page,"snippet":e.snippet,"relevance":round(e.rerank_score*100),"semanticScore":e.semantic_score,"bm25Score":e.bm25_score,"hybridScore":e.hybrid_score,"rerankScore":e.rerank_score,"temporalStatus":e.temporal_status,"documentId":e.document_id,"chunkId":e.chunk_id})
    trust={"score":q.trust,**(q.trust_details or {}),"explanation":(q.trust_details or {}).get("explanation","Trust details were not recorded for this query.")}
    return {"queryId":q.id,"question":q.question,"intent":q.intent,"topic":q.topic,"keywords":q.question.lower().split(),"reformulations":[q.question], "status":q.status,"answer":q.answer,"coverage":q.coverage,"claims":claims,"evidence":evidence,"missingInformation":q.missing_information or [],"trust":trust,"temporalSummary":q.temporal_summary or {},"knowledgeGap":{"detected":q.status!="ANSWERABLE","topic":q.topic,"reason":(q.missing_information or ["Evidence coverage is insufficient."])[0]},"generatedAt":q.created_at.isoformat()}

@app.get("/api/query/{id}")
def get_query(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(Query).filter_by(id=id,owner_id=u.id).first()
    if not q: raise HTTPException(404,"Query not found")
    return query_response(db,q)

@app.get("/api/queries")
def recent_queries(limit:int=5,db:Session=Depends(get_db),u:User=Depends(current_user)):
    limit=max(1,min(limit,5))
    rows=db.query(Query).filter_by(owner_id=u.id).order_by(Query.created_at.desc()).limit(limit).all()
    return [{"id":row.id,"question":row.question,"answer":row.answer,"status":row.status,"createdAt":row.created_at.isoformat()} for row in rows]

@app.get("/api/query/{id}/claims")
def get_claims(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(Query).filter_by(id=id,owner_id=u.id).first()
    if not q: raise HTTPException(404,"Query not found")
    return query_response(db,q)["claims"]

@app.get("/api/query/{id}/evidence")
def get_evidence(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(Query).filter_by(id=id,owner_id=u.id).first()
    if not q: raise HTTPException(404,"Query not found")
    return query_response(db,q)["evidence"]

@app.get("/api/query/{id}/temporal-relations")
def query_temporal(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(Query).filter_by(id=id,owner_id=u.id).first()
    if not q: raise HTTPException(404,"Query not found")
    evidence_document_ids={e.document_id for e in q.evidence}
    rels=db.query(TemporalRelation).filter(TemporalRelation.owner_id==u.id,TemporalRelation.older_document_id.in_(evidence_document_ids)|TemporalRelation.newer_document_id.in_(evidence_document_ids)).all()
    return temporal_json(db,rels)

def temporal_json(db,rels):
    out=[]
    for r in rels:
        a=db.get(Document,r.older_document_id); b=db.get(Document,r.newer_document_id)
        if a and b: out.append({"id":r.id,"olderDocument":{"id":a.id,"filename":a.filename,"version":a.version,"effectiveDate":a.effective_date},"newerDocument":{"id":b.id,"filename":b.filename,"version":b.version,"effectiveDate":b.effective_date},"relationType":r.relation_type,"confidence":r.confidence,"reason":r.reason})
    return out

@app.get("/api/query/{id}/graph")
def query_graph(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(Query).filter_by(id=id,owner_id=u.id).first()
    if not q: raise HTTPException(404,"Query not found")
    return build_graph(db,q)

@app.post("/api/evidence-graph")
def evidence_graph(data:dict,db:Session=Depends(get_db),u:User=Depends(current_user)):
    qtext=str(data.get("query","")).strip()
    if not qtext: raise HTTPException(400,"query is required")
    # If no persisted query exists, create an analysis first so graph provenance is real.
    q=analyze(db,u.id,qtext)
    return build_graph(db,q)

def build_graph(db,q):
    nodes=[]; node_ids=set(); edges=[]; edge_ids=set()
    def add_node(node):
        if node["id"] not in node_ids:
            nodes.append(node); node_ids.add(node["id"])
    def add_edge(edge):
        if edge["id"] not in edge_ids:
            edges.append(edge); edge_ids.add(edge["id"])
    add_node({"id":f"query-{q.id}","kind":"QUERY","label":q.question,"detail":"Persisted query","documentId":None})
    for c in q.claims:
        add_node({"id":f"claim-{c.id}","kind":"CLAIM","label":c.text,"detail":c.status})
        add_edge({"id":f"q-c-{c.id}","from":f"query-{q.id}","to":f"claim-{c.id}","label":"DERIVED_FROM"})
        for link in c.links:
            e=link.evidence; d=db.get(Document,e.document_id)
            if not e: continue
            add_node({"id":f"evidence-{e.id}","kind":"EVIDENCE","label":e.snippet[:100],"detail":f"Chunk {e.chunk_id} · page {e.page} · {e.version if hasattr(e,'version') else (d.version if d else 'unknown')} · {e.temporal_status}","source":d.filename if d else "unknown","documentId":e.document_id})
            add_edge({"id":f"c-e-{link.id}","from":f"claim-{c.id}","to":f"evidence-{e.id}","label":"CONTRADICTS" if link.relation=="CONTRADICTS" else "SUPPORTS"})
            if d:
                add_node({"id":f"document-{d.id}","kind":"DOCUMENT","label":d.filename,"detail":f"{d.source} · {d.effective_date or 'No effective date'}","documentId":d.id})
                add_edge({"id":f"e-d-{e.id}","from":f"evidence-{e.id}","to":f"document-{d.id}","label":"DERIVED_FROM"})
                add_node({"id":f"version-{d.id}","kind":"VERSION","label":d.version,"detail":f"Effective {d.effective_date or 'unknown'} · {e.temporal_status}","documentId":d.id})
                add_edge({"id":f"d-v-{d.id}","from":f"document-{d.id}","to":f"version-{d.id}","label":"DERIVED_FROM"})
    document_ids={e.document_id for e in q.evidence}
    for r in db.query(TemporalRelation).filter(TemporalRelation.owner_id==q.owner_id,TemporalRelation.older_document_id.in_(document_ids)|TemporalRelation.newer_document_id.in_(document_ids)).all():
        label=r.relation_type if r.relation_type in {"SUPERSEDES","GENUINE_CONFLICT"} else "RELATED"
        add_edge({"id":f"tem-{r.id}","from":f"document-{r.older_document_id}","to":f"document-{r.newer_document_id}","label":label})
    return {"queryId":q.id,"query":q.question,"nodes":nodes,"edges":edges,"matchedDocuments":len(q.evidence),"generatedAt":datetime.utcnow().isoformat()}

@app.get("/api/knowledge-gaps")
def gaps(db:Session=Depends(get_db),u:User=Depends(current_user)):
    update_knowledge_gaps(db,u.id)
    rows=db.query(KnowledgeGap).filter_by(owner_id=u.id).order_by(KnowledgeGap.updated_at.desc()).all()
    return [{"id":g.id,"topic":g.topic,"reason":g.reason,"frequency":g.frequency,"lastSeen":g.updated_at.isoformat(),"queries":[(db.get(Query,qid).question if db.get(Query,qid) else qid) for qid in list(g.query_ids or [])],"representativeQuery":g.representative_query,"averageTrust":round(g.average_trust),"evidenceCoverage":round(g.evidence_coverage)} for g in rows]

@app.get("/api/analytics")
def analytics(db:Session=Depends(get_db),u:User=Depends(current_user)):
    query_rows=db.query(Query.created_at,Query.trust,Query.coverage).filter_by(owner_id=u.id).order_by(Query.created_at).all()
    claim_counts=dict(db.query(Claim.status,func.count(Claim.id)).join(Query).filter(Query.owner_id==u.id).group_by(Claim.status).all())
    latest_indexed=db.query(func.max(Document.updated_at)).filter(Document.owner_id==u.id,Document.status=="INDEXED").scalar()
    return {"documents":db.query(func.count(Document.id)).filter_by(owner_id=u.id).scalar() or 0,"chunks":db.query(func.count(Chunk.id)).join(Document).filter(Document.owner_id==u.id).scalar() or 0,"queries":len(query_rows),"claims":sum(claim_counts.values()),"evidence":db.query(func.count(Evidence.id)).join(Query).filter(Query.owner_id==u.id).scalar() or 0,"claimStatuses":{status:claim_counts.get(status,0) for status in ["SUPPORTED","PARTIALLY_SUPPORTED","CONTRADICTED","UNVERIFIED"]},"knowledgeGaps":db.query(func.count(KnowledgeGap.id)).filter_by(owner_id=u.id).scalar() or 0,"temporalRelations":db.query(func.count(TemporalRelation.id)).filter_by(owner_id=u.id).scalar() or 0,"averageTrust":round(db.query(func.avg(Query.trust)).filter_by(owner_id=u.id).scalar() or 0),"latestIndexed":latest_indexed.isoformat() if latest_indexed else None,"queryTimeline":[{"date":created_at.date().isoformat(),"queries":1,"trust":trust,"coverage":coverage} for created_at,trust,coverage in query_rows]}

@app.get("/api/search")
def global_search(q:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=q.strip()
    if len(q)<2:return []
    escaped=q.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
    pattern=f"%{escaped}%"
    out=[]
    remaining=50
    docs=(db.query(Document.id,Document.filename,Document.title).filter(Document.owner_id==u.id,Document.filename.ilike(pattern,escape="\\")|Document.title.ilike(pattern,escape="\\")|Document.source.ilike(pattern,escape="\\")).limit(remaining).all())
    out.extend({"type":"document","id":row.id,"title":row.filename,"text":row.title} for row in docs)
    remaining=50-len(out)
    if remaining:
        rows=db.query(Query.id,Query.question,Query.status).filter(Query.owner_id==u.id,Query.question.ilike(pattern,escape="\\")).limit(remaining).all()
        out.extend({"type":"query","id":row.id,"title":row.question,"text":row.status} for row in rows)
    remaining=50-len(out)
    if remaining:
        rows=db.query(Claim.id,Claim.text,Claim.status).join(Query).filter(Query.owner_id==u.id,Claim.text.ilike(pattern,escape="\\")).limit(remaining).all()
        out.extend({"type":"claim","id":row.id,"title":row.text,"text":row.status} for row in rows)
    remaining=50-len(out)
    if remaining:
        rows=db.query(Evidence.id,Evidence.snippet,Evidence.page).join(Query).filter(Query.owner_id==u.id,Evidence.snippet.ilike(pattern,escape="\\")).limit(remaining).all()
        out.extend({"type":"evidence","id":row.id,"title":row.snippet[:120],"text":f"Page {row.page}"} for row in rows)
    remaining=50-len(out)
    if remaining:
        rows=db.query(KnowledgeGap.id,KnowledgeGap.topic,KnowledgeGap.reason,KnowledgeGap.representative_query).filter(KnowledgeGap.owner_id==u.id,KnowledgeGap.topic.ilike(pattern,escape="\\")|KnowledgeGap.reason.ilike(pattern,escape="\\")|KnowledgeGap.representative_query.ilike(pattern,escape="\\")).limit(remaining).all()
        out.extend({"type":"knowledge-gap","id":row.id,"title":row.topic,"text":row.representative_query} for row in rows)
    return out

@app.websocket("/api/events")
async def events(ws:WebSocket,token:str):
    from jose import jwt,JWTError
    try:
        payload=jwt.decode(token,settings.jwt_secret,algorithms=["HS256"]); uid=payload["sub"]
    except Exception:
        await ws.close(code=1008); return
    await bus.subscribe(uid,ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: bus.unsubscribe(uid,ws)
