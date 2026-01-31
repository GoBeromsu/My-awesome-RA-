import { expect } from 'chai'
import { screen, fireEvent } from '@testing-library/react'
import sinon from 'sinon'
import React from 'react'

import { EvidenceItem } from '../../../../frontend/js/components/evidence-item'
import { createMockResult } from '../helpers/evidence-providers'
import { renderWithReferencesContext } from '../helpers/references-providers'

describe('<EvidenceItem />', function () {
  let clipboardStub: sinon.SinonStub
  let originalClipboard: Clipboard | undefined

  beforeEach(function () {
    // Save original clipboard (may not exist in JSDOM)
    originalClipboard = navigator.clipboard

    // Mock clipboard API for JSDOM
    const writeTextStub = sinon.stub().resolves()
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: writeTextStub },
      writable: true,
      configurable: true,
    })
    clipboardStub = writeTextStub
  })

  afterEach(function () {
    // Restore original clipboard
    if (originalClipboard !== undefined) {
      Object.defineProperty(navigator, 'clipboard', {
        value: originalClipboard,
        writable: true,
        configurable: true,
      })
    }
    sinon.restore()
  })

  describe('rendering', function () {
    it('displays title, authors, and year', function () {
      const result = createMockResult({
        title: 'Research Paper Title',
        authors: 'Smith, J. and Doe, A.',
        year: 2023,
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      expect(screen.getByText('Research Paper Title')).to.exist
      // New format: "Last Name et al. (Year)" for multiple authors
      expect(screen.getByText('Smith et al. (2023)')).to.exist
    })

    it('displays rank number', function () {
      const result = createMockResult()

      renderWithReferencesContext(<EvidenceItem result={result} rank={3} />)

      expect(screen.getByText('#3')).to.exist
    })

    it('displays authors without year when year is null', function () {
      const result = createMockResult({
        authors: 'Smith, J.',
        year: null,
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      // New format: just last name for single author
      expect(screen.getByText('Smith')).to.exist
    })

    it('displays year without authors when authors is empty', function () {
      const result = createMockResult({
        authors: '',
        year: 2023,
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      expect(screen.getByText('(2023)')).to.exist
    })

    it('has listitem role for accessibility', function () {
      const result = createMockResult()

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      expect(screen.getByRole('listitem')).to.exist
    })
  })

  describe('relevance score display', function () {
    it('shows relevance score as percentage', function () {
      const result = createMockResult({ score: 0.85 })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      expect(screen.getByText('85%')).to.exist
    })

    it('applies high score class for scores >= 80%', function () {
      const result = createMockResult({ score: 0.85 })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const scoreElement = screen.getByText('85%')
      expect(scoreElement.classList.contains('score-high')).to.be.true
    })

    it('applies medium score class for scores 60-79%', function () {
      const result = createMockResult({ score: 0.7 })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const scoreElement = screen.getByText('70%')
      expect(scoreElement.classList.contains('score-medium')).to.be.true
    })

    it('applies low score class for scores < 60%', function () {
      const result = createMockResult({ score: 0.5 })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const scoreElement = screen.getByText('50%')
      expect(scoreElement.classList.contains('score-low')).to.be.true
    })

    it('rounds score percentage to nearest integer', function () {
      const result = createMockResult({ score: 0.876 })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      expect(screen.getByText('88%')).to.exist
    })
  })

  describe('expand/collapse functionality', function () {
    it('starts collapsed by default', function () {
      const result = createMockResult({
        snippet: 'This is the snippet text.',
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      expect(screen.queryByText('This is the snippet text.')).to.not.exist
    })

    it('expands to show full text on click', function () {
      const result = createMockResult({
        snippet: 'This is the snippet text that should appear when expanded.',
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      expect(
        screen.getByText('This is the snippet text that should appear when expanded.')
      ).to.exist
    })

    it('collapses when clicked again', function () {
      const result = createMockResult({
        snippet: 'Snippet text',
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const header = screen.getByText(result.title).closest('.evidence-item-header')!

      // Expand
      fireEvent.click(header)
      expect(screen.getByText('Snippet text')).to.exist

      // Collapse
      fireEvent.click(header)
      expect(screen.queryByText('Snippet text')).to.not.exist
    })

    it('toggles aria-expanded attribute', function () {
      const result = createMockResult()

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const expandButton = screen.getByLabelText('Expand')
      expect(expandButton.getAttribute('aria-expanded')).to.equal('false')

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      const collapseButton = screen.getByLabelText('Collapse')
      expect(collapseButton.getAttribute('aria-expanded')).to.equal('true')
    })

    it('changes expand icon based on state', function () {
      const result = createMockResult()

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      expect(screen.getByLabelText('Expand')).to.exist

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      expect(screen.getByLabelText('Collapse')).to.exist
    })
  })

  describe('expanded details', function () {
    it('displays page number when available', function () {
      const result = createMockResult({ page: 42 })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      expect(screen.getByText('Page 42')).to.exist
    })

    it('does not display page section when page is null', function () {
      const result = createMockResult({ page: null })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      expect(screen.queryByText(/Page/)).to.not.exist
    })

    it('displays source PDF filename', function () {
      const result = createMockResult({
        sourcePdf: '/documents/research-paper.pdf',
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      expect(screen.getByText('research-paper.pdf')).to.exist
    })

    it('does not display source PDF section when empty', function () {
      const result = createMockResult({ sourcePdf: '' })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      // Should not have a source PDF display element
      expect(screen.queryByText('.pdf')).to.not.exist
    })

    it('displays snippet in blockquote', function () {
      const result = createMockResult({
        snippet: 'Important quote from the paper.',
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      const blockquote = screen.getByText('Important quote from the paper.')
        .closest('blockquote')

      expect(blockquote).to.exist
    })
  })

  describe('clipboard functionality', function () {
    it('copies text to clipboard on button click', async function () {
      const result = createMockResult({
        snippet: 'Text to be copied.',
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      const copyButton = screen.getByRole('button', { name: /copy/i })
      fireEvent.click(copyButton)

      expect(clipboardStub.calledOnce).to.be.true
      expect(clipboardStub.calledWith('Text to be copied.')).to.be.true
    })

    it('has copy button with title tooltip', function () {
      const result = createMockResult()

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const header = screen.getByText(result.title).closest('.evidence-item-header')!
      fireEvent.click(header)

      const copyButton = screen.getByRole('button', { name: /copy/i })
      expect(copyButton.getAttribute('title')).to.equal('Copy snippet to clipboard')
    })
  })

  describe('edge cases', function () {
    it('handles very long titles gracefully', function () {
      const longTitle =
        'This is a very long title that might overflow the container and need special handling with ellipsis or truncation'

      const result = createMockResult({ title: longTitle })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      const titleElement = screen.getByText(longTitle)
      expect(titleElement.getAttribute('title')).to.equal(longTitle)
    })

    it('handles score of 0', function () {
      const result = createMockResult({ score: 0 })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      expect(screen.getByText('0%')).to.exist
    })

    it('handles score of 1 (100%)', function () {
      const result = createMockResult({ score: 1 })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      expect(screen.getByText('100%')).to.exist
    })

    it('handles empty authors and null year', function () {
      const result = createMockResult({
        authors: '',
        year: null,
      })

      renderWithReferencesContext(<EvidenceItem result={result} rank={1} />)

      // Citation element should not be rendered when both are empty
      const citationElement = screen.getByText(result.title)
        .closest('.evidence-item-header')
        ?.querySelector('.evidence-item-citation')

      expect(citationElement).to.be.null
    })
  })
})
