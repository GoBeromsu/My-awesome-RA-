import React, { useMemo } from 'react'
import { EvidenceItem } from './evidence-item'
import { EvidenceResult } from '../context/evidence-context'

interface EvidenceListProps {
  results: EvidenceResult[]
  referenceKeys?: Set<string>
}

export const EvidenceList: React.FC<EvidenceListProps> = React.memo(
  function EvidenceList({ results, referenceKeys }) {
    // Check if a result's document is cited in the bibliography
    // We match by checking if the document title (normalized) exists in referenceKeys
    const isCitedMap = useMemo(() => {
      if (!referenceKeys || referenceKeys.size === 0) {
        return new Map<string, boolean>()
      }

      const normalizedKeys = new Set(
        [...referenceKeys].map(key => key.toLowerCase())
      )

      return new Map(
        results.map(result => {
          // Try to match the document title against reference keys
          const title = result.title?.toLowerCase() || ''
          const isCited = normalizedKeys.has(title) ||
            [...normalizedKeys].some(key =>
              title.includes(key) || key.includes(title)
            )
          return [result.id, isCited]
        })
      )
    }, [results, referenceKeys])

    if (results.length === 0) {
      return null
    }

    return (
      <div className="evidence-list" role="list">
        {results.map((result, index) => (
          <EvidenceItem
            key={result.id}
            result={result}
            rank={index + 1}
            isCited={referenceKeys ? isCitedMap.get(result.id) : undefined}
          />
        ))}
      </div>
    )
  }
)
