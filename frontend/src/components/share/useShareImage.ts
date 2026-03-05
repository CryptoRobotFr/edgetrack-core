import { useState, useCallback, useRef } from "react"
import { toBlob } from "html-to-image"

interface UseShareImageReturn {
  capture: (element: HTMLDivElement) => Promise<void>
  imageBlob: Blob | null
  imageUrl: string | null
  isCapturing: boolean
  reset: () => void
}

export function useShareImage(): UseShareImageReturn {
  const [imageBlob, setImageBlob] = useState<Blob | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [isCapturing, setIsCapturing] = useState(false)
  const urlRef = useRef<string | null>(null)

  const reset = useCallback(() => {
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
    setImageBlob(null)
    setImageUrl(null)
    setIsCapturing(false)
  }, [])

  const capture = useCallback(async (element: HTMLDivElement) => {
    setIsCapturing(true)
    try {
      // Wait for fonts to be ready
      await document.fonts.ready

      const blob = await toBlob(element, {
        width: 1080,
        height: 1080,
        pixelRatio: 1,
        skipAutoScale: true,
      })

      if (blob) {
        // Revoke previous URL if any
        if (urlRef.current) {
          URL.revokeObjectURL(urlRef.current)
        }
        const url = URL.createObjectURL(blob)
        urlRef.current = url
        setImageBlob(blob)
        setImageUrl(url)
      }
    } finally {
      setIsCapturing(false)
    }
  }, [])

  return { capture, imageBlob, imageUrl, isCapturing, reset }
}
