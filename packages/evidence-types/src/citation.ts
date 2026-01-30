/**
 * Citation-related types
 */

export interface CitationExtractRequest {
  text: string;
  extractionSchema?: string;
}

export interface Citation {
  title: string;
  authors: string[];
  year?: number;
  venue?: string;
  doi?: string;
  rawText?: string;
}

export interface CitationExtractResponse {
  citations: Citation[];
  total: number;
}

export interface EvidencePanelSettings {
  autoSearch: boolean;
  searchDelay: number;
  topK: number;
  threshold: number;
  panelWidth: number;
}

export interface EvidencePanelState {
  isOpen: boolean;
  isLoading: boolean;
  query: string;
  results: import('./evidence').EvidenceResult[];
  error?: string;
  settings: EvidencePanelSettings;
}
