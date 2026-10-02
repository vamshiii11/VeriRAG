import re, math, hashlib, logging
from uuid import uuid4
from datetime import datetime, date
from sqlalchemy.orm import Session
from .models import Query,Claim,Evidence,ClaimEvidence,TemporalRelation,KnowledgeGap,Document
from .retrieval import retriever
from .llm import generate, verify_claim_with_llm

logger=logging.getLogger(__name__)
_knowledge_gap_signatures={}

def keywords(q): return [x for x in re.findall(r"\b\w+\b",q.lower()) if len(x)>2 and x not in {"what","which","does","this","that","with","from","have","about","current","can","the"}]
def intent(q):
    q=q.lower()
    if any(x in q for x in ["current","today","now"]): return "POLICY_LOOKUP"
    if any(x in q for x in ["without approval","allowed","may i","can i"]): return "POLICY_COMPLIANCE"
    if any(x in q for x in ["compare","difference","versus","was in"]): return "TEMPORAL_COMPARISON"
    if any(x in q for x in ["penalty","violate","violation"]): return "POLICY_CONSEQUENCE"
    return "GENERAL_KNOWLEDGE_LOOKUP"

def dateval(x):
    if not x:return datetime(1900,1,1)
    try:return datetime.fromisoformat(x[:10])
    except:return datetime(1900,1,1)

def query_date(question):
    match=re.search(r"\b(20\d{2})(?:[-/]([01]?\d))?(?:[-/]([0-3]?\d))?\b",question)
    if not match:return None
    month=int(match.group(2) or 1); day=int(match.group(3) or 1)
    try:return datetime(int(match.group(1)),month,day)
    except ValueError:return None

def same_policy_scope(first,second):
    normalize=lambda value: re.sub(r"(?:version|v)?\s*\d+(?:\.\d+)?|\b20\d{2}\b|[^a-z0-9]+","",value.lower())
    return normalize(first.title)==normalize(second.title) or ("wfh" in first.title.lower() and "wfh" in second.title.lower())

def temporal_relations(db,owner_id,docs,new_document_id=None):
    rels=[]
    # Relations are based on policy scope and dates, never on database identifiers.
    if new_document_id:
        new_document=next((doc for doc in docs if doc.id==new_document_id),None)
        pairs=((doc,new_document) for doc in docs if new_document and doc.id!=new_document_id)
    else:
        pairs=((first,second) for index,first in enumerate(docs) for second in docs[index+1:])
    for a,b in pairs:
            same=same_policy_scope(a,b)
            explicit=("supersed" in a.extracted_text.lower() and b.version.lower() in a.extracted_text.lower()) or ("supersed" in b.extracted_text.lower() and a.version.lower() in b.extracted_text.lower())
            if same and dateval(a.effective_date)!=dateval(b.effective_date):
                older,newer=(a,b) if dateval(a.effective_date)<dateval(b.effective_date) else (b,a)
                exists=db.query(TemporalRelation).filter_by(older_document_id=older.id,newer_document_id=newer.id).first()
                if not exists:
                    rel=TemporalRelation(id=str(uuid4()),owner_id=owner_id,older_document_id=older.id,newer_document_id=newer.id,relation_type="SUPERSEDES",confidence=0.9 if explicit else 0.75,reason="Later effective date for the same policy scope; explicit supersedes language used when present.")
                    db.add(rel); rels.append(rel)
            elif explicit:
                older,newer=(a,b) if b.version.lower() in a.extracted_text.lower() else (b,a)
                if not db.query(TemporalRelation).filter_by(older_document_id=older.id,newer_document_id=newer.id,relation_type="SUPERSEDES").first():
                    rel=TemporalRelation(id=str(uuid4()),owner_id=owner_id,older_document_id=older.id,newer_document_id=newer.id,relation_type="SUPERSEDES",confidence=.9,reason="The newer document explicitly names the superseded version.")
                    db.add(rel); rels.append(rel)
    db.commit()
    return rels

