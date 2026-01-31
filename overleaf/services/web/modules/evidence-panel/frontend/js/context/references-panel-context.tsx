import React, {
  createContext,
  useContext,
  useCallback,
  useMemo,
  useState,
  useEffect,
  useRef,
  FC,
  ReactNode,
} from 'react'
import { useBibEntries, BibEntry } from '../hooks/use-bib-entries'
import { useReferencesContext } from '@/features/ide-react/context/references-context'

declare global {
  interface Window {
    __EVIDENCE_API_URL__?: string
  }
}

const API_BASE_URL = window.__EVIDENCE_API_URL__ || 'http://localhost:8000'
const POLL_INTERVAL = 2000

export type IndexStatus = 'none' | 'indexing' | 'indexed' | 'error'

export interface ReferencePaper {
  citeKey: string
  title?: string
  authors?: string
  year?: string
  // PDF status
  hasPdf: boolean
  pdfFileId?: string
  pdfFilename?: string
  // Indexing status
  indexStatus: IndexStatus
  documentId?: string
  chunkCount?: number
  error?: string
}

interface IndexedDocumentResponse {
  document_id: string
  title: string | null
  authors: string | null
  chunk_count: number
  indexed_at: string | null
}

interface IndexedDocument {
  documentId: string
  title: string
  status: 'processing' | 'indexed' | 'error'
  chunkCount?: number
  message?: string
}

export interface ReferencesPanelContextValue {
  papers: ReferencePaper[]
  isLoading: boolean
  error: string | null
  selectedDocId: string | null
  setSelectedDocId: (docId: string | null) => void
  refreshAll: () => Promise<void>
  indexPaper: (citeKey: string, file: File) => Promise<void>
  reindexPaper: (documentId: string) => Promise<void>
  removePaper: (documentId: string) => Promise<void>
  uploadPdf: (file: File) => Promise<string | null>
}

export const ReferencesPanelContext = createContext<
  ReferencesPanelContextValue | undefined
>(undefined)

interface ReferencesPanelProviderProps {
  children: ReactNode
}

