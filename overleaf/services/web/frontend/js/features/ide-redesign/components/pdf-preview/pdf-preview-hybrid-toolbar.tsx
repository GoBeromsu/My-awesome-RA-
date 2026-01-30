import { memo, useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import OLButtonToolbar from '@/shared/components/ol/ol-button-toolbar'
import PdfCompileButton from '@/features/pdf-preview/components/pdf-compile-button'
import PdfHybridDownloadButton from '@/features/pdf-preview/components/pdf-hybrid-download-button'
import { DetachedSynctexControl } from '@/features/pdf-preview/components/detach-synctex-control'
import SwitchToEditorButton from '@/features/pdf-preview/components/switch-to-editor-button'
import PdfHybridLogsButton from '@/features/pdf-preview/components/pdf-hybrid-logs-button'
import EditorTourLogsTooltip from '../editor-tour/editor-tour-logs-tooltip'
import MaterialIcon from '@/shared/components/material-icon'
import OLTooltip from '@/shared/components/ol/ol-tooltip'

interface PdfPreviewHybridToolbarProps {
  showEvidence?: boolean
  onToggleEvidence?: () => void
}

function PdfPreviewHybridToolbar({
  showEvidence = false,
  onToggleEvidence,
}: PdfPreviewHybridToolbarProps) {
  const { t } = useTranslation()

  const [logsButtonElt, setLogsButtonElt] = useState<HTMLElement | null>(null)
  const logsButtonRef = useCallback((node: HTMLButtonElement) => {
    if (node !== null) {
      setLogsButtonElt(node)
    }
  }, [])

  // TODO: add detached pdf logic
  return (
    <OLButtonToolbar
      className="toolbar toolbar-pdf toolbar-pdf-hybrid"
      aria-label={t('pdf')}
    >
      <div className="toolbar-pdf-left">
        <PdfCompileButton />
        <PdfHybridLogsButton ref={logsButtonRef} />
        <PdfHybridDownloadButton />
        {onToggleEvidence && (
          <OLTooltip
            id="toggle-evidence-tooltip-new"
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
        <EditorTourLogsTooltip target={logsButtonElt} />
      </div>
      <div className="toolbar-pdf-right">
        <div className="toolbar-pdf-controls" id="toolbar-pdf-controls" />
        <SwitchToEditorButton />
        <DetachedSynctexControl />
        {/* TODO: should we have code check? */}
      </div>
    </OLButtonToolbar>
  )
}

export default memo(PdfPreviewHybridToolbar)