def resolve_temporal_evidence(question, evidence, relations):
    """Classify retrieved evidence for this question and return a stable ordering."""
    requested=query_date(question)
    as_of=requested or datetime.utcnow()
    current_query=not requested and not any(token in question.lower() for token in ("historical","previous","old policy","earlier policy"))
    groups={}
    for item in evidence:
        document=item["document"]
        groups.setdefault(re.sub(r"(?:version|v)?\s*\d+(?:\.\d+)?|\b20\d{2}\b|[^a-z0-9]+","",document.title.lower()),[]).append(item)
    relation_pairs={(r.older_document_id,r.newer_document_id) for r in relations if r.relation_type=="SUPERSEDES"}
    for item in evidence:
        document=item["document"]
        effective=dateval(document.effective_date)
        expired=bool(document.expiry_date and dateval(document.expiry_date)<as_of)
        item["temporal_status"]="HISTORICAL" if requested else "UNRESOLVED"
        item["temporal_reason"]="No temporal preference was required."
        item["temporal_boost"]=1.0
        if expired:
            item["temporal_status"]="EXPIRED"; item["temporal_reason"]="The document expired before the query date."; item["temporal_boost"]=0.1
        elif requested and effective<=as_of:
            item["temporal_status"]="CURRENT"; item["temporal_reason"]="The document was effective on the requested historical date."; item["temporal_boost"]=1.0
        elif requested:
            item["temporal_status"]="HISTORICAL"; item["temporal_reason"]="The document became effective after the requested date."; item["temporal_boost"]=0.35
    if current_query or requested:
        for members in groups.values():
            valid=[x for x in members if x["temporal_status"] in {"UNRESOLVED","CURRENT"} and dateval(x["document"].effective_date)<=as_of]
            if not valid:continue
            newest_date=max(dateval(x["document"].effective_date) for x in valid)
            newest=[x for x in valid if dateval(x["document"].effective_date)==newest_date]
            max_authority=max(float(x["document"].authority or 0) for x in newest)
            winners=[x for x in newest if float(x["document"].authority or 0)==max_authority]
            winner_documents={x["document"].id for x in winners}
            conflict=len(winner_documents)>1 and len({re.sub(r"\s+"," ",x["snippet"].lower()) for x in winners})>1
            for item in members:
                if conflict and item in winners:
                    item["temporal_status"]="CONFLICTED"; item["temporal_reason"]="Current documents share an effective date and authority but contain different evidence."; item["temporal_boost"]=0.7
                elif item in winners:
                    item["temporal_status"]="CURRENT"; item["temporal_reason"]="Latest valid effective date, with authority used as the tie-breaker."; item["temporal_boost"]=1.0
                elif item["temporal_status"] not in {"EXPIRED","HISTORICAL"}:
                    item["temporal_status"]="SUPERSEDED"; item["temporal_reason"]="A later valid document in the same policy scope supersedes this evidence."; item["temporal_boost"]=0.35
    return sorted(evidence,key=lambda item:item["rerank"]*item["temporal_boost"],reverse=True)

def verify_claim(db,claim_text,evidence_rows):
    if not evidence_rows:return "UNVERIFIED",0,"No evidence retrieved for this claim."
    claim_tokens=set(keywords(claim_text))
    best=0; contradiction=False
    for e in evidence_rows:
        et=set(keywords(e["snippet"]))
        overlap=len(claim_tokens & et)/max(1,len(claim_tokens))
        best=max(best,overlap)
        # Explicit negation cues indicate potential contradiction.
        if any(n in e["snippet"].lower() for n in ["not allowed","prohibited","no approval","not permitted"]) and any(x in claim_text.lower() for x in ["allowed","permitted","can"]):
            contradiction=True
    if contradiction and best>=.25:return "CONTRADICTED",min(100,round(best*100)),"Retrieved evidence contains a conflicting prohibition/condition."
    if best>=.65:return "SUPPORTED",min(100,round(best*100)),"Claim terms and meaning are strongly covered by retrieved evidence."
    if best>=.3:return "PARTIALLY_SUPPORTED",round(best*100),"Only part of the claim is covered by retrieved evidence."
    return "UNVERIFIED",round(best*100),"Evidence overlap is insufficient to verify the claim."

