import { useEffect, useRef, useCallback, useState } from "react"
import { Copy, Download, Loader2 } from "lucide-react"
import { toast } from "sonner"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { useShareImage } from "./useShareImage"
import { getExchangeIconDataUrl } from "./exchange-icons"

interface ShareDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  cardComponent: React.ForwardRefExoticComponent<any>
  cardProps: Record<string, unknown>
  exchangeName: string
  filenamePrefix?: string
  showPnlToggle?: boolean
}

const CAPTURE_DELAY_MS = 600

const SHARE_TEXT = "Check out my trading performance on EdgeTrack!"

function XIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  )
}

function DiscordIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
    </svg>
  )
}

function TelegramIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  )
}

export function ShareDialog({ open, onOpenChange, cardComponent: CardComponent, cardProps, exchangeName, filenamePrefix = "edgetrack", showPnlToggle = false }: ShareDialogProps) {
  const cardRef = useRef<HTMLDivElement>(null)
  const { capture, imageBlob, imageUrl, isCapturing, reset } = useShareImage()
  const [showUsdPnl, setShowUsdPnl] = useState(false)

  // Get exchange icon as inline base64 data URL (no CORS/loading issues)
  const iconDataUrl = getExchangeIconDataUrl(exchangeName)

  // Stable key from cardProps to detect when data changes (e.g. coin image loaded)
  const cardPropsKey = JSON.stringify(cardProps)

  // Capture image when dialog opens, toggle changes, or card data updates
  useEffect(() => {
    if (!open) {
      reset()
      setShowUsdPnl(false)
      return
    }

    let cancelled = false

    async function prepare() {
      // Wait for ECharts render + images to load, then capture
      await new Promise((r) => setTimeout(r, CAPTURE_DELAY_MS))
      if (!cancelled && cardRef.current) {
        capture(cardRef.current)
      }
    }

    prepare()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, showUsdPnl, cardPropsKey, capture, reset])

  const handleCopy = useCallback(async () => {
    if (!imageBlob) return
    try {
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": imageBlob }),
      ])
      toast.success("Image copied to clipboard")
    } catch {
      toast.error("Failed to copy image to clipboard")
    }
  }, [imageBlob])

  const handleDownload = useCallback(() => {
    if (!imageUrl) return
    const date = new Date().toISOString().split("T")[0]
    const a = document.createElement("a")
    a.href = imageUrl
    a.download = `${filenamePrefix}-${date}.png`
    a.click()
  }, [imageUrl])

  const handleShareX = useCallback(async () => {
    if (!imageBlob) return
    try {
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": imageBlob }),
      ])
      toast.success("Image copied — paste it in your post on X with Ctrl+V")
    } catch {
      toast.error("Failed to copy image to clipboard")
    }
    window.open(
      `https://x.com/intent/post?text=${encodeURIComponent(SHARE_TEXT)}`,
      "_blank",
      "noopener,noreferrer"
    )
  }, [imageBlob])

  const handleShareDiscord = useCallback(async () => {
    if (!imageBlob) return
    try {
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": imageBlob }),
      ])
      toast.success("Image copied — paste it in Discord with Ctrl+V")
    } catch {
      toast.error("Failed to copy image to clipboard")
    }
  }, [imageBlob])

  const handleShareTelegram = useCallback(async () => {
    if (!imageBlob) return
    try {
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": imageBlob }),
      ])
      toast.success("Image copied — paste it in Telegram with Ctrl+V")
    } catch {
      // Clipboard not available
    }
    window.open(
      `https://t.me/share/url?url=${encodeURIComponent("https://edge-track.com")}&text=${encodeURIComponent(SHARE_TEXT)}`,
      "_blank",
      "noopener,noreferrer"
    )
  }, [imageBlob])

  const imageReady = !!imageUrl && !isCapturing

  // Use inline base64 icon for the share card (zero network requests)
  const mergedCardProps = { ...cardProps, exchangeAvatarDataUrl: iconDataUrl, ...(showPnlToggle ? { showUsdPnl } : {}) }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Share your performance</DialogTitle>
          <DialogDescription>
            Download or share your trading performance image
          </DialogDescription>
        </DialogHeader>

        {/* Off-screen render target for image capture */}
        <div
          style={{
            position: "absolute",
            left: -9999,
            top: 0,
            overflow: "hidden",
          }}
          aria-hidden="true"
        >
          <CardComponent ref={cardRef} {...mergedCardProps} />
        </div>

        {/* PnL display toggle */}
        {showPnlToggle && (
          <div className="flex items-center gap-2">
            <Checkbox
              id="show-usd-pnl"
              checked={showUsdPnl}
              onCheckedChange={(checked) => setShowUsdPnl(checked === true)}
            />
            <Label htmlFor="show-usd-pnl" className="text-sm cursor-pointer">
              Show P&L in USD
            </Label>
          </div>
        )}

        {/* Preview with download icon overlay */}
        <div className="relative flex items-center justify-center min-h-[400px]">
          {!imageReady ? (
            <div className="flex flex-col items-center gap-3 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin" />
              <span className="text-sm">Generating image...</span>
            </div>
          ) : (
            <>
              <img
                src={imageUrl}
                alt="Share preview"
                className="w-full rounded-lg border"
              />
              <div className="absolute top-3 right-3 flex gap-2">
                <button
                  onClick={handleCopy}
                  className="flex h-9 w-9 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm transition-colors hover:bg-black/80"
                  aria-label="Copy image"
                >
                  <Copy className="h-4 w-4" />
                </button>
                <button
                  onClick={handleDownload}
                  className="flex h-9 w-9 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm transition-colors hover:bg-black/80"
                  aria-label="Download image"
                >
                  <Download className="h-4 w-4" />
                </button>
              </div>
            </>
          )}
        </div>

        {/* Social share links */}
        {imageReady && (
          <div className="flex items-center justify-center gap-3">
            <Button
              variant="outline"
              size="lg"
              className="gap-2"
              onClick={handleShareX}
            >
              <XIcon className="h-4 w-4" />
              Post on X
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="gap-2"
              onClick={handleShareDiscord}
            >
              <DiscordIcon className="h-4 w-4" />
              Discord
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="gap-2"
              onClick={handleShareTelegram}
            >
              <TelegramIcon className="h-4 w-4" />
              Telegram
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
