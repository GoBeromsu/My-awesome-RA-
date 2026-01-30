import { memo, useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import OLButtonToolbar from '@/shared/components/ol/ol-button-toolbar'
import { useLayoutContext } from '@/shared/context/layout-context'
import PdfCompileButton from './pdf-compile-button'
import SwitchToEditorButton from './switch-to-editor-button'
import PdfHybridLogsButton from './pdf-hybrid-logs-button'
import PdfHybridDownloadButton from './pdf-hybrid-download-button'
import PdfHybridCodeCheckButton from './pdf-hybrid-code-check-button'
import PdfOrphanRefreshButton from './pdf-orphan-refresh-button'
import { DetachedSynctexControl } from './detach-synctex-control'
import LoadingSpinner from '@/shared/components/loading-spinner'
import MaterialIcon from '@/shared/components/material-icon'
import OLTooltip from '@/shared/components/ol/ol-tooltip'

const ORPHAN_UI_TIMEOUT_MS = 5000

interface PdfPreviewHybridToolbarProps {
  showEvidence?: boolean
  onToggleEvidence?: () => void
}

function PdfPreviewHybridToolbar({
  showEvidence = false,
  onToggleEvidence,
}: PdfPreviewHybridToolbarProps) {
  const { detachRole, detachIsLinked } = useLayoutContext()
  const { t } = useTranslation()
  const uiTimeoutRef = useRef<number>()
  const [orphanPdfTabAfterDelay, setOrphanPdfTabAfterDelay] = useState(false)

  const orphanPdfTab = !detachIsLinked && detachRole === 'detached'

  useEffect(() => {
    if (uiTimeoutRef.current) {
      window.clearTimeout(uiTimeoutRef.current)
    }

    if (orphanPdfTab) {
      uiTimeoutRef.current = window.setTimeout(() => {
        setOrphanPdfTabAfterDelay(true)
      }, ORPHAN_UI_TIMEOUT_MS)
    } else {
      setOrphanPdfTabAfterDelay(false)
    }
  }, [orphanPdfTab])

  let ToolbarInner = null
  if (orphanPdfTabAfterDelay) {
    // when the detached tab has been orphan for a while
    ToolbarInner = <PdfPreviewHybridToolbarOrphanInner />
  } else if (orphanPdfTab) {
    ToolbarInner = <PdfPreviewHybridToolbarConnectingInner />
  } else {
    // tab is not detached or not orphan
    ToolbarInner = (
      <PdfPreviewHybridToolbarInner
        showEvidence={showEvidence}
        onToggleEvidence={onToggleEvidence}
      />
    )
  }

  return (
    <OLButtonToolbar
      className="toolbar toolbar-pdf toolbar-pdf-hybrid"
      aria-label={t('pdf')}
    >
      {ToolbarInner}
    </OLButtonToolbar>
  )
}

interface PdfPreviewHybridToolbarInnerProps {
  showEvidence?: boolean
  onToggleEvidence?: () => void
}

function PdfPreviewHybridToolbarInner({
  showEvidence = false,
  onToggleEvidence,
}: PdfPreviewHybridToolbarInnerProps) {
  const { t } = useTranslation()

  return (
    <>
      <div className="toolbar-pdf-left">
        <PdfCompileButton />
        <PdfHybridLogsButton />
        <PdfHybridDownloadButton />
        {onToggleEvidence && (
          <OLTooltip
            id="toggle-evidence-tooltip"
            description={showEvidence ? t('show_pdf') : t('show_evidence')}
            overlayProps={{ placement: 'bottom' }}
          >
            <button
              className={`toolbar-evidence-toggle ${showEvidence ? 'active' : ''}`}
              onClick={onToggleEvidence}
              aria-pressed={showEvidence}
              aria-label={showEvidence ? t('show_pdf') : t('show_evidence')}
            >
              {showEvidence ? 'PDF' : 'Cite'}
            </button>
          </OLTooltip>
        )}
      </div>
      <div className="toolbar-pdf-right">
        <div className="toolbar-pdf-controls" id="toolbar-pdf-controls" />
        <PdfHybridCodeCheckButton />
        <SwitchToEditorButton />
        <DetachedSynctexControl />
      </div>
    </>
  )
}

function PdfPreviewHybridToolbarOrphanInner() {
  const { t } = useTranslation()
  return (
    <>
      <div className="toolbar-pdf-orphan">
        {t('tab_no_longer_connected')}
        <PdfOrphanRefreshButton />
      </div>
    </>
  )
}

function PdfPreviewHybridToolbarConnectingInner() {
  const { t } = useTranslation()
  return (
    <>
      <div className="toolbar-pdf-orphan">
        <LoadingSpinner size="sm" loadingText={`${t('tab_connecting')}…`} />
      </div>
    </>
  )
}

export default memo(PdfPreviewHybridToolbar)