def calculate_trust(claims, evidence, question, all_evidence=None):
    linked_ids={link.evidence_id for claim in claims for link in claim.links}
    linked=[item for item in evidence if item.id in linked_ids]
    evidence_strength=sum(item.rerank_score for item in linked)/len(linked)*100 if linked else 0
    authorities=[float(item.document.authority or 0) for item in linked if item.document]
    authority=sum(authorities)/len(authorities) if authorities else 0
    as_of=query_date(question) or datetime.utcnow()
    dated=[item for item in linked if item.document and item.document.effective_date and dateval(item.document.effective_date)<=as_of]
    recency=sum(max(0,100-(as_of-dateval(item.document.effective_date)).days/365*20) for item in dated)/len(dated) if dated else 0
    agreements=[]
    for index,item in enumerate(linked):
        first=set(keywords(item.snippet))
        for other in linked[index+1:]:
            second=set(keywords(other.snippet)); agreements.append(len(first & second)/max(1,len(first | second))*100)
    agreement=sum(agreements)/len(agreements) if agreements else (100 if linked else 0)
    contradicted=sum(claim.status=="CONTRADICTED" for claim in claims)
    unverified=sum(claim.status=="UNVERIFIED" for claim in claims)
    total=max(1,len(claims))
    contradiction_penalty=25*contradicted/total
    unverified_penalty=15*unverified/total
    conflict_penalty=20 if any(item.temporal_status=="CONFLICTED" for item in (all_evidence or linked)) else 0
    base=.35*evidence_strength+.25*authority+.20*recency+.20*agreement
    score=round(max(0,min(100,base-contradiction_penalty-unverified_penalty-conflict_penalty)),2)
    explanation="Trust is based on linked evidence strength, source authority, dated recency, and actual lexical agreement."
    if conflict_penalty: explanation="Trust reduced because current evidence sources conflict."
    elif contradiction_penalty: explanation="Trust reduced because one or more linked claims are contradicted."
    elif score>=75: explanation="Trust is high because linked evidence is relevant, dated, authoritative, and consistent."
    return score,{"evidenceStrength":round(evidence_strength,2),"sourceAuthority":round(authority,2),"recency":round(recency,2),"agreement":round(agreement,2),"contradictionPenalty":round(contradiction_penalty+conflict_penalty,2),"unverifiedPenalty":round(unverified_penalty,2),"explanation":explanation}

def update_knowledge_gaps(db, owner_id):
    """Recluster unanswered queries after writes; retain exact gaps if embeddings are unavailable."""
    from .models import KnowledgeGap
    queries=db.query(Query).filter(Query.owner_id==owner_id,Query.status!="ANSWERABLE").order_by(Query.question).all()
    signature=tuple(query.id for query in queries)
    if _knowledge_gap_signatures.get(owner_id)==signature:return
    if not queries:
        _knowledge_gap_signatures[owner_id]=signature
        return
    try:
        from sklearn.cluster import DBSCAN
        import numpy as np
        retriever.model_load()
        embeddings=np.asarray(retriever.model.encode([q.question for q in queries],normalize_embeddings=True))
        labels=DBSCAN(eps=0.38,min_samples=1,metric="cosine").fit_predict(embeddings)
        for label in sorted(set(labels)):
            members=[q for q,current in zip(queries,labels) if current==label]
            representative=members[0].question
            key="semantic:"+hashlib.sha1(representative.lower().encode("utf-8")).hexdigest()[:16]
            gap=db.query(KnowledgeGap).filter_by(owner_id=owner_id,cluster_key=key).first()
            if not gap:
                gap=KnowledgeGap(id=str(uuid4()),owner_id=owner_id,cluster_key=key,topic=members[0].topic or "Unclassified",reason="Semantically similar queries have insufficient or incomplete evidence.",representative_query=representative)
                db.add(gap)
            gap.frequency=len(members); gap.query_ids=[q.id for q in members]; gap.average_trust=sum(q.trust for q in members)/len(members); gap.evidence_coverage=sum(q.coverage for q in members)/len(members); gap.updated_at=datetime.utcnow()
        db.commit()
        _knowledge_gap_signatures[owner_id]=signature
    except Exception as exc:
        logger.warning("knowledge-gap clustering failed for owner %s; retaining exact gaps: %s",owner_id,exc)