export const ReferencesPanelProvider: FC<ReferencesPanelProviderProps> = ({
  children,
}) => {
  // Get reference keys from Overleaf's bib parser
  const { referenceKeys, indexAllReferences } = useReferencesContext()

  // Get bib entries with PDF matching from file tree
  const { bibEntries, refresh: refreshBibEntries } = useBibEntries(referenceKeys)

  // State for indexed documents from API
  const [indexedDocs, setIndexedDocs] = useState<IndexedDocument[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)

  // Polling refs
  const pollingIntervals = useRef<Map<string, NodeJS.Timeout>>(new Map())

  // Fetch indexed documents from API
  const fetchIndexedDocuments = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/documents`)
      if (!response.ok) {
        throw new Error(`Failed to fetch documents: ${response.statusText}`)
      }

      const data = await response.json()
      if (!Array.isArray(data?.documents)) {
        throw new Error('Invalid response format: documents array expected')
      }
      const docs: IndexedDocument[] = data.documents.map(
        (doc: IndexedDocumentResponse) => ({
          documentId: doc.document_id,
          title: doc.title || doc.document_id,
          status: 'indexed' as const,
          chunkCount: doc.chunk_count,
        })
      )

      setIndexedDocs(docs)
      setError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch documents'
      setError(message)
    }
  }, [])

  // Refresh everything
  const refreshAll = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Refresh Overleaf's references index
      await indexAllReferences(false)
      // Refresh our bib entries
      refreshBibEntries()
      // Fetch indexed docs from API
      await fetchIndexedDocuments()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Refresh failed'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [indexAllReferences, refreshBibEntries, fetchIndexedDocuments])

  // Initial load
  useEffect(() => {
    const init = async () => {
      setIsLoading(true)
      await fetchIndexedDocuments()
      setIsLoading(false)
    }
    init()
  }, [fetchIndexedDocuments])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      pollingIntervals.current.forEach(interval => clearInterval(interval))
      pollingIntervals.current.clear()
    }
  }, [])

  // Poll document status
  const pollDocumentStatus = useCallback(
    async (documentId: string): Promise<void> => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/documents/${documentId}/status`
        )

        if (!response.ok) return

        const data = await response.json()

        if (data.status === 'indexed' || data.status === 'error') {
          // Stop polling
          const interval = pollingIntervals.current.get(documentId)
          if (interval) {
            clearInterval(interval)
            pollingIntervals.current.delete(documentId)
          }

          // Update state
          setIndexedDocs(prev =>
            prev.map(doc =>
              doc.documentId === documentId
                ? {
                    ...doc,
                    status: data.status,
                    chunkCount: data.chunk_count,
                    message: data.message,
                  }
                : doc
            )
          )

          // Refresh full list if indexed
          if (data.status === 'indexed') {
            await fetchIndexedDocuments()
          }
        }
      } catch (err) {
        // Non-fatal polling error - log for debugging
        console.debug('[Evidence] Polling error:', err)
      }
    },
    [fetchIndexedDocuments]
  )

  // Start polling for a document
  const startPolling = useCallback(
    (documentId: string) => {
      // Clear existing interval
      const existing = pollingIntervals.current.get(documentId)
      if (existing) {
        clearInterval(existing)
      }

      const interval = setInterval(
        () => pollDocumentStatus(documentId),
        POLL_INTERVAL
      )
      pollingIntervals.current.set(documentId, interval)
    },
    [pollDocumentStatus]
  )

  // Upload a PDF file
  const uploadPdf = useCallback(
    async (file: File): Promise<string | null> => {
      setError(null)

      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(`${API_BASE_URL}/documents/upload`, {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(
            errorData.detail || `Upload failed: ${response.statusText}`
          )
        }

        const data = await response.json()
        const documentId = data.document_id

        // Add to indexed docs with processing status
        const newDoc: IndexedDocument = {
          documentId,
          title: file.name.replace(/\.pdf$/i, ''),
          status: data.status === 'indexed' ? 'indexed' : 'processing',
          message: data.message,
        }

        setIndexedDocs(prev => {
          const exists = prev.some(d => d.documentId === documentId)
          if (exists) {
            return prev.map(d => (d.documentId === documentId ? newDoc : d))
          }
          return [...prev, newDoc]
        })

        // Start polling if processing
        if (data.status === 'processing') {
          startPolling(documentId)
        }

        return documentId
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Upload failed'
        setError(message)
        return null
      }
    },
    [startPolling]
  )

  // Index a paper (upload its PDF)
  const indexPaper = useCallback(
    async (citeKey: string, file: File): Promise<void> => {
      await uploadPdf(file)
    },
    [uploadPdf]
  )

  // Reindex an existing document
  const reindexPaper = useCallback(
    async (documentId: string): Promise<void> => {
      setError(null)

      try {
        const response = await fetch(
          `${API_BASE_URL}/documents/${documentId}/reindex`,
          { method: 'POST' }
        )

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(
            errorData.detail || `Reindex failed: ${response.statusText}`
          )
        }

        // Update status to processing
        setIndexedDocs(prev =>
          prev.map(doc =>
            doc.documentId === documentId
              ? { ...doc, status: 'processing' as const }
              : doc
          )
        )

        // Start polling
        startPolling(documentId)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Reindex failed'
        setError(message)
      }
    },
    [startPolling]
  )

  // Remove a document from index
  const removePaper = useCallback(async (documentId: string): Promise<void> => {
    setError(null)

    try {
      const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(
          errorData.detail || `Delete failed: ${response.statusText}`
        )
      }

      // Remove from local state
      setIndexedDocs(prev => prev.filter(d => d.documentId !== documentId))

      // Stop any polling
      const interval = pollingIntervals.current.get(documentId)
      if (interval) {
        clearInterval(interval)
        pollingIntervals.current.delete(documentId)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed'
      setError(message)
    }
  }, [])

  // Merge bib entries with indexed documents
  const papers = useMemo<ReferencePaper[]>(() => {
    // Create a map of indexed docs by title (lowercased for matching)
    const indexedByTitle = new Map<string, IndexedDocument>()
    const indexedByDocId = new Map<string, IndexedDocument>()
    for (const doc of indexedDocs) {
      const titleKey = doc.title.toLowerCase().replace(/\.pdf$/i, '')
      indexedByTitle.set(titleKey, doc)
      indexedByDocId.set(doc.documentId, doc)
    }

    // Build papers from bib entries
    const papersFromBib: ReferencePaper[] = bibEntries.map(entry => {
      // Try to match indexed doc by cite key or PDF filename
      const matchKey = entry.citeKey.toLowerCase()
      const indexedDoc = indexedByTitle.get(matchKey)

      let indexStatus: IndexStatus = 'none'
      if (indexedDoc) {
        indexStatus =
          indexedDoc.status === 'processing'
            ? 'indexing'
            : indexedDoc.status === 'error'
              ? 'error'
              : 'indexed'
      }

      return {
        citeKey: entry.citeKey,
        title: entry.title,
        authors: entry.authors,
        year: entry.year,
        hasPdf: entry.hasPdf,
        pdfFileId: entry.pdfFileId,
        pdfFilename: entry.pdfFilename,
        indexStatus,
        documentId: indexedDoc?.documentId,
        chunkCount: indexedDoc?.chunkCount,
        error: indexedDoc?.message,
      }
    })

    // Add orphan indexed docs (not in bib)
    const bibCiteKeys = new Set(bibEntries.map(e => e.citeKey.toLowerCase()))
    const orphanDocs = indexedDocs.filter(
      doc => !bibCiteKeys.has(doc.title.toLowerCase().replace(/\.pdf$/i, ''))
    )

    const orphanPapers: ReferencePaper[] = orphanDocs.map(doc => ({
      citeKey: doc.title,
      title: doc.title,
      hasPdf: true,
      indexStatus:
        doc.status === 'processing'
          ? 'indexing'
          : doc.status === 'error'
            ? 'error'
            : 'indexed',
      documentId: doc.documentId,
      chunkCount: doc.chunkCount,
      error: doc.message,
    }))

    return [...papersFromBib, ...orphanPapers]
  }, [bibEntries, indexedDocs])

  const value = useMemo<ReferencesPanelContextValue>(
    () => ({
      papers,
      isLoading,
      error,
      selectedDocId,
      setSelectedDocId,
      refreshAll,
      indexPaper,
      reindexPaper,
      removePaper,
      uploadPdf,
    }),
    [
      papers,
      isLoading,
      error,
      selectedDocId,
      setSelectedDocId,
      refreshAll,
      indexPaper,
      reindexPaper,
      removePaper,
      uploadPdf,
    ]
  )

  return (
    <ReferencesPanelContext.Provider value={value}>
      {children}
    </ReferencesPanelContext.Provider>
  )
}

export function useReferencesPanelContext() {
  const context = useContext(ReferencesPanelContext)
  if (!context) {
    throw new Error(
      'useReferencesPanelContext must be used within a ReferencesPanelProvider'
    )
  }
  return context
}
