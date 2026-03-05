import { useState } from "react"
import { Trash2 } from "lucide-react"
import type { components } from "@/api/schema"
import { formatRelativeTime } from "@/lib/formatters"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import DeleteApiKeyDialog from "./DeleteApiKeyDialog"

type ApiKeyResponse = components["schemas"]["ApiKeyResponse"]

const EXCHANGE_AVATARS: Record<string, string> = {
  bitget: "https://www.bitget.com/favicon.ico",
  bitmart: "https://www.bitmart.com/favicon.ico",
  hyperliquid: "https://assets.coingecko.com/markets/images/1208/standard/Hyperliquid_logo.png?1706865217",
}

interface ApiKeyCardProps {
  apiKey: ApiKeyResponse
}

function maskKey(key: string): string {
  if (key.length <= 8) return key
  return `${key.substring(0, 4)}...${key.substring(key.length - 4)}`
}

function capitalizeFirst(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export default function ApiKeyCard({ apiKey }: ApiKeyCardProps) {
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const isLinked = apiKey.accounts_count > 0

  return (
    <>
      <Card className="shadow-md flex flex-col h-full">
        <CardHeader className="pb-3">
          <div className="flex items-center space-x-4">
            {EXCHANGE_AVATARS[apiKey.exchange_name] && (
              <img
                src={EXCHANGE_AVATARS[apiKey.exchange_name]}
                alt={`${apiKey.exchange_name} logo`}
                className="h-10 w-10 rounded-full"
              />
            )}
            <div>
              <CardTitle className="text-lg font-semibold">
                {apiKey.name}
              </CardTitle>
              <CardDescription className="text-sm text-muted-foreground">
                {capitalizeFirst(apiKey.exchange_name)}
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-1 pt-0 pb-4 flex-grow">
          <div className="text-sm text-muted-foreground">
            Public Key:{" "}
            <span className="text-foreground font-mono font-medium">
              {maskKey(apiKey.public_key)}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">
            Linked Accounts:{" "}
            <span className="text-foreground font-medium">
              {apiKey.accounts_count} account{apiKey.accounts_count !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">
            Created:{" "}
            <span className="text-foreground font-medium">
              {formatRelativeTime(apiKey.created_at)}
            </span>
          </div>
        </CardContent>

        <CardFooter className="px-4">
          {isLinked ? (
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="w-full">
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled
                      className="w-full relative flex items-center justify-center"
                    >
                      <Trash2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" />
                      Delete
                    </Button>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p>
                    This key is linked to {apiKey.accounts_count} account{apiKey.accounts_count !== 1 ? "s" : ""}. Remove the account{apiKey.accounts_count !== 1 ? "s" : ""} first.
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          ) : (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setIsDeleteOpen(true)}
              className="w-full relative flex items-center justify-center"
            >
              <Trash2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" />
              Delete
            </Button>
          )}
        </CardFooter>
      </Card>

      <DeleteApiKeyDialog
        apiKey={apiKey}
        open={isDeleteOpen}
        onOpenChange={setIsDeleteOpen}
      />
    </>
  )
}
