export interface DemoResponse {
  message: string;
}

export interface DocumentRecord {
  id: string;
  filename: string;
  title: string;
  type: string;
  size: number;
  source: string;
  authority: number;
  version: string;
  createdDate?: string;
  effectiveDate?: string;
  expiryDate?: string;
  text: string;
  chunks: number;
  createdAt: string;
}

export interface EvidenceGraphNode {
  id: string;
  kind: "QUERY" | "CLAIM" | "EVIDENCE" | "DOCUMENT" | "VERSION";
  label: string;
  detail: string;
  source?: string;
  documentId?: string;
}

export interface EvidenceGraphEdge {
  id: string;
  from: string;
  to: string;
  label: "SUPPORTS" | "CONTRADICTS" | "SUPERSEDES" | "GENUINE_CONFLICT" | "RELATED" | "DERIVED_FROM";
}

export interface EvidenceGraphResponse {
  queryId: string;
  query: string;
  nodes: EvidenceGraphNode[];
  edges: EvidenceGraphEdge[];
  matchedDocuments: number;
  generatedAt: string;
}

export interface QueryAnalysisResponse {
  queryId: string;
  question: string;
  intent: string;
  topic: string;
  keywords: string[];
  reformulations: string[];
  status: "ANSWERABLE" | "PARTIALLY_ANSWERABLE" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE" | "OUT_OF_SCOPE" | "KNOWLEDGE_GAP";
  answer: string;
  coverage: number;
  claims: Array<{ id: string; text: string; status: "SUPPORTED" | "PARTIALLY_SUPPORTED" | "CONTRADICTED" | "UNVERIFIED"; confidence: number; reason: string; evidence: Array<{ evidenceId: string; documentId: string; document: string; chunkId: string; page: number; version: string; effectiveDate?: string; temporalStatus: string; relation: string }> }>;
  evidence: Array<{ id: string; document: string; version: string; source: string; page: number; snippet: string; relevance: number; semanticScore: number; bm25Score: number; hybridScore: number; rerankScore: number; temporalStatus: string; documentId: string; chunkId: string }>;
  missingInformation: string[];
  trust: { score: number; evidenceStrength: number; sourceAuthority: number; recency: number; agreement: number; contradictionPenalty: number; unverifiedPenalty: number; explanation: string };
  temporalSummary: { requestedDate?: string | null; statuses?: Record<string, number>; relations?: string[] };
  knowledgeGap: { detected: boolean; topic: string; reason: string };
  generatedAt: string;
}