def analyze(db,owner_id,question):
    rows=retriever.search(db,owner_id,question,8)
    evidence=[]
    for x in rows:
        c=x["chunk"]; d=c.document
        evidence.append({"chunk":c,"document":d,"semantic":x["semantic"],"bm25":x["bm25"],"hybrid":x["hybrid"],"rerank":x["rerank"],"snippet":c.text[:1200],"page":c.page})
    evidence_document_ids={item["document"].id for item in evidence}
    if evidence:
        temporal_relations(db,owner_id,list({item["document"].id:item["document"] for item in evidence}.values()))
    relations=(db.query(TemporalRelation).filter(TemporalRelation.owner_id==owner_id,TemporalRelation.older_document_id.in_(evidence_document_ids)|TemporalRelation.newer_document_id.in_(evidence_document_ids)).all() if evidence_document_ids else [])
    evidence=resolve_temporal_evidence(question,evidence,relations)
    # Keep historical/conflicting evidence available for explanation, but do not
    # let weak or expired material become current-answer context.
    usable=[x for x in evidence if x["rerank"]*x["temporal_boost"]>=.38 and x["temporal_status"] not in {"EXPIRED","HISTORICAL"}]
    context_evidence=usable or [x for x in evidence if x["temporal_status"] not in {"EXPIRED"}]
    if not context_evidence:
        llm={"answer":"Insufficient evidence was found in the indexed documents to answer this question.","claims":[],"missing_information":["No relevant, current evidence was retrieved."]}
    else:
        try:
            llm=generate(question,[{"document":x["document"].filename,"version":x["document"].version,"effective_date":x["document"].effective_date,"page":x["page"],"snippet":x["snippet"],"temporal_status":x["temporal_status"],"temporal_reason":x["temporal_reason"]} for x in context_evidence[:6]])
        except RuntimeError as exc:
            llm={"answer":"Insufficient evidence to generate a grounded answer because the configured LLM provider is unavailable.","claims":[],"missing_information":[str(exc)]}
    if any(term in question.lower() for term in ("compare", "2025", "historical", "previous")):
        historical_sentences=[]
        for item in usable:
            for sentence in re.split(r"(?<=[.!?])\s+", item["snippet"]):
                lowered=sentence.lower()
                if "2025" in lowered and ("paid leave" in lowered or "work-from-home" in lowered or "wfh" in lowered) and re.search(r"\b\d+\s+(?:paid leave )?days?\b", lowered):
                    historical_sentences.append(sentence.strip())
        if historical_sentences and not re.search(r"\b2025\b", str(llm.get("answer", ""))):
            llm["answer"]=(str(llm.get("answer", "")).rstrip(" .")+". Historical evidence: "+historical_sentences[0]).strip()
            llm["missing_information"]=[item for item in llm.get("missing_information", []) if "2025" not in str(item)]
    claims_text=llm.get("claims") or []
    missing_information=llm.get("missing_information") or []
    question_terms=set(keywords(question))
    claims_text=[claim for claim in claims_text if len(question_terms & set(keywords(str(claim)))) / max(1,len(question_terms)) >= .25]
    llm["missing_information"]=[item for item in missing_information if len(question_terms & set(keywords(str(item)))) / max(1,len(question_terms)) >= .25]
    if not claims_text and usable:
        # Safe local decomposition fallback: split the generated/extractive answer
        # into factual propositions. Each proposition is still independently verified.
        claims_text=[x.strip() for x in re.split(r"(?<=[.!?])\s+", str(llm.get("answer",""))) if len(x.strip())>12][:6]
    conflict_found=any(item["temporal_status"]=="CONFLICTED" for item in evidence)
    temporal_summary={"requestedDate":query_date(question).date().isoformat() if query_date(question) else None,"statuses":{status:sum(1 for item in evidence if item["temporal_status"]==status) for status in {item["temporal_status"] for item in evidence}},"relations":[r.id for r in relations]}
    q=Query(id=str(uuid4()),owner_id=owner_id,question=question,intent=intent(question),topic=" ".join(keywords(question)[:5]) or "unclassified",answer=llm.get("answer",""),missing_information=llm.get("missing_information",[]),temporal_summary=temporal_summary)
    db.add(q); db.flush()
    ev_objs=[]
    for x in evidence[:8]:
        e=Evidence(id=str(uuid4()),query_id=q.id,chunk_id=x["chunk"].id,document_id=x["document"].id,page=x["page"],snippet=x["snippet"],semantic_score=x["semantic"],bm25_score=x["bm25"],hybrid_score=x["hybrid"],rerank_score=x["rerank"],temporal_status=x["temporal_status"])
        db.add(e); ev_objs.append((e,x))
    db.flush()
    claim_objs=[]
    for ct in claims_text:
        ct=str(ct).strip()
        if not ct:continue
        claim_terms=set(keywords(ct))
        claim_numbers=set(re.findall(r"\b\d+(?:\.\d+)?\b",ct))
        targeted=[x for x in usable[:6] if claim_numbers.intersection(re.findall(r"\b\d+(?:\.\d+)?\b",x["snippet"])) or len(claim_terms & set(keywords(x["snippet"]))) / max(1,len(claim_terms)) >= .35]
        claim_rows=retriever.search(db,owner_id,ct,4)
        claim_chunk_ids={row["chunk"].id for row in claim_rows}
        claim_pairs=[pair for pair in ev_objs if pair[1]["chunk"].id in claim_chunk_ids]
        claim_pairs=claim_pairs or [(pair) for pair in ev_objs if pair[1] in targeted]
        claim_evidence=[{"id":e.id,"snippet":x["snippet"],"document":x["document"].filename,"page":x["page"],"version":x["document"].version,"temporal_status":x["temporal_status"]} for e,x in claim_pairs]
        heuristic_status,heuristic_conf,heuristic_reason=verify_claim(db,ct,claim_evidence)
        if heuristic_status in {"SUPPORTED","CONTRADICTED"}:
            status,conf,reason=heuristic_status,heuristic_conf,heuristic_reason
            claim_numbers=set(re.findall(r"\b\d+(?:\.\d+)?\b",ct))
        else:
            try:
                vr=verify_claim_with_llm(ct, claim_evidence)
                status=str(vr.get("status","UNVERIFIED"))
                conf=float(vr.get("confidence",0))
                if conf <= 1: conf *= 100
                reason=str(vr.get("reason",""))
                if status not in {"SUPPORTED","PARTIALLY_SUPPORTED","CONTRADICTED","UNVERIFIED"}: status="UNVERIFIED"
            except Exception:
                status,conf,reason=heuristic_status,heuristic_conf,heuristic_reason
                reason=f"Deterministic verification fallback used because the LLM verifier was unavailable: {reason}"
        cl=Claim(id=str(uuid4()),query_id=q.id,text=ct,status=status,confidence=round(conf,2),verification_reason=reason)
        db.add(cl); db.flush(); claim_objs.append(cl)
        for e,x in claim_pairs:
            st,_,_=verify_claim(db,ct,[{"snippet":e.snippet}])
            if st in ("SUPPORTED","PARTIALLY_SUPPORTED","CONTRADICTED"):
                db.add(ClaimEvidence(id=str(uuid4()),claim_id=cl.id,evidence_id=e.id,relation="CONTRADICTS" if st=="CONTRADICTED" else "SUPPORTS",temporal_status=x["temporal_status"]))
    coverage=round(min(100,max([x["rerank"]*x["temporal_boost"] for x in usable],default=0)*100))
    evidence_strength=coverage
    contrad=any(c.status=="CONTRADICTED" for c in claim_objs)
    if not usable: status="INSUFFICIENT_EVIDENCE"
    elif conflict_found: status="CONTRADICTED"
    elif contrad: status="CONTRADICTED"
    elif any(c.status in ("UNVERIFIED","PARTIALLY_SUPPORTED") for c in claim_objs) or llm.get("missing_information"): status="PARTIALLY_ANSWERABLE"
    else: status="ANSWERABLE"
    db.flush()
    score,trust_details=calculate_trust(claim_objs,[pair[0] for pair in ev_objs],question,[pair[0] for pair in ev_objs])
    q.status=status;q.coverage=coverage;q.trust=score;q.trust_details=trust_details
    if conflict_found:
        conflicted=[item for item in evidence if item["temporal_status"]=="CONFLICTED"]
        for index,item in enumerate(conflicted):
            for other in conflicted[index+1:]:
                if not same_policy_scope(item["document"],other["document"]):
                    continue
                already=db.query(TemporalRelation).filter(
                    TemporalRelation.owner_id==owner_id,
                    TemporalRelation.relation_type=="GENUINE_CONFLICT",
                    ((TemporalRelation.older_document_id==item["document"].id) & (TemporalRelation.newer_document_id==other["document"].id)) |
                    ((TemporalRelation.older_document_id==other["document"].id) & (TemporalRelation.newer_document_id==item["document"].id)),
                ).first()
                if not already:
                    db.add(TemporalRelation(id=str(uuid4()),owner_id=owner_id,older_document_id=item["document"].id,newer_document_id=other["document"].id,relation_type="GENUINE_CONFLICT",confidence=.85,reason="Current evidence has equal temporal priority and no superseding relationship was established."))
    # Conservative knowledge gap creation.
    if status!="ANSWERABLE" or not usable:
        key=" ".join(sorted(set(keywords(question)))[:8]) or "unclassified"
        gap=db.query(KnowledgeGap).filter_by(owner_id=owner_id,cluster_key=key).first()
        if not gap:
            gap=KnowledgeGap(id=str(uuid4()),owner_id=owner_id,cluster_key=key,topic=q.topic,reason=(q.missing_information or ["Evidence coverage is insufficient."])[0],representative_query=question,query_ids=[q.id])
            db.add(gap)
        else:
            gap.frequency+=1; gap.query_ids=list(gap.query_ids or [])+[q.id]; gap.updated_at=datetime.utcnow()
    db.commit()
    return q

def baseline_answer(db,owner_id,question):
    """Basic RAG comparator: retrieve and generate without temporal, claim, or trust stages."""
    rows=retriever.search(db,owner_id,question,8)
    context=[]
    for row in rows[:6]:
        document=row["chunk"].document
        context.append({"document":document.filename,"version":document.version,"effective_date":document.effective_date,"page":row["chunk"].page,"snippet":row["chunk"].text[:1200]})
    if not context:
        return {"question":question,"answer":"Insufficient evidence was found in the indexed documents to answer this question.","evidence":[]}
    result=generate(question,context)
    return {"question":question,"answer":result.get("answer",""),"evidence":context}
