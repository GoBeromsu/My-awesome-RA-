import React from 'react'
import { ReferencesPanelProvider } from '../context/references-panel-context'
import { ReferencesPanel } from './references-panel'

/**
 * References Tab - File-tree style view of bibliography references
 *
 * Displays papers from .bib files with PDF availability and indexing status.
 * Papers can be indexed for evidence search via the API.
 */
export const ReferencesTab: React.FC = React.memo(function ReferencesTab() {
  return (
    <ReferencesPanelProvider>
      <ReferencesPanel />
    </ReferencesPanelProvider>
  )
})

export default ReferencesTab
