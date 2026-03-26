import { Info } from "lucide-react"
import { Link } from "react-router-dom"
import { useAccount } from "@/contexts/AccountContext"

/**
 * Banner displayed on all pages when the demo account is selected.
 * Renders nothing if the selected account is not a demo account.
 */
export function DemoBanner() {
  const { isDemoSelected } = useAccount()

  if (!isDemoSelected) return null

  return (
    <div className="flex items-center gap-2 px-4 py-2 text-sm bg-primary/5 border-b border-primary/10 text-muted-foreground">
      <Info className="h-4 w-4 text-primary shrink-0" />
      <p>
        You are viewing the demo account with sample data.{" "}
        <Link
          to="/accounts"
          className="text-primary font-medium hover:underline underline-offset-2"
        >
          Connect your own trading account
        </Link>
        {" "}to unlock the full potential of EdgeTrack.
      </p>
    </div>
  )
}
