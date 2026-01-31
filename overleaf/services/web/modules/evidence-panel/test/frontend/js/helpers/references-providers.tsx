import React, { ReactNode, createRef } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import sinon from 'sinon'
import {
  ReferencesPanelContext,
  ReferencesPanelContextValue,
  ReferencePaper,
} from '../../../../frontend/js/context/references-panel-context'

// Mock RailContext to avoid dependency on complex providers
const mockRailContext = {
  selectedTab: 'references' as const,
  isOpen: true,
  setIsOpen: () => {},
  panelRef: createRef(),
  togglePane: () => {},
  handlePaneExpand: () => {},
  handlePaneCollapse: () => {},
  resizing: false,
  setResizing: () => {},
  activeModal: null,
  setActiveModal: () => {},
  openTab: () => {},
}

// Create a simple mock for RailContext
const RailContext = React.createContext(mockRailContext)

// Stub the rail-context module to use our mock
const railContextStub = sinon.stub()
railContextStub.returns(mockRailContext)

const defaultContextValue: ReferencesPanelContextValue = {
  papers: [],
  isLoading: false,
  error: null,
  selectedDocId: null,
  setSelectedDocId: () => {},
  refreshAll: async () => {},
  indexPaper: async () => {},
  reindexPaper: async () => {},
  removePaper: async () => {},
  uploadPdf: async () => null,
  getBibMetadata: () => undefined,
}

interface ReferencesProviderWrapperProps {
  children: ReactNode
  value?: Partial<ReferencesPanelContextValue>
}

export function ReferencesProviderWrapper({
  children,
  value = {},
}: ReferencesProviderWrapperProps) {
  const contextValue = {
    ...defaultContextValue,
    ...value,
  }

  return (
    <RailContext.Provider value={mockRailContext}>
      <ReferencesPanelContext.Provider value={contextValue}>
        {children}
      </ReferencesPanelContext.Provider>
    </RailContext.Provider>
  )
}

interface RenderWithReferencesContextOptions {
  contextValue?: Partial<ReferencesPanelContextValue>
  renderOptions?: RenderOptions
}

export function renderWithReferencesContext(
  component: React.ReactElement,
  options: RenderWithReferencesContextOptions = {}
) {
  const { contextValue = {}, renderOptions = {} } = options

  const wrapper = ({ children }: { children: ReactNode }) => (
    <ReferencesProviderWrapper value={contextValue}>
      {children}
    </ReferencesProviderWrapper>
  )

  return render(component, {
    wrapper,
    ...renderOptions,
  })
}

export function createMockPaper(overrides: Partial<ReferencePaper> = {}): ReferencePaper {
  return {
    citeKey: 'Smith2024',
    title: 'Test Paper Title',
    authors: 'Smith, J. and Doe, A.',
    year: '2024',
    hasPdf: true,
    pdfFileId: 'file_1',
    pdfFilename: 'smith2024.pdf',
    indexStatus: 'indexed',
    documentId: 'doc_123456789012',
    chunkCount: 5,
    ...overrides,
  }
}

export function createMockPapers(count: number): ReferencePaper[] {
  return Array.from({ length: count }, (_, i) =>
    createMockPaper({
      citeKey: `Paper${i + 1}`,
      title: `Paper ${i + 1} Title`,
      documentId: `doc_${String(i + 1).padStart(12, '0')}`,
      chunkCount: (i + 1) * 2,
    })
  )
}
