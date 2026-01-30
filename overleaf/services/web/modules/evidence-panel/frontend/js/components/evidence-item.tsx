import React, { useCallback, useState } from 'react'
import classNames from 'classnames'
import MaterialIcon from '@/shared/components/material-icon'
import { EvidenceResult } from '../context/evidence-context'

declare global {
  interface Window {
    __EVIDENCE_API_URL__?: string
  }
}

interface EvidenceItemProps {
  result: EvidenceResult
  rank: number
  isCited?: boolean
}

export const EvidenceItem: React.FC<EvidenceItemProps> = React.memo(
  function EvidenceItem({ result, rank, isCited }) {
    const [isExpanded, setIsExpanded] = useState(false)

    const toggleExpand = useCallback(() => {
      setIsExpanded(prev => !prev)
    }, [])

    const scorePercentage = Math.round(result.score * 100)
    const levelClass =
      scorePercentage >= 80
        ? 'success'
        : scorePercentage >= 60
          ? 'typesetting'
          : 'info'

    const handleCopySnippet = useCallback(
      (e: React.MouseEvent) => {
        e.stopPropagation()
        navigator.clipboard.writeText(result.snippet)
      },
      [result.snippet]
    )

    const handleViewPdf = useCallback(
      (e: React.MouseEvent) => {
        e.stopPropagation()
        const apiBaseUrl =
          window.__EVIDENCE_API_URL__ || 'http://localhost:8000'
        const page = result.page || 1
        const pdfUrl = `${apiBaseUrl}/documents/${result.documentId}/file#page=${page}`
        window.open(pdfUrl, '_blank', 'noopener,noreferrer')
      },
      [result.documentId, result.page]
    )

    const formatCitation = () => {
      const parts = []
      if (result.authors) {
        parts.push(result.authors)
      }
      if (result.year) {
        parts.push(`(${result.year})`)
      }
      return parts.join(' ')
    }

    const citedClass =
      isCited === undefined
        ? undefined
        : isCited
          ? 'evidence-item--cited'
          : 'evidence-item--non-cited'

    return (
      <div className={classNames('log-entry', citedClass)} role="listitem">
        <div
          className={`log-entry-header log-entry-header-${levelClass} evidence-item-header`}
          onClick={toggleExpand}
        >
          <span className="evidence-rank">#{rank}</span>
          <h3 className="log-entry-header-title">
            {result.title}
            <small style={{ fontWeight: 'normal', marginLeft: '8px' }}>
              {formatCitation()}
            </small>
          </h3>
          <span className="evidence-score">{scorePercentage}%</span>
          <button
            className={`log-entry-header-link log-entry-header-link-${levelClass}`}
            aria-expanded={isExpanded}
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
            onClick={toggleExpand}
          >
            <MaterialIcon
              type={isExpanded ? 'expand_less' : 'expand_more'}
            />
          </button>
        </div>

        {isExpanded && (
          <div className="log-entry-content">
            <div className="log-entry-formatted-content">
              <blockquote className="evidence-snippet">
                {result.snippet}
              </blockquote>
            </div>

            <div className="evidence-meta">
              {result.page && (
                <span className="evidence-meta-item">
                  <MaterialIcon type="description" />
                  Page {result.page}
                </span>
              )}
              {result.sourcePdf && (
                <span className="evidence-meta-item">
                  <MaterialIcon type="picture_as_pdf" />
                  {result.sourcePdf.split('/').pop()}
                </span>
              )}
            </div>

            <div className="logs-pane-actions evidence-actions">
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleCopySnippet}
                title="Copy snippet to clipboard"
              >
                <MaterialIcon type="content_copy" />
                Copy
              </button>
              {result.documentId && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleViewPdf}
                  title={`Open PDF at page ${result.page || 1}`}
                >
                  <MaterialIcon type="open_in_new" />
                  View PDF
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    )
  }
)
