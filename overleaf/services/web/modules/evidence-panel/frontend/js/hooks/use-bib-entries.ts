import { useMemo, useCallback, useState, useEffect } from 'react'
import { useFileTreeData } from '@/shared/context/file-tree-data-context'

export interface BibEntry {
  citeKey: string
  title?: string
  authors?: string
  year?: string
  hasPdf: boolean
  pdfFileId?: string
  pdfFilename?: string
}

interface FileEntity {
  _id: string
  name: string
  type?: string
}

interface FolderEntity {
  _id: string
  name: string
  folders?: FolderEntity[]
  docs?: FileEntity[]
  fileRefs?: FileEntity[]
}

/**
 * Recursively find all files matching a predicate in the file tree
 */
function findFilesInTree(
  folder: FolderEntity | null,
  predicate: (file: FileEntity) => boolean
): Array<FileEntity & { folderId: string }> {
  if (!folder) return []

  const results: Array<FileEntity & { folderId: string }> = []

  // Check fileRefs (uploaded files like PDFs)
  if (folder.fileRefs) {
    for (const file of folder.fileRefs) {
      if (predicate(file)) {
        results.push({ ...file, folderId: folder._id })
      }
    }
  }

  // Recursively check subfolders
  if (folder.folders) {
    for (const subfolder of folder.folders) {
      results.push(...findFilesInTree(subfolder, predicate))
    }
  }

  return results
}

/**
 * Match a PDF filename to a cite key (case-insensitive)
 */
function matchPdfToCiteKey(
  pdfFilename: string,
  citeKeys: string[]
): string | null {
  const baseName = pdfFilename.replace(/\.pdf$/i, '').toLowerCase()
  return citeKeys.find(key => key.toLowerCase() === baseName) || null
}

/**
 * Hook to get bib entries from project .bib files with PDF matching
 *
 * Uses Overleaf's file tree to find .bib and .pdf files,
 * then matches PDFs to cite keys by filename convention.
 */
export function useBibEntries(referenceKeys: Set<string>) {
  const { fileTreeData } = useFileTreeData()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Find all PDF files in the project
  const pdfFiles = useMemo(() => {
    if (!fileTreeData) return []
    return findFilesInTree(fileTreeData, file =>
      file.name.toLowerCase().endsWith('.pdf')
    )
  }, [fileTreeData])

  // Build bib entries from reference keys with PDF matching
  const bibEntries = useMemo<BibEntry[]>(() => {
    if (!referenceKeys || referenceKeys.size === 0) {
      return []
    }

    const citeKeyArray = Array.from(referenceKeys)

    // Create a map of lowercase cite keys to PDF files
    const pdfMap = new Map<string, (typeof pdfFiles)[0]>()
    for (const pdf of pdfFiles) {
      const matchedKey = matchPdfToCiteKey(pdf.name, citeKeyArray)
      if (matchedKey) {
        pdfMap.set(matchedKey.toLowerCase(), pdf)
      }
    }

    // Build entries for each cite key
    return citeKeyArray.map(citeKey => {
      const pdf = pdfMap.get(citeKey.toLowerCase())
      return {
        citeKey,
        hasPdf: !!pdf,
        pdfFileId: pdf?._id,
        pdfFilename: pdf?.name,
      }
    }).sort((a, b) => a.citeKey.localeCompare(b.citeKey))
  }, [referenceKeys, pdfFiles])

  // Effect to update loading state
  useEffect(() => {
    setIsLoading(false)
    setError(null)
  }, [bibEntries])

  // Refresh function (triggers re-read of file tree)
  const refresh = useCallback(() => {
    setIsLoading(true)
    // The file tree data will update automatically via context
    // This is mainly for UI feedback
    setTimeout(() => setIsLoading(false), 100)
  }, [])

  return {
    bibEntries,
    pdfFiles,
    isLoading,
    error,
    refresh,
  }
}

export default useBibEntries
