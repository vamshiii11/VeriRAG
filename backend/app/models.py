from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, Boolean, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from .db import Base

class User(Base):
    __tablename__="users"
    id=Column(String, primary_key=True)
    email=Column(String, unique=True, index=True, nullable=False)
    password_hash=Column(String, nullable=False)
    created_at=Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__="documents"
    id=Column(String, primary_key=True)
    owner_id=Column(String, ForeignKey("users.id"), index=True, nullable=False)
    filename=Column(String, nullable=False)
    title=Column(String, nullable=False)
    mime_type=Column(String, default="")
    size=Column(Integer, default=0)
    source=Column(String, default="User upload")
    authority=Column(Float, default=50)
    version=Column(String, default="unversioned")
    created_date=Column(String, nullable=True)
    effective_date=Column(String, nullable=True)
    expiry_date=Column(String, nullable=True)
    metadata_source=Column(String, default="manual_or_inferred")
    metadata_uncertain=Column(Boolean, default=False)
    supersedes_document_id=Column(String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    storage_key=Column(String, nullable=False)
    content_hash=Column(String(64), nullable=True)
    extracted_text=Column(Text, default="")
    extraction_method=Column(String, default="text")
    page_count=Column(Integer, default=0)
    status=Column(String, default="PROCESSING")
    created_at=Column(DateTime, default=datetime.utcnow)
    updated_at=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    chunks=relationship("Chunk", cascade="all, delete-orphan", back_populates="document")
    relations_from=relationship("TemporalRelation", foreign_keys="TemporalRelation.older_document_id", cascade="all, delete-orphan")
    relations_to=relationship("TemporalRelation", foreign_keys="TemporalRelation.newer_document_id", cascade="all, delete-orphan")
    __table_args__=(Index("ix_documents_owner_content_hash", "owner_id", "content_hash"),Index("ix_documents_owner_created_at", "owner_id", "created_at"))

class Chunk(Base):
    __tablename__="chunks"
    id=Column(String, primary_key=True)
    document_id=Column(String, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page=Column(Integer, default=0)
    text=Column(Text, nullable=False)
    token_count=Column(Integer, default=0)
    faiss_row=Column(Integer, nullable=True)
    document=relationship("Document", back_populates="chunks")

class Query(Base):
    __tablename__="queries"
    id=Column(String, primary_key=True)
    owner_id=Column(String, ForeignKey("users.id"), index=True, nullable=False)
    question=Column(Text, nullable=False)
    intent=Column(String, default="")
    topic=Column(String, default="")
    status=Column(String, default="INSUFFICIENT_EVIDENCE")
    coverage=Column(Float, default=0)
    trust=Column(Float, default=0)
    answer=Column(Text, default="")
    missing_information=Column(JSON, default=list)
    trust_details=Column(JSON, default=dict)
    temporal_summary=Column(JSON, default=dict)
    created_at=Column(DateTime, default=datetime.utcnow)
    claims=relationship("Claim", cascade="all, delete-orphan", back_populates="query")
    evidence=relationship("Evidence", cascade="all, delete-orphan", back_populates="query")
    __table_args__=(Index("ix_queries_owner_created_at", "owner_id", "created_at"),)

class Claim(Base):
    __tablename__="claims"
    id=Column(String, primary_key=True)
    query_id=Column(String, ForeignKey("queries.id", ondelete="CASCADE"), index=True)
    text=Column(Text, nullable=False)
    status=Column(String, default="UNVERIFIED")
    confidence=Column(Float, default=0)
    verification_reason=Column(Text, default="")
    query=relationship("Query", back_populates="claims")
    links=relationship("ClaimEvidence", cascade="all, delete-orphan", back_populates="claim")

class Evidence(Base):
    __tablename__="evidence"
    id=Column(String, primary_key=True)
    query_id=Column(String, ForeignKey("queries.id", ondelete="CASCADE"), index=True)
    chunk_id=Column(String, ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True)
    document_id=Column(String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    page=Column(Integer, default=0)
    snippet=Column(Text, nullable=False)
    semantic_score=Column(Float, default=0)
    bm25_score=Column(Float, default=0)
    hybrid_score=Column(Float, default=0)
    rerank_score=Column(Float, default=0)
    evidence_type=Column(String, default="RETRIEVED")
    temporal_status=Column(String, default="UNRESOLVED")
    query=relationship("Query", back_populates="evidence")
    document=relationship("Document", foreign_keys=[document_id])
    links=relationship("ClaimEvidence", cascade="all, delete-orphan", back_populates="evidence")

class ClaimEvidence(Base):
    __tablename__="claim_evidence"
    id=Column(String, primary_key=True)
    claim_id=Column(String, ForeignKey("claims.id", ondelete="CASCADE"))
    evidence_id=Column(String, ForeignKey("evidence.id", ondelete="CASCADE"))
    relation=Column(String, default="SUPPORTS")
    temporal_status=Column(String, default="UNRESOLVED")
    claim=relationship("Claim", back_populates="links")
    evidence=relationship("Evidence", back_populates="links")
    __table_args__=(UniqueConstraint("claim_id","evidence_id","relation"),)

class TemporalRelation(Base):
    __tablename__="temporal_relations"
    id=Column(String, primary_key=True)
    owner_id=Column(String, ForeignKey("users.id"), index=True)
    older_document_id=Column(String, ForeignKey("documents.id", ondelete="CASCADE"))
    newer_document_id=Column(String, ForeignKey("documents.id", ondelete="CASCADE"))
    relation_type=Column(String, nullable=False)
    confidence=Column(Float, default=0)
    reason=Column(Text, default="")
    created_at=Column(DateTime, default=datetime.utcnow)

class KnowledgeGap(Base):
    __tablename__="knowledge_gaps"
    id=Column(String, primary_key=True)
    owner_id=Column(String, ForeignKey("users.id"), index=True)
    cluster_key=Column(String, index=True)
    topic=Column(String)
    reason=Column(Text)
    frequency=Column(Integer, default=1)
    average_trust=Column(Float, default=0)
    evidence_coverage=Column(Float, default=0)
    representative_query=Column(Text)
    query_ids=Column(JSON, default=list)
    created_at=Column(DateTime, default=datetime.utcnow)
    updated_at=Column(DateTime, default=datetime.utcnow)
