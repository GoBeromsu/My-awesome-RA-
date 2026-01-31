import {
  createContext,
  useContext,
  useCallback,
  useMemo,
  useState,
  useRef,
  useEffect,
  FC,
  ReactNode,
} from 'react'
import {
  EVIDENCE_PARAGRAPH_CHANGE_EVENT,
  ParagraphChangeDetail,
} from '@/features/source-editor/extensions/evidence-tracker'
import { EVIDENCE_SHOW_EVENT } from '../constants/events'
import {
  MIN_PARAGRAPH_LENGTH_FOR_SEARCH,
  MAX_PARAGRAPH_LENGTH_FOR_SEARCH,
} from '../constants/search'

export interface EvidenceResult {
  id: string
  title: string
  authors: string
  year: number | null
  snippet: string
  score: number
  sourcePdf: string
  page: number | null
  documentId: string
  chunkId: string
}

export interface EvidenceSearchState {
  status: 'idle' | 'loading' | 'success' | 'error'
  results: EvidenceResult[]
  query: string
  error: string | null
  total: number
}

export interface EvidenceContextValue {
  searchState: EvidenceSearchState
  currentParagraph: string
  autoMode: boolean
  setAutoMode: (enabled: boolean) => void
  searchEvidence: (query: string) => Promise<void>
  setCurrentParagraph: (paragraph: string) => void
  clearResults: () => void
}

const initialSearchState: EvidenceSearchState = {
  status: 'idle',
  results: [],
  query: '',
  error: null,
  total: 0,
}

export const EvidenceContext = createContext<EvidenceContextValue | undefined>(
  undefined
)

interface EvidenceProviderProps {
  children: ReactNode
  apiBaseUrl?: string
}

export const EvidenceProvider: FC<EvidenceProviderProps> = ({
  children,
  apiBaseUrl = 'http://localhost:8000',
}) => {
  const [searchState, setSearchState] =
    useState<EvidenceSearchState>(initialSearchState)
  const [currentParagraph, setCurrentParagraph] = useState<string>('')
  const [autoMode, setAutoMode] = useState<boolean>(true)

  const abortControllerRef = useRef<AbortController | null>(null)

  const searchEvidence = useCallback(
    async (query: string) => {
      if (!query.trim()) {
        setSearchState(prev => ({
          ...prev,
          status: 'idle',
          results: [],
          query: '',
          total: 0,
        }))
        return
      }

      // Cancel any pending request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }

      abortControllerRef.current = new AbortController()

      setSearchState(prev => ({
        ...prev,
        status: 'loading',
        query,
        error: null,
      }))

      try {
        const response = await fetch(`${apiBaseUrl}/evidence/search`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query,
            top_k: 10,
            threshold: 0.2,
          }),
          signal: abortControllerRef.current.signal,
        })

        if (!response.ok) {
          throw new Error(`Search failed: ${response.statusText}`)
        }

        const data = await response.json()

        const results: EvidenceResult[] = data.results.map(
          (r: {
            document_id: string
            chunk_id: string
            text: string
            page?: number
            score: number
            metadata?: {
              title?: string
              authors?: string
              year?: number
              source_pdf?: string
            }
          }) => ({
            id: `${r.document_id}_${r.chunk_id}`,
            title: r.metadata?.title || 'Unknown Document',
            authors: r.metadata?.authors || 'Unknown Authors',
            year: r.metadata?.year || null,
            snippet: r.text,
            score: r.score,
            sourcePdf: r.metadata?.source_pdf || '',
            page: r.page || null,
            documentId: r.document_id,
            chunkId: r.chunk_id,
          })
        )

        setSearchState({
          status: 'success',
          results,
          query,
          error: null,
          total: data.total,
        })
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          // Request was cancelled, don't update state
          return
        }

        setSearchState(prev => ({
          ...prev,
          status: 'error',
          error: error instanceof Error ? error.message : 'Search failed',
        }))
      }
    },
    [apiBaseUrl]
  )

  const clearResults = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    setSearchState(initialSearchState)
  }, [])

  const value = useMemo<EvidenceContextValue>(
    () => ({
      searchState,
      currentParagraph,
      autoMode,
      setAutoMode,
      searchEvidence,
      setCurrentParagraph,
      clearResults,
    }),
    [
      searchState,
      currentParagraph,
      autoMode,
      setAutoMode,
      searchEvidence,
      setCurrentParagraph,
      clearResults,
    ]
  )

  return (
    <EvidenceContext.Provider value={value}>
      <EvidenceTrackerIntegration />
      {children}
    </EvidenceContext.Provider>
  )
}

/**
 * Component that integrates the CodeMirror evidence tracker with the Evidence context.
 * Listens for paragraph change events and triggers searches in auto mode.
 * This component renders nothing but sets up the event listener.
 */
const EvidenceTrackerIntegration: FC = () => {
  const context = useContext(EvidenceContext)
  if (!context) {
    return null
  }
  const { autoMode, searchEvidence, setCurrentParagraph } = context
  const lastParagraphRef = useRef<string>('')

  const handleParagraphChange = useCallback(
    (event: Event) => {
      if (!autoMode) {
        return
      }

      const customEvent = event as CustomEvent<ParagraphChangeDetail>
      const { paragraph } = customEvent.detail

      // Skip if paragraph hasn't changed
      if (paragraph === lastParagraphRef.current) {
        return
      }

      lastParagraphRef.current = paragraph
      setCurrentParagraph(paragraph)

      // Trigger search if paragraph is meaningful (not too short or too long)
      if (
        paragraph &&
        paragraph.length >= MIN_PARAGRAPH_LENGTH_FOR_SEARCH &&
        paragraph.length <= MAX_PARAGRAPH_LENGTH_FOR_SEARCH
      ) {
        searchEvidence(paragraph)

        // Dispatch event to show Evidence view in PDF panel
        window.dispatchEvent(new CustomEvent(EVIDENCE_SHOW_EVENT))
      }
    },
    [autoMode, searchEvidence, setCurrentParagraph]
  )

  useEffect(() => {
    // Listen for paragraph change events from the CodeMirror extension
    document.addEventListener(
      EVIDENCE_PARAGRAPH_CHANGE_EVENT,
      handleParagraphChange
    )

    return () => {
      document.removeEventListener(
        EVIDENCE_PARAGRAPH_CHANGE_EVENT,
        handleParagraphChange
      )
    }
  }, [handleParagraphChange])

  // Reset last paragraph when auto mode is toggled off
  useEffect(() => {
    if (!autoMode) {
      lastParagraphRef.current = ''
    }
  }, [autoMode])

  return null
}

export function useEvidenceContext() {
  const context = useContext(EvidenceContext)
  if (!context) {
    throw new Error(
      'useEvidenceContext must be used within an EvidenceProvider'
    )
  }
  return context
}
