import React, { useCallback, useState, useMemo } from 'react'
import classNames from 'classnames'
import MaterialIcon from '@/shared/components/material-icon'
import { EvidenceResult } from '../context/evidence-context'
import { useReferencesPanelContext } from '../context/references-panel-context'

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

/**
 * Extract cite key from document ID (format: "CiteKey_hash" or just "CiteKey")
 */
function extractCiteKey(documentId: string): string {
  // Match pattern: everything before the last underscore followed by hex chars
  const match = documentId.match(/^(.+?)_[a-f0-9]{8,}$/i)
  return match ? match[1] : documentId
}

/**
 * Format authors for display: "First Author et al." or just "First Author"
 */
function formatAuthorsShort(authors: string): string {
  if (!authors) return ''

  // BibTeX format: "Last, First and Last2, First2 and ..."
  const authorList = authors.split(/\s+and\s+/i)

  if (authorList.length === 0) return ''

  // Get first author's last name
  const firstAuthor = authorList[0].trim()
  const lastName = firstAuthor.split(',')[0].trim()

  if (authorList.length === 1) {
    return lastName
  }

  return `${lastName} et al.`
}

/**
 * Format citation line: "Author (Year)" or just "Author" or "(Year)"
 */
function formatCitationLine(authors: string, year: number | string | null): string {
  const authorStr = formatAuthorsShort(authors)
  const yearStr = year ? String(year) : ''

  if (authorStr && yearStr) return `${authorStr} (${yearStr})`
  if (authorStr) return authorStr
  if (yearStr) return `(${yearStr})`
  return ''
}

/**
 * Determine CSS class for cited state
 */
function getCitedClass(isCited: boolean | undefined): string | undefined {
  if (isCited === undefined) return undefined
  return isCited ? 'evidence-item--cited' : 'evidence-item--non-cited'
}

/**
 * Determine CSS class for score badge based on percentage
 */
function getScoreClass(scorePercentage: number): string {
  if (scorePercentage >= 80) return 'score-high'
  if (scorePercentage >= 60) return 'score-medium'
  return 'score-low'
}

export const EvidenceItem: React.FC<EvidenceItemProps> = React.memo(
  function EvidenceItem({ result, rank, isCited }) {
    const [isExpanded, setIsExpanded] = useState(false)
    const { getBibMetadata } = useReferencesPanelContext()

    // Extract cite key and look up bib metadata
    const citeKey = extractCiteKey(result.documentId)
    const bibMetadata = getBibMetadata(citeKey)

    // Derive display values: prefer API data, fall back to bib metadata
    const { displayTitle, displayAuthors, displayYear } = useMemo(() => {
      // Title: prefer real API title, then bib metadata, then cite key
      const hasRealTitle = result.title &&
        result.title !== 'Unknown Document' &&
        !result.title.match(/^[A-Za-z]+\d{4}[A-Za-z]+_[a-f0-9]+$/i)

      const title = hasRealTitle
        ? result.title
        : bibMetadata?.title || citeKey

      // Authors: prefer API authors if meaningful
      const authors = (result.authors && result.authors !== 'Unknown Authors')
        ? result.authors
        : bibMetadata?.authors || ''

      // Year: prefer API, fall back to bib metadata
      let year: number | null = null
      if (result.year) {
        year = result.year
      } else if (bibMetadata?.year) {
        year = parseInt(bibMetadata.year, 10) || null
      }

      return { displayTitle: title, displayAuthors: authors, displayYear: year }
    }, [result.title, result.authors, result.year, bibMetadata, citeKey])

    const toggleExpand = useCallback(() => {
      setIsExpanded(prev => !prev)
    }, [])

    const scorePercentage = Math.round(result.score * 100)

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

    const citationLine = formatCitationLine(displayAuthors, displayYear)
    const citedClass = getCitedClass(isCited)
    const scoreClass = getScoreClass(scorePercentage)

    return (
      <div className={classNames('evidence-item', citedClass)} role="listitem">
        <div
          className="evidence-item-header"
          onClick={toggleExpand}
        >
          <span className="evidence-item-rank">#{rank}</span>
          <div className="evidence-item-meta">
            <h3 className="evidence-item-title" title={displayTitle}>
              {displayTitle}
            </h3>
            {citationLine && (
              <span className="evidence-item-citation">{citationLine}</span>
            )}
          </div>
          <span className={classNames('evidence-item-score', scoreClass)}>
            {scorePercentage}%
          </span>
          <button
            className="evidence-item-expand-btn"
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
          <div className="evidence-item-body">
            <div className="evidence-item-snippet">
              <blockquote>
                {result.snippet}
              </blockquote>
            </div>

            <div className="evidence-item-details">
              {result.page && (
                <span>
                  <MaterialIcon type="description" />
                  Page {result.page}
                </span>
              )}
              {result.sourcePdf && (
                <span>
                  <MaterialIcon type="picture_as_pdf" />
                  {result.sourcePdf.split('/').pop()}
                </span>
              )}
            </div>

            <div className="evidence-item-actions">
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
