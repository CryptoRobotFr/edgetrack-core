import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2, Play, Settings, Trash2 } from "lucide-react"
import type { AccountOverviewItem } from "@/hooks/useAccountsOverview"
import { formatUsd, formatRelativeTime } from "@/lib/formatters"
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
import { cn } from "@/lib/utils"
import EditAccountDialog from "./EditAccountDialog"
import DeleteAccountDialog from "./DeleteAccountDialog"

interface AccountCardProps {
  account: AccountOverviewItem
  allAccounts: AccountOverviewItem[]
}

export default function AccountCard({ account, allAccounts }: AccountCardProps) {
  const navigate = useNavigate()
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)

  const needsInitialSync = account.last_sync_date === null && !account.sync_in_progress

  const capitalizeFirst = (s: string) =>
    s.charAt(0).toUpperCase() + s.slice(1)

  const formatProductType = (type: string | null) => {
    if (!type) return ""
    return type
      .split("-")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  }

  return (
    <>
      <Card className="shadow-md flex flex-col h-full relative">
        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
          <div className="flex items-center space-x-4">
            {account.exchange_avatar_url && (
              <img
                src={account.exchange_avatar_url}
                alt={`${account.exchange_name} logo`}
                className="h-10 w-10 rounded-full"
              />
            )}
            <div>
              <CardTitle className="text-lg font-semibold">
                {account.name}
              </CardTitle>
              <CardDescription className="text-sm text-muted-foreground">
                {capitalizeFirst(account.exchange_name)} -{" "}
                {formatProductType(account.product_type) || capitalizeFirst(account.account_type)}
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="relative flex items-center justify-center w-4 h-4 mt-1">
                    <div
                      className={cn(
                        "absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping",
                        account.is_connected ? "bg-green-400" : "bg-red-400"
                      )}
                    />
                    <div
                      className={cn(
                        "relative inline-flex rounded-full h-3 w-3",
                        account.is_connected ? "bg-green-500" : "bg-red-500"
                      )}
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent
                  className={cn(
                    "text-white border-none shadow-md",
                    account.is_connected ? "bg-green-500" : "bg-red-500"
                  )}
                >
                  <p>{account.is_connected ? "Connected" : "Disconnected"}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </CardHeader>

        <CardContent className="space-y-1 pt-0 pb-4 flex-grow">
          <div className="text-sm text-muted-foreground">
            Equity:{" "}
            <span className="text-foreground font-medium">
              {account.equity != null ? formatUsd(account.equity) : "N/A"}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">
            Trades Synced:{" "}
            <span className="text-foreground font-medium">
              {account.total_trades}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">
            Last Sync:{" "}
            {needsInitialSync ? (
              <Button
                variant="link"
                size="sm"
                className="h-auto p-0 text-sm font-medium text-primary"
                onClick={() => navigate(`/accounts/${account.id}/sync`)}
              >
                <Play className="mr-1 h-3 w-3" />
                Start initial sync
              </Button>
            ) : (
              <span className="text-foreground font-medium">
                {account.last_sync_date
                  ? formatRelativeTime(account.last_sync_date)
                  : "Never"}
              </span>
            )}
          </div>
        </CardContent>

        <CardFooter className="flex items-center gap-4 px-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsEditOpen(true)}
            className="flex-1 relative flex items-center justify-center"
          >
            <Settings className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" />
            Edit
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setIsDeleteOpen(true)}
            className="flex-1 relative flex items-center justify-center"
          >
            <Trash2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" />
            Delete
          </Button>
        </CardFooter>

        {account.sync_in_progress && (
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center rounded-lg z-10">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        )}
      </Card>

      <EditAccountDialog
        account={account}
        open={isEditOpen}
        onOpenChange={setIsEditOpen}
      />
      <DeleteAccountDialog
        account={account}
        allAccounts={allAccounts}
        open={isDeleteOpen}
        onOpenChange={setIsDeleteOpen}
      />
    </>
  )
}
