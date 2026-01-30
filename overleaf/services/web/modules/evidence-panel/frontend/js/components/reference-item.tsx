import React from 'react'
import MaterialIcon from '@/shared/components/material-icon'

export interface ReferenceInfo {
  documentId: string
  filename: string
  title: string
  status: 'not_indexed' | 'indexing' | 'indexed' | 'error'
  chunkCount?: number
  error?: string
}

interface ReferenceItemProps {
  reference: ReferenceInfo
  onIndex: (documentId: string) => void
  onRemove: (documentId: string) => void
  onReindex?: (documentId: string) => void
  disabled?: boolean
}

export const ReferenceItem: React.FC<ReferenceItemProps> = React.memo(
  function ReferenceItem({
    reference,
    onIndex,
    onRemove,
    onReindex,
    disabled = false,
  }) {
  const getStatusIcon = () => {
    switch (reference.status) {
      case 'indexed':
        return <MaterialIcon type="check_circle" className="status-icon indexed" />
      case 'indexing':
        return <MaterialIcon type="hourglass_empty" className="status-icon indexing" />
      case 'error':
        return <MaterialIcon type="error" className="status-icon error" />
      default:
        return <MaterialIcon type="radio_button_unchecked" className="status-icon not-indexed" />
    }
  }

  const getStatusText = () => {
    switch (reference.status) {
      case 'indexed':
        return `${reference.chunkCount} chunks`
      case 'indexing':
        return 'Indexing...'
      case 'error':
        return reference.error || 'Error'
      default:
        return 'Not indexed'
    }
  }

  return (
    <div className={`reference-item reference-item--${reference.status}`}>
      <div className="reference-item-icon">
        <MaterialIcon type="picture_as_pdf" />
      </div>
      <div className="reference-item-content">
        <div className="reference-item-title" title={reference.title}>
          {reference.title}
        </div>
        <div className="reference-item-filename" title={reference.filename}>
          {reference.filename}
        </div>
        <div className="reference-item-status">
          {getStatusIcon()}
          <span className="reference-item-status-text">{getStatusText()}</span>
        </div>
      </div>
      <div className="reference-item-actions">
        {reference.status === 'not_indexed' && (
          <button
            className="btn btn-sm btn-primary"
            onClick={() => onIndex(reference.documentId)}
            disabled={disabled}
            title="Index this PDF for evidence search"
          >
            Index
          </button>
        )}
        {reference.status === 'indexed' && (
          <>
            {onReindex && (
              <button
                className="btn btn-sm btn-secondary"
                onClick={() => onReindex(reference.documentId)}
                disabled={disabled}
                title="Re-parse and re-index this document"
              >
                <MaterialIcon type="refresh" />
              </button>
            )}
            <button
              className="btn btn-sm btn-danger-ghost"
              onClick={() => onRemove(reference.documentId)}
              disabled={disabled}
              title="Remove from index"
            >
              Remove
            </button>
          </>
        )}
        {reference.status === 'error' && (
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => onIndex(reference.documentId)}
            disabled={disabled}
            title="Retry indexing"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  )
  }
)

export default ReferenceItem
