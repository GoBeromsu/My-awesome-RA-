import React, { useContext } from 'react'
import classnames from 'classnames'
import { EvidenceList } from './evidence-list'
import { useEvidenceContext } from '../context/evidence-context'
import { ReferencesContext } from '@/features/ide-react/context/references-context'
import MaterialIcon from '@/shared/components/material-icon'

export const EvidenceViewer: React.FC = React.memo(
  function EvidenceViewer() {
    const { searchState, currentParagraph } = useEvidenceContext()

    // Try to get reference keys for cited/non-cited differentiation
    // Use useContext directly to allow undefined (when ReferencesProvider is not available)
    const referencesContext = useContext(ReferencesContext)
    const referenceKeys = referencesContext?.referenceKeys

    const renderContent = () => {
      switch (searchState.status) {
        case 'idle':
          return (
            <div className="log-entry">
              <div className="log-entry-header log-entry-header-info">
                <MaterialIcon type="search" />
                <h3 className="log-entry-header-title">
                  Select text in your LaTeX document to search for evidence
                </h3>
              </div>
            </div>
          )

        case 'loading':
          return (
            <div className="log-entry">
              <div className="log-entry-header log-entry-header-info">
                <div className="loading-spinner-small" />
                <h3 className="log-entry-header-title">
                  Searching for evidence...
                </h3>
              </div>
            </div>
          )

        case 'error':
          return (
            <div className="log-entry">
              <div className="log-entry-header log-entry-header-error">
                <MaterialIcon type="error" />
                <h3 className="log-entry-header-title">
                  {searchState.error || 'An error occurred'}
                </h3>
              </div>
            </div>
          )

        case 'success':
          if (searchState.results.length === 0) {
            return (
              <div className="log-entry">
                <div className="log-entry-header log-entry-header-warning">
                  <MaterialIcon type="search_off" />
                  <h3 className="log-entry-header-title">
                    No evidence found for the current paragraph
                  </h3>
                </div>
              </div>
            )
          }
          return (
            <EvidenceList
              results={searchState.results}
              referenceKeys={referenceKeys}
            />
          )
      }
    }

    return (
      <div className={classnames('logs-pane')} data-testid="evidence-viewer">
        <div className="logs-pane-content">
          {/* Header with back button */}
          <div className="log-entry">
            <div className="log-entry-header log-entry-header-success">
              <MaterialIcon type="library_books" />
              <h3 className="log-entry-header-title">
                Evidence
                {searchState.total > 0 && ` (${searchState.total})`}
              </h3>
            </div>
          </div>

          {/* Query display */}
          {currentParagraph && (
            <div className="log-entry">
              <div className="log-entry-header log-entry-header-raw">
                <MaterialIcon type="format_quote" />
                <h3 className="log-entry-header-title">
                  {currentParagraph.length > 100
                    ? `${currentParagraph.substring(0, 100)}...`
                    : currentParagraph}
                </h3>
              </div>
            </div>
          )}

          {/* Results */}
          {renderContent()}
        </div>
      </div>
    )
  }
)
