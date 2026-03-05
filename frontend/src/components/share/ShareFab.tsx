import { useState } from "react"
import { createPortal } from "react-dom"
import { Share2 } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ShareDialog } from "./ShareDialog"

interface ShareFabProps {
  cardComponent: React.ForwardRefExoticComponent<any>
  cardProps: Record<string, unknown>
  exchangeName: string
  filenamePrefix?: string
}

export function ShareFab({ cardComponent, cardProps, exchangeName, filenamePrefix }: ShareFabProps) {
  const [dialogOpen, setDialogOpen] = useState(false)

  const fab = (
    <>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={() => setDialogOpen(true)}
              className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              aria-label="Share performance"
            >
              <Share2 className="h-4 w-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="left">
            <p>Share performance</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <ShareDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        cardComponent={cardComponent}
        cardProps={cardProps}
        exchangeName={exchangeName}
        filenamePrefix={filenamePrefix}
      />
    </>
  )

  return createPortal(fab, document.body)
}
