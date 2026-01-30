import React, { useContext, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Form, Nav, Tab } from 'react-bootstrap'
import { useEvidenceContext } from '../context/evidence-context'
import { useEvidenceTrackerIntegration } from '../hooks/use-evidence-tracker-integration'
import { EvidenceSearchBar } from './evidence-search-bar'
import { EvidenceList } from './evidence-list'
import { ReferencesTab } from './references-tab'
import { FullSizeLoadingSpinner } from '@/shared/components/loading-spinner'
import MaterialIcon from '@/shared/components/material-icon'
import withErrorBoundary from '@/infrastructure/error-boundary'
import { ReferencesContext } from '@/features/ide-react/context/references-context'

import '../../stylesheets/evidence-panel.scss'

type TabKey = 'search' | 'references'

const SearchTabContent = React.memo(function SearchTabContent() {
  const {
    searchState,
    currentParagraph,
    autoMode,
    setAutoMode,
    searchEvidence,
    clearResults,
  } = useEvidenceContext()

  // Get reference keys for cited/non-cited differentiation
  const referencesContext = useContext(ReferencesContext)
  const referenceKeys = referencesContext?.referenceKeys

  // Integrate with CodeMirror evidence tracker
  useEvidenceTrackerIntegration()

  const handleManualSearch = (query: string) => {
    searchEvidence(query)
  }

  const isLoading = searchState.status === 'loading'
  const hasResults = searchState.results.length > 0
  const hasError = searchState.status === 'error'
  const isIdle = searchState.status === 'idle'

  return (
    <div className="evidence-search-tab">
      <div className="evidence-search-controls">
        <Form.Check
          type="switch"
          id="evidence-auto-toggle"
          label="Auto"
          checked={autoMode}
          onChange={() => setAutoMode(!autoMode)}
          className="evidence-auto-toggle"
        />
      </div>

      <EvidenceSearchBar onSearch={handleManualSearch} disabled={isLoading} />

      {autoMode && currentParagraph && (
        <div className="evidence-current-context">
          <div className="evidence-context-label">Current paragraph:</div>
          <div className="evidence-context-text">
            {currentParagraph.length > 100
              ? `${currentParagraph.slice(0, 100)}...`
              : currentParagraph}
          </div>
        </div>
      )}

      <div className="evidence-panel-content">
        {isLoading && (
          <div className="evidence-loading">
            <FullSizeLoadingSpinner delay={200} />
            <div className="evidence-loading-text">Searching...</div>
          </div>
        )}

        {hasError && (
          <div className="evidence-error">
            <MaterialIcon type="error_outline" />
            <div className="evidence-error-message">
              {searchState.error || 'Search failed'}
            </div>
            <button
              className="btn btn-secondary btn-sm"
              onClick={clearResults}
            >
              Clear
            </button>
          </div>
        )}

        {!isLoading && !hasError && hasResults && (
          <>
            <div className="evidence-results-header">
              <span className="evidence-results-count">
                {searchState.total} result{searchState.total !== 1 ? 's' : ''} found
              </span>
              <span className="evidence-results-note">
                (Estimated relevance)
              </span>
            </div>
            <EvidenceList
              results={searchState.results}
              referenceKeys={referenceKeys}
            />
          </>
        )}

        {!isLoading && !hasError && !hasResults && !isIdle && (
          <div className="evidence-no-results">
            <MaterialIcon type="search_off" />
            <div>No evidence found</div>
            <div className="evidence-no-results-hint">
              Try a different search or check your indexed documents
            </div>
          </div>
        )}

        {isIdle && (
          <div className="evidence-placeholder">
            <MaterialIcon type="auto_stories" />
            <div className="evidence-placeholder-title">
              {autoMode ? 'Start writing' : 'Search for evidence'}
            </div>
            <div className="evidence-placeholder-hint">
              {autoMode
                ? 'Evidence will appear as you write paragraphs'
                : 'Enter a query above to search your references'}
            </div>
          </div>
        )}
      </div>
    </div>
  )
})

const EvidencePanelContent = React.memo(function EvidencePanelContent() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<TabKey>('search')
  const [isOpenedOnce, setIsOpenedOnce] = useState(false)

  useEffect(() => {
    setIsOpenedOnce(true)
  }, [])

  if (!isOpenedOnce) {
    return null
  }

  return (
    <aside className="evidence-panel" aria-label="Evidence Panel">
      <div className="evidence-panel-header">
        <h2 className="evidence-panel-title">
          <MaterialIcon type="library_books" />
          <span>Evidence</span>
        </h2>
      </div>

      <Tab.Container
        activeKey={activeTab}
        onSelect={(k) => k && setActiveTab(k as TabKey)}
      >
        <Nav variant="tabs" className="evidence-panel-tabs">
          <Nav.Item>
            <Nav.Link eventKey="search">
              <MaterialIcon type="search" />
              <span>Search</span>
            </Nav.Link>
          </Nav.Item>
          <Nav.Item>
            <Nav.Link eventKey="references">
              <MaterialIcon type="folder" />
              <span>References</span>
            </Nav.Link>
          </Nav.Item>
        </Nav>

        <Tab.Content className="evidence-panel-tab-content">
          <Tab.Pane eventKey="search">
            <SearchTabContent />
          </Tab.Pane>
          <Tab.Pane eventKey="references">
            <ReferencesTab />
          </Tab.Pane>
        </Tab.Content>
      </Tab.Container>
    </aside>
  )
})

function EvidencePanelFallback() {
  return (
    <div className="evidence-panel evidence-panel-error">
      <div className="evidence-fallback-message">
        <MaterialIcon type="error" />
        <span>Something went wrong</span>
      </div>
    </div>
  )
}

const EvidencePanelWithBoundary = withErrorBoundary(
  EvidencePanelContent,
  () => <EvidencePanelFallback />
)

export function EvidencePanel() {
  return <EvidencePanelWithBoundary />
}

export default EvidencePanel
