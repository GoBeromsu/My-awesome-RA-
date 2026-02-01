import { ElementType, memo, Suspense, useState, useEffect, useCallback, lazy } from 'react'
import classNames from 'classnames'
import PdfLogsViewer from './pdf-logs-viewer'
import PdfViewer from './pdf-viewer'
import { FullSizeLoadingSpinner } from '../../../shared/components/loading-spinner'
import PdfHybridPreviewToolbar from './pdf-preview-hybrid-toolbar'
import { useDetachCompileContext as useCompileContext } from '../../../shared/context/detach-compile-context'
import { PdfPreviewMessages } from './pdf-preview-messages'
import CompileTimeWarningUpgradePrompt from './compile-time-warning-upgrade-prompt'
import { PdfPreviewProvider } from './pdf-preview-provider'
import PdfPreviewHybridToolbarNew from '@/features/ide-redesign/components/pdf-preview/pdf-preview-hybrid-toolbar'
import { useIsNewEditorEnabled } from '@/features/ide-redesign/utils/new-editor-utils'
import importOverleafModules from '../../../../macros/import-overleaf-module.macro'
import PdfCodeCheckFailedBanner from '@/features/ide-redesign/components/pdf-preview/pdf-code-check-failed-banner'
import getMeta from '@/utils/meta'
import NewPdfLogsViewer from '@/features/ide-redesign/components/pdf-preview/pdf-logs-viewer'
import { EVIDENCE_SHOW_EVENT } from '@modules/evidence-panel/frontend/js/constants/events'

// Lazy load EvidencePanel for code splitting
const EvidencePanel = lazy(() =>
  import('@modules/evidence-panel/frontend/js/components/evidence-panel').then(
    module => ({ default: module.EvidencePanel })
  )
)

// Lazy load ChatTab for code splitting (replaces FeedbackPanel)
const ChatTab = lazy(() =>
  import('@modules/evidence-panel/frontend/js/components/chat-tab')
)

function PdfPreviewPane() {
  const {
    pdfUrl,
    pdfViewer,
    darkModePdf: darkModeSetting,
    activeOverallTheme,
  } = useCompileContext()
  const { compileTimeout } = getMeta('ol-compileSettings')
  const usesNewEditor = useIsNewEditorEnabled()
  const darkModePdf =
    usesNewEditor &&
    pdfViewer === 'pdfjs' &&
    activeOverallTheme === 'dark' &&
    darkModeSetting

  // Panel view toggle states (mutually exclusive)
  const [showEvidence, setShowEvidence] = useState(false)
  const [showAnalyze, setShowAnalyze] = useState(false)

  // Auto-switch to Evidence view when paragraph is selected
  useEffect(() => {
    const handleShowEvidence = () => {
      setShowEvidence(true)
      setShowAnalyze(false) // Close Analyze when Evidence is triggered
    }
    window.addEventListener(EVIDENCE_SHOW_EVENT, handleShowEvidence)
    return () => {
      window.removeEventListener(EVIDENCE_SHOW_EVENT, handleShowEvidence)
    }
  }, [])

  // Manual toggle callback for toolbar button (mutual exclusivity)
  const toggleEvidence = useCallback(() => {
    setShowEvidence(prev => {
      if (!prev) setShowAnalyze(false) // Close Analyze when opening Evidence
      return !prev
    })
  }, [])

  const toggleAnalyze = useCallback(() => {
    setShowAnalyze(prev => {
      if (!prev) setShowEvidence(false) // Close Evidence when opening Analyze
      return !prev
    })
  }, [])

  const classes = classNames('pdf', 'full-size', {
    'pdf-empty': !pdfUrl,
    'pdf-dark-mode': darkModePdf,
  })
  const newEditor = useIsNewEditorEnabled()

  const pdfPromotions = importOverleafModules('pdfPreviewPromotions') as {
    import: { default: ElementType }
    path: string
  }[]

  return (
    <div className={classes}>
      <PdfPreviewProvider>
        {newEditor ? (
          <PdfPreviewHybridToolbarNew
            showEvidence={showEvidence}
            onToggleEvidence={toggleEvidence}
            showAnalyze={showAnalyze}
            onToggleAnalyze={toggleAnalyze}
          />
        ) : (
          <PdfHybridPreviewToolbar
            showEvidence={showEvidence}
            onToggleEvidence={toggleEvidence}
            showAnalyze={showAnalyze}
            onToggleAnalyze={toggleAnalyze}
          />
        )}
        {newEditor && <PdfCodeCheckFailedBanner />}
        <PdfPreviewMessages>
          {compileTimeout < 60 && <CompileTimeWarningUpgradePrompt />}
        </PdfPreviewMessages>

        {showEvidence ? (
          <Suspense fallback={<FullSizeLoadingSpinner delay={500} />}>
            <div className="evidence-viewer-container" data-testid="evidence-panel">
              <EvidencePanel />
            </div>
          </Suspense>
        ) : showAnalyze ? (
          <Suspense fallback={<FullSizeLoadingSpinner delay={500} />}>
            <div className="evidence-viewer-container" data-testid="chat-panel">
              <ChatTab />
            </div>
          </Suspense>
        ) : (
          <>
            <Suspense fallback={<FullSizeLoadingSpinner delay={500} />}>
              <div className="pdf-viewer" data-testid="pdf-viewer">
                <PdfViewer />
              </div>
            </Suspense>
            {newEditor ? <NewPdfLogsViewer /> : <PdfLogsViewer />}
          </>
        )}

        {pdfPromotions.map(({ import: { default: Component }, path }) => (
          <Component key={path} />
        ))}
      </PdfPreviewProvider>
    </div>
  )
}

export default memo(PdfPreviewPane)
