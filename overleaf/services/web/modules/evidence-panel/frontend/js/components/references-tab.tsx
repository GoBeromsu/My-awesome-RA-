import React, { useCallback, useEffect, useRef, useState } from 'react'
import MaterialIcon from '@/shared/components/material-icon'
import { FullSizeLoadingSpinner } from '@/shared/components/loading-spinner'
import { ReferenceItem, ReferenceInfo } from './reference-item'

// Configuration - API URL from window global or environment
declare global {
  interface Window {
    __EVIDENCE_API_URL__?: string
  }
}

const API_BASE_URL = window.__EVIDENCE_API_URL__ || 'http://localhost:8000'
const POLL_INTERVAL = 3000 // 3 seconds
const MAX_POLL_RETRIES = 10
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50 MB

interface IndexedDocument {
  document_id: string
  title: string | null
  authors: string | null
  chunk_count: number
  indexed_at: string | null
}

interface DocumentStatus {
  document_id: string
  status: 'processing' | 'indexed' | 'error'
  message: string | null
  chunk_count: number | null
}

const isValidPdf = (file: File): boolean => {
  const validExtension = file.name.toLowerCase().endsWith('.pdf')
  const validMimeType = file.type === 'application/pdf' || file.type === ''
  return validExtension && validMimeType
}

