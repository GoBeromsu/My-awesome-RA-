import { useState, useCallback, useRef, useEffect } from 'react'

declare global {
  interface Window {
    __EVIDENCE_API_URL__?: string
  }
}

const API_BASE_URL = window.__EVIDENCE_API_URL__ || 'http://localhost:8000'
const POLL_INTERVAL = 2000

export type DocumentStatus = 'processing' | 'indexed' | 'error'

export interface IndexedDocument {
  documentId: string
  citeKey: string | null
  title: string
  status: DocumentStatus
  chunkCount?: number
  pageCount?: number
  message?: string
  hasPdf: boolean
}

interface IndexedDocumentResponse {
  document_id: string
  cite_key: string | null
  title: string | null
  authors: string | null
  year: number | null
  page_count: number | null
  chunk_count: number
  indexed_at: string | null
  has_pdf?: boolean
}

function extractErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

export interface UseDocumentsApiResult {
  documents: IndexedDocument[]
  isLoading: boolean
  error: string | null
  fetchDocuments: () => Promise<void>
  uploadDocument: (file: File, citeKey?: string) => Promise<string | null>
  reindexDocument: (documentId: string) => Promise<void>
  removeDocument: (documentId: string) => Promise<void>
  clearError: () => void
}

export function useDocumentsApi(): UseDocumentsApiResult {
  const [documents, setDocuments] = useState<IndexedDocument[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pollingIntervals = useRef<Map<string, NodeJS.Timeout>>(new Map())

  const clearError = useCallback(() => setError(null), [])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      pollingIntervals.current.forEach(interval => clearInterval(interval))
      pollingIntervals.current.clear()
    }
  }, [])

  const stopPolling = useCallback((documentId: string) => {
    const interval = pollingIntervals.current.get(documentId)
    if (interval) {
      clearInterval(interval)
      pollingIntervals.current.delete(documentId)
    }
  }, [])

  const fetchDocuments = useCallback(async () => {
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
          citeKey: doc.cite_key,
          title: doc.title || doc.document_id,
          status: 'indexed' as const,
          chunkCount: doc.chunk_count,
          pageCount: doc.page_count ?? undefined,
          hasPdf: doc.has_pdf ?? doc.chunk_count > 0,
        })
      )

      setDocuments(docs)
      setError(null)
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to fetch documents'))
    }
  }, [])

  const pollDocumentStatus = useCallback(
    async (documentId: string): Promise<void> => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/documents/${documentId}/status`
        )
        if (!response.ok) return

        const data = await response.json()

        if (data.status === 'indexed' || data.status === 'error') {
          stopPolling(documentId)

          setDocuments(prev =>
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

          if (data.status === 'indexed') {
            await fetchDocuments()
          }
        }
      } catch {
        // Non-fatal polling error - silently ignore
      }
    },
    [fetchDocuments, stopPolling]
  )

  const startPolling = useCallback(
    (documentId: string) => {
      stopPolling(documentId)
      const interval = setInterval(
        () => pollDocumentStatus(documentId),
        POLL_INTERVAL
      )
      pollingIntervals.current.set(documentId, interval)
    },
    [pollDocumentStatus, stopPolling]
  )

  const uploadDocument = useCallback(
    async (file: File, citeKey?: string): Promise<string | null> => {
      setError(null)

      try {
        const formData = new FormData()
        formData.append('file', file)
        if (citeKey) {
          formData.append('cite_key', citeKey)
        }

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

        const newDoc: IndexedDocument = {
          documentId,
          citeKey: citeKey || null,
          title: file.name.replace(/\.pdf$/i, ''),
          status: data.status === 'indexed' ? 'indexed' : 'processing',
          message: data.message,
          hasPdf: true,  // Uploaded documents have PDFs
        }

        setDocuments(prev => {
          const exists = prev.some(d => d.documentId === documentId)
          if (exists) {
            return prev.map(d => (d.documentId === documentId ? newDoc : d))
          }
          return [...prev, newDoc]
        })

        if (data.status === 'processing') {
          startPolling(documentId)
        }

        return documentId
      } catch (err) {
        setError(extractErrorMessage(err, 'Upload failed'))
        return null
      }
    },
    [startPolling]
  )

  const reindexDocument = useCallback(
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

        setDocuments(prev =>
          prev.map(doc =>
            doc.documentId === documentId
              ? { ...doc, status: 'processing' as const }
              : doc
          )
        )

        startPolling(documentId)
      } catch (err) {
        setError(extractErrorMessage(err, 'Reindex failed'))
      }
    },
    [startPolling]
  )

  const removeDocument = useCallback(
    async (documentId: string): Promise<void> => {
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

        setDocuments(prev => prev.filter(d => d.documentId !== documentId))
        stopPolling(documentId)
      } catch (err) {
        setError(extractErrorMessage(err, 'Delete failed'))
      }
    },
    [stopPolling]
  )

  return {
    documents,
    isLoading,
    error,
    fetchDocuments,
    uploadDocument,
    reindexDocument,
    removeDocument,
    clearError,
  }
}

export default useDocumentsApi
