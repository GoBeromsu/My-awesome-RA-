import { EditorView, ViewPlugin, ViewUpdate } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { PARAGRAPH_CHANGE_DEBOUNCE_MS } from '@modules/evidence-panel/frontend/js/constants/search'

/**
 * Event name for paragraph change events
 */
export const EVIDENCE_PARAGRAPH_CHANGE_EVENT = 'evidence:paragraph-change'

/**
 * Interface for paragraph change event detail
 */
export interface ParagraphChangeDetail {
  paragraph: string
  cursorPosition: number
}

/**
 * Check if a line is a blank line (empty or whitespace only)
 */
function isBlankLine(line: string): boolean {
  return line.trim() === ''
}

/**
 * Check if a line is a LaTeX structural command that delimits sections
 */
function isStructuralCommand(line: string): boolean {
  const trimmed = line.trim()
  return (
    /^\\(section|subsection|subsubsection|chapter|part|paragraph|begin|end)\{/.test(
      trimmed
    ) ||
    /^\\(begin|end)\{(document|abstract|figure|table|equation|align)\}/.test(
      trimmed
    )
  )
}

/**
 * Extract the current paragraph from the editor state based on cursor position.
 * Paragraphs are delimited by blank lines or structural LaTeX commands.
 */
export function getCurrentParagraph(state: EditorState): string {
  const cursor = state.selection.main.head
  const doc = state.doc
  const totalLines = doc.lines

  // Find the line containing the cursor
  const cursorLine = doc.lineAt(cursor)
  const cursorLineNumber = cursorLine.number

  // Find paragraph start (search backwards for blank line or structural command)
  let startLine = cursorLineNumber
  for (let i = cursorLineNumber - 1; i >= 1; i--) {
    const line = doc.line(i)
    const lineText = line.text
    if (isBlankLine(lineText) || isStructuralCommand(lineText)) {
      startLine = i + 1
      break
    }
    if (i === 1) {
      startLine = 1
    }
  }

  // Find paragraph end (search forwards for blank line or structural command)
  let endLine = cursorLineNumber
  for (let i = cursorLineNumber + 1; i <= totalLines; i++) {
    const line = doc.line(i)
    const lineText = line.text
    if (isBlankLine(lineText) || isStructuralCommand(lineText)) {
      endLine = i - 1
      break
    }
    if (i === totalLines) {
      endLine = totalLines
    }
  }

  // Ensure valid range
  if (startLine > endLine) {
    return ''
  }

  // Extract paragraph text
  const startPos = doc.line(startLine).from
  const endPos = doc.line(endLine).to
  const paragraphText = doc.sliceString(startPos, endPos)

  return paragraphText.trim()
}

/**
 * Clean LaTeX content for better search queries.
 * Removes common LaTeX commands while preserving meaningful text.
 */
export function cleanLatexForSearch(text: string): string {
  if (!text) {
    return ''
  }

  return (
    text
      // Remove comments
      .replace(/%.*$/gm, '')
      // Remove citation commands but keep the key for reference
      .replace(/\\cite\{([^}]*)\}/g, '')
      // Remove reference commands
      .replace(/\\(ref|eqref|pageref|autoref|cref|Cref)\{[^}]*\}/g, '')
      // Remove label commands
      .replace(/\\label\{[^}]*\}/g, '')
      // Remove common formatting commands with content
      .replace(
        /\\(textbf|textit|emph|underline|textsc|textsf|texttt)\{([^}]*)\}/g,
        '$2'
      )
      // Remove footnotes
      .replace(/\\footnote\{[^}]*\}/g, '')
      // Remove remaining commands with arguments
      .replace(/\\[a-zA-Z]+\{[^}]*\}/g, '')
      // Remove commands without arguments
      .replace(/\\[a-zA-Z]+/g, '')
      // Remove math delimiters and inline math
      .replace(/\$[^$]*\$/g, '')
      // Remove display math
      .replace(/\\\[[^\]]*\\\]/g, '')
      // Remove special characters
      .replace(/[{}[\]$%&_#~^]/g, '')
      // Normalize whitespace
      .replace(/\s+/g, ' ')
      .trim()
  )
}

/**
 * Dispatch a paragraph change event
 */
function dispatchParagraphChange(
  view: EditorView,
  paragraph: string,
  cursorPosition: number
) {
  const event = new CustomEvent<ParagraphChangeDetail>(
    EVIDENCE_PARAGRAPH_CHANGE_EVENT,
    {
      detail: {
        paragraph,
        cursorPosition,
      },
      bubbles: true,
    }
  )
  view.dom.dispatchEvent(event)
}

/**
 * CodeMirror extension that tracks the current paragraph and emits events
 * when the paragraph changes.
 */
export const evidenceTracker = ViewPlugin.fromClass(
  class {
    private lastParagraph: string = ''
    private debounceTimer: ReturnType<typeof setTimeout> | null = null
    private readonly debounceDelay = PARAGRAPH_CHANGE_DEBOUNCE_MS

    constructor(private view: EditorView) {
      // Initial paragraph detection
      this.checkParagraphChange()
    }

    update(update: ViewUpdate) {
      // Only check on selection changes or document changes
      if (update.selectionSet || update.docChanged) {
        this.scheduleParagraphCheck()
      }
    }

    private scheduleParagraphCheck() {
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer)
      }

      this.debounceTimer = setTimeout(() => {
        this.debounceTimer = null
        this.checkParagraphChange()
      }, this.debounceDelay)
    }

    private checkParagraphChange() {
      const rawParagraph = getCurrentParagraph(this.view.state)
      const cleanedParagraph = cleanLatexForSearch(rawParagraph)

      // Skip if paragraph is blank or hasn't changed
      if (!cleanedParagraph || cleanedParagraph === this.lastParagraph) {
        return
      }

      this.lastParagraph = cleanedParagraph
      dispatchParagraphChange(
        this.view,
        cleanedParagraph,
        this.view.state.selection.main.head
      )
    }

    destroy() {
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer)
      }
    }
  }
)

export default evidenceTracker
