import React, { Suspense, lazy } from 'react'
import { useTranslation } from 'react-i18next'
import { RailElement } from '@/features/ide-redesign/utils/rail-types'
import { FullSizeLoadingSpinner } from '@/shared/components/loading-spinner'

const ReferencesTab = lazy(() =>
  import('./references-tab').then(m => ({ default: m.ReferencesTab }))
)

// Note: RailElement requires a static title string, not a hook result.
// The i18n key 'reference_library' is available for use elsewhere.
const railEntry: RailElement = {
  key: 'references',
  icon: 'library_books',
  title: 'Reference Library',
  component: (
    <Suspense fallback={<FullSizeLoadingSpinner delay={500} />}>
      <ReferencesTab />
    </Suspense>
  ),
}

export default railEntry
