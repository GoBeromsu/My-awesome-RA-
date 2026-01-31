import React from 'react'
import { useTranslation } from 'react-i18next'
import MaterialIcon from '@/shared/components/material-icon'
import OLTooltip from '@/shared/components/ol/ol-tooltip'
import OLSpinner from '@/shared/components/ol/ol-spinner'
import type { IndexStatus } from '../context/references-panel-context'

interface ReferenceStatusIconsProps {
  hasPdf: boolean
  indexStatus: IndexStatus
}

export const ReferenceStatusIcons: React.FC<ReferenceStatusIconsProps> = ({
  hasPdf,
  indexStatus,
}) => {
  const { t } = useTranslation()

  return (
    <span className="reference-status-icons">
      <PdfStatusIcon hasPdf={hasPdf} t={t} />
      {hasPdf && <IndexStatusIcon status={indexStatus} t={t} />}
    </span>
  )
}

interface PdfStatusIconProps {
  hasPdf: boolean
  t: (key: string) => string
}

function PdfStatusIcon({ hasPdf, t }: PdfStatusIconProps) {
  if (hasPdf) {
    return (
      <OLTooltip
        id="pdf-status-uploaded"
        description={t('pdf_uploaded')}
        overlayProps={{ placement: 'top' }}
      >
        <span className="status-icon status-icon--success">
          <MaterialIcon type="picture_as_pdf" />
        </span>
      </OLTooltip>
    )
  }

  return (
    <OLTooltip
      id="pdf-status-missing"
      description={t('no_pdf')}
      overlayProps={{ placement: 'top' }}
    >
      <span className="status-icon status-icon--muted">
        <MaterialIcon type="picture_as_pdf" />
      </span>
    </OLTooltip>
  )
}

interface IndexStatusIconProps {
  status: IndexStatus
  t: (key: string) => string
}

function IndexStatusIcon({ status, t }: IndexStatusIconProps) {
  switch (status) {
    case 'indexed':
      return (
        <OLTooltip
          id="index-status-indexed"
          description={t('indexed')}
          overlayProps={{ placement: 'top' }}
        >
          <span className="status-icon status-icon--success">
            <MaterialIcon type="check_circle" />
          </span>
        </OLTooltip>
      )

    case 'indexing':
      return (
        <OLTooltip
          id="index-status-indexing"
          description={t('indexing')}
          overlayProps={{ placement: 'top' }}
        >
          <span className="status-icon status-icon--warning">
            <OLSpinner size="sm" />
          </span>
        </OLTooltip>
      )

    case 'error':
      return (
        <OLTooltip
          id="index-status-error"
          description={t('indexing_failed')}
          overlayProps={{ placement: 'top' }}
        >
          <span className="status-icon status-icon--danger">
            <MaterialIcon type="error" />
          </span>
        </OLTooltip>
      )

    default:
      return (
        <OLTooltip
          id="index-status-none"
          description={t('not_indexed')}
          overlayProps={{ placement: 'top' }}
        >
          <span className="status-icon status-icon--muted">
            <MaterialIcon type="radio_button_unchecked" />
          </span>
        </OLTooltip>
      )
  }
}

export default ReferenceStatusIcons
