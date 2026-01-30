/**
 * Evidence-related types
 */

export interface EvidenceSearchRequest {
  query: string;
  topK?: number;
  threshold?: number;
  documentIds?: string[];
}

export interface EvidenceResult {
  documentId: string;
  chunkId: string;
  text: string;
  page?: number;
  score: number;
  metadata?: Record<string, string | number | boolean>;
}

export interface EvidenceSearchResponse {
  results: EvidenceResult[];
  query: string;
  total: number;
}

export interface DocumentParseResponse {
  filename: string;
  pages: number;
  content: string;
  metadata?: Record<string, string | number | boolean>;
}

export interface DocumentIndexRequest {
  documentId: string;
  content: string;
  metadata?: Record<string, string | number | boolean>;
}

export interface DocumentIndexResponse {
  documentId: string;
  chunkCount: number;
  status: 'indexed' | 'error';
}

export interface DocumentChunk {
  chunkId: string;
  text: string;
  page?: number;
  startIdx: number;
  endIdx: number;
}

export interface DocumentChunksResponse {
  documentId: string;
  chunks: DocumentChunk[];
  total: number;
}
