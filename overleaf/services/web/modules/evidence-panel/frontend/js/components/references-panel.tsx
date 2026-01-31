import React, { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import MaterialIcon from '@/shared/components/material-icon'
import '../../stylesheets/evidence-panel.scss'
import { FullSizeLoadingSpinner } from '@/shared/components/loading-spinner'
import OLIconButton from '@/shared/components/ol/ol-icon-button'
import OLTooltip from '@/shared/components/ol/ol-tooltip'
import RailPanelHeader from '@/features/ide-redesign/components/rail/rail-panel-header'
import { ReferenceTreeItem } from './reference-tree-item'
import {
  useReferencesPanelContext,
  ReferencePaper,
} from '../context/references-panel-context'

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50 MB

export const ReferencesPanel: React.FC = React.memo(function ReferencesPanel() {
  const { t } = useTranslation()
  const {
    papers,
    isLoading,
    error,
    refreshAll,
    uploadPdf,
    reindexPaper,
    removePaper,
  } = useReferencesPanelContext()

  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Stats
  const indexedCount = papers.filter(p => p.indexStatus === 'indexed').length
  const totalCount = papers.length
  const processingCount = papers.filter(p => p.indexStatus === 'indexing').length

  // Handle file upload
  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files
      if (!files || files.length === 0) return

      setIsUploading(true)

      for (const file of Array.from(files)) {
        // Validate
        if (!file.name.toLowerCase().endsWith('.pdf')) {
          continue
        }
        if (file.size > MAX_FILE_SIZE) {
          continue
        }

        await uploadPdf(file)
      }

      setIsUploading(false)

      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    },
    [uploadPdf]
  )

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleIndex = useCallback(
    (_paper: ReferencePaper) => {
      // Trigger file upload for this paper
      handleUploadClick()
    },
    [handleUploadClick]
  )

  const handleReindex = useCallback(
    (paper: ReferencePaper) => {
      if (paper.documentId) {
        reindexPaper(paper.documentId)
      }
    },
    [reindexPaper]
  )

  const handleRemove = useCallback(
    (paper: ReferencePaper) => {
      if (paper.documentId) {
        removePaper(paper.documentId)
      }
    },
    [removePaper]
  )

  // Header actions
  const headerActions = [
    <OLTooltip
      key="upload"
      id="references-upload"
      description={t('upload_pdf_files')}
      overlayProps={{ placement: 'bottom' }}
    >
      <OLIconButton
        onClick={handleUploadClick}
        disabled={isUploading}
        icon={isUploading ? 'hourglass_empty' : 'upload_file'}
        accessibilityLabel={t('upload_pdf_files')}
        size="sm"
        className="rail-panel-header-button-subdued"
      />
    </OLTooltip>,
    <OLTooltip
      key="refresh"
      id="references-refresh"
      description={t('refresh_list')}
      overlayProps={{ placement: 'bottom' }}
    >
      <OLIconButton
        onClick={refreshAll}
        disabled={isLoading}
        icon="refresh"
        accessibilityLabel={t('refresh_list')}
        size="sm"
        className="rail-panel-header-button-subdued"
      />
    </OLTooltip>,
  ]

  if (isLoading && papers.length === 0) {
    return (
      <div className="references-panel">
        <RailPanelHeader
          title={t('reference_library')}
          actions={headerActions}
        />
        <div className="references-panel-loading">
          <FullSizeLoadingSpinner delay={200} />
          <span>{t('loading_references')}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="references-panel">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        multiple
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      {/* Header using RailPanelHeader */}
      <RailPanelHeader
        title={
          <span className="references-panel-title-content">
            {t('reference_library')}
            <span className="references-panel-count">
              {indexedCount}/{totalCount}
            </span>
            {processingCount > 0 && (
              <span className="references-panel-processing">
                <MaterialIcon type="sync" className="icon-spin" />
              </span>
            )}
          </span>
        }
        actions={headerActions}
      />

      {/* Error banner */}
      {error && (
        <div className="references-panel-error-banner">
          <MaterialIcon type="error_outline" />
          <span>{error}</span>
        </div>
      )}

      {/* Content */}
      <div className="references-panel-content">
        {papers.length === 0 ? (
          <div className="references-panel-empty">
            <MaterialIcon type="library_books" />
            <div className="references-panel-empty-title">
              {t('no_references')}
            </div>
            <div className="references-panel-empty-hint">
              {t('upload_pdfs_hint')}
            </div>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleUploadClick}
            >
              <MaterialIcon type="upload_file" />
              <span>{t('upload_pdfs')}</span>
            </button>
          </div>
        ) : (
          <ul className="references-tree" role="tree" aria-label={t('reference_library')}>
            {papers.map(paper => (
              <ReferenceTreeItem
                key={paper.documentId || paper.citeKey}
                paper={paper}
                onIndex={handleIndex}
                onReindex={handleReindex}
                onRemove={handleRemove}
                onUploadPdf={handleUploadClick}
                disabled={isUploading}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
})

export default ReferencesPanel