export const ReferencesTab: React.FC = React.memo(function ReferencesTab() {
  const [references, setReferences] = useState<ReferenceInfo[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set())
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map())
  const pollRetryCountRef = useRef<Map<string, number>>(new Map())

  // Fetch indexed documents from API
  const fetchIndexedDocuments = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/documents`)
      if (!response.ok) {
        throw new Error('Failed to fetch documents')
      }
      const data = await response.json()

      const refs: ReferenceInfo[] = data.documents.map((doc: IndexedDocument) => ({
        documentId: doc.document_id,
        filename: doc.title || doc.document_id,
        title: doc.title || doc.document_id,
        status: 'indexed' as const,
        chunkCount: doc.chunk_count,
      }))

      setReferences(refs)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchIndexedDocuments()
  }, [fetchIndexedDocuments])

  // Cleanup polling timers on unmount
  useEffect(() => {
    return () => {
      pollTimersRef.current.forEach(timer => clearTimeout(timer))
      pollTimersRef.current.clear()
      pollRetryCountRef.current.clear()
    }
  }, [])

  // Poll for document status with retry limit and exponential backoff
  const pollDocumentStatus = useCallback(async (documentId: string) => {
    const retries = pollRetryCountRef.current.get(documentId) || 0

    const stopPollingWithError = (errorMessage: string) => {
      const timer = pollTimersRef.current.get(documentId)
      if (timer) {
        clearTimeout(timer)
        pollTimersRef.current.delete(documentId)
      }
      pollRetryCountRef.current.delete(documentId)

      setReferences(prev =>
        prev.map(ref =>
          ref.documentId === documentId
            ? { ...ref, status: 'error' as const, error: errorMessage }
            : ref
        )
      )
      setProcessingIds(prev => {
        const next = new Set(prev)
        next.delete(documentId)
        return next
      })
    }

    try {
      const response = await fetch(`${API_BASE_URL}/documents/${documentId}/status`)
      if (!response.ok) {
        throw new Error('Failed to get status')
      }

      const status: DocumentStatus = await response.json()

      if (status.status === 'indexed') {
        // Stop polling and update reference
        const timer = pollTimersRef.current.get(documentId)
        if (timer) {
          clearTimeout(timer)
          pollTimersRef.current.delete(documentId)
        }
        pollRetryCountRef.current.delete(documentId)

        setReferences(prev =>
          prev.map(ref =>
            ref.documentId === documentId
              ? {
                  ...ref,
                  status: 'indexed' as const,
                  chunkCount: status.chunk_count || 0,
                }
              : ref
          )
        )
        setProcessingIds(prev => {
          const next = new Set(prev)
          next.delete(documentId)
          return next
        })
      } else if (status.status === 'error') {
        stopPollingWithError(status.message || 'Processing failed')
      } else {
        // Continue polling with reset retry count on success
        pollRetryCountRef.current.set(documentId, 0)
        const timer = setTimeout(() => pollDocumentStatus(documentId), POLL_INTERVAL)
        pollTimersRef.current.set(documentId, timer)
      }
    } catch (err) {
      // Check retry limit
      if (retries >= MAX_POLL_RETRIES) {
        stopPollingWithError('Connection timeout')
        return
      }

      // Continue polling with exponential backoff
      pollRetryCountRef.current.set(documentId, retries + 1)
      const backoffDelay = POLL_INTERVAL * Math.pow(1.5, retries)
      const timer = setTimeout(() => pollDocumentStatus(documentId), backoffDelay)
      pollTimersRef.current.set(documentId, timer)
    }
  }, [])

  // Handle file upload
  const handleFileUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    setIsUploading(true)
    setError(null)

    for (const file of Array.from(files)) {
      // Validate file type
      if (!isValidPdf(file)) {
        setError(`"${file.name}" is not a valid PDF file`)
        continue
      }

      // Validate file size
      if (file.size > MAX_FILE_SIZE) {
        setError(`"${file.name}" exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`)
        continue
      }

      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(`${API_BASE_URL}/documents/upload`, {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          throw new Error('Upload failed')
        }

        const result = await response.json()
        const documentId = result.document_id

        // Add to references list with indexing status
        setReferences(prev => {
          // Check if already exists
          const exists = prev.some(ref => ref.documentId === documentId)
          if (exists) {
            return prev.map(ref =>
              ref.documentId === documentId
                ? { ...ref, status: 'indexing' as const }
                : ref
            )
          }
          return [
            ...prev,
            {
              documentId,
              filename: file.name,
              title: file.name.replace(/\.pdf$/i, ''),
              status: 'indexing' as const,
            },
          ]
        })

        setProcessingIds(prev => new Set(prev).add(documentId))

        // Start polling for status if processing
        if (result.status === 'processing') {
          const timer = setTimeout(() => pollDocumentStatus(documentId), POLL_INTERVAL)
          pollTimersRef.current.set(documentId, timer)
        } else if (result.status === 'indexed') {
          // Already indexed
          setReferences(prev =>
            prev.map(ref =>
              ref.documentId === documentId
                ? { ...ref, status: 'indexed' as const }
                : ref
            )
          )
          setProcessingIds(prev => {
            const next = new Set(prev)
            next.delete(documentId)
            return next
          })
        }
      } catch (err) {
        setError(`Failed to upload ${file.name}`)
      }
    }

    setIsUploading(false)
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [pollDocumentStatus])

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleIndex = useCallback(async (documentId: string) => {
    // For re-indexing, we need the file - prompt user to upload again
    // This is triggered for 'not_indexed' or 'error' status items
    // In the current implementation, items come from API with 'indexed' status
    // so this is mainly for retry after error
    handleUploadClick()
  }, [handleUploadClick])

  const handleReindex = useCallback(async (documentId: string) => {
    setProcessingIds(prev => new Set(prev).add(documentId))

    // Update status to indexing
    setReferences(prev =>
      prev.map(ref =>
        ref.documentId === documentId
          ? { ...ref, status: 'indexing' as const }
          : ref
      )
    )

    try {
      const response = await fetch(`${API_BASE_URL}/documents/${documentId}/reindex`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error('Reindex failed')
      }

      // Start polling for status
      const timer = setTimeout(() => pollDocumentStatus(documentId), POLL_INTERVAL)
      pollTimersRef.current.set(documentId, timer)
    } catch (err) {
      setReferences(prev =>
        prev.map(ref =>
          ref.documentId === documentId
            ? { ...ref, status: 'error' as const, error: 'Reindex failed' }
            : ref
        )
      )
      setProcessingIds(prev => {
        const next = new Set(prev)
        next.delete(documentId)
        return next
      })
    }
  }, [pollDocumentStatus])

  const handleRemove = useCallback(async (documentId: string) => {
    setProcessingIds(prev => new Set(prev).add(documentId))

    try {
      const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to remove document')
      }

      setReferences(prev => prev.filter(ref => ref.documentId !== documentId))
    } catch (err) {
      setReferences(prev =>
        prev.map(ref =>
          ref.documentId === documentId
            ? { ...ref, status: 'error' as const, error: 'Failed to remove' }
            : ref
        )
      )
    } finally {
      setProcessingIds(prev => {
        const next = new Set(prev)
        next.delete(documentId)
        return next
      })
    }
  }, [])

  if (isLoading) {
    return (
      <div className="references-tab-loading">
        <FullSizeLoadingSpinner delay={200} />
        <div className="references-tab-loading-text">Loading references...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="references-tab-error">
        <MaterialIcon type="error_outline" />
        <div className="references-tab-error-message">{error}</div>
        <button
          className="btn btn-secondary btn-sm"
          onClick={fetchIndexedDocuments}
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="references-tab">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        multiple
        onChange={handleFileUpload}
        style={{ display: 'none' }}
      />

      <div className="references-tab-header">
        <span className="references-tab-count">
          {references.filter(r => r.status === 'indexed').length} indexed
        </span>
        <div className="references-tab-actions">
          <button
            className="btn btn-primary btn-sm"
            onClick={handleUploadClick}
            disabled={isUploading}
            title="Upload PDF files"
          >
            {isUploading ? (
              <MaterialIcon type="hourglass_empty" />
            ) : (
              <MaterialIcon type="upload_file" />
            )}
            <span>Upload</span>
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={fetchIndexedDocuments}
            title="Refresh list"
          >
            <MaterialIcon type="refresh" />
          </button>
        </div>
      </div>

      {references.length === 0 ? (
        <div className="references-tab-empty">
          <MaterialIcon type="library_books" />
          <div className="references-tab-empty-title">No references indexed</div>
          <div className="references-tab-empty-hint">
            Upload PDF files to your project and index them here
          </div>
        </div>
      ) : (
        <div className="references-list">
          {references.map(ref => (
            <ReferenceItem
              key={ref.documentId}
              reference={ref}
              onIndex={handleIndex}
              onRemove={handleRemove}
              onReindex={handleReindex}
              disabled={processingIds.has(ref.documentId)}
            />
          ))}
        </div>
      )}
    </div>
  )
})

export default ReferencesTab
