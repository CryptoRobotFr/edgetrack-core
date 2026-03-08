import { Share2 } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface ShareCardProps {
  onShare: () => void
  disabled?: boolean
}

export function ShareCard({ onShare, disabled }: ShareCardProps) {
  return (
    <Card>
      <CardContent className="p-4">
        <Button className="w-full gap-2" size="lg" onClick={onShare} disabled={disabled}>
          <Share2 className="h-4 w-4" />
          Share Trade
        </Button>
      </CardContent>
    </Card>
  )
}
