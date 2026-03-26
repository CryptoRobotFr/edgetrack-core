import { ChevronDown, Crown, Plus, Wallet } from "lucide-react"
import { Link } from "react-router-dom"
import { useAccount } from "@/contexts/AccountContext"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

interface AccountSelectorProps {
  disabledAccountIds?: string[]
  disabledTooltip?: string
}

export function AccountSelector({ disabledAccountIds, disabledTooltip }: AccountSelectorProps = {}) {
  const {
    filteredAccounts,
    selectedAccount,
    setSelectedAccountId,
    isLoading,
    showSelector,
  } = useAccount()

  // Don't render if selector should be hidden on this route
  if (!showSelector) return null

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center gap-2">
        <Skeleton className="h-5 w-5 rounded-full" />
        <Skeleton className="h-4 w-24" />
      </div>
    )
  }

  // No accounts available
  if (filteredAccounts.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Wallet className="h-4 w-4" />
        <span>No accounts</span>
      </div>
    )
  }

  return (
    <TooltipProvider delayDuration={0}>
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="flex items-center gap-2 px-3 h-9 bg-white dark:bg-white/10 hover:bg-white/80 dark:hover:bg-white/15 border border-border"
        >
          {selectedAccount && (
            <>
              <Avatar className="h-5 w-5">
                <AvatarImage
                  src={selectedAccount.exchange_avatar_url ?? undefined}
                  alt={selectedAccount.exchange_name}
                />
                <AvatarFallback className="text-[10px]">
                  {selectedAccount.exchange_name.slice(0, 2).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <span className="text-sm font-medium">{selectedAccount.name}</span>
              {selectedAccount.is_demo && (
                <span className="text-[10px] font-semibold bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                  Demo
                </span>
              )}
            </>
          )}
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>Select Account</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {filteredAccounts.map((account) => {
          const isDisabled = disabledAccountIds?.includes(account.id) ?? false

          const item = (
            <DropdownMenuItem
              key={account.id}
              onClick={() => !isDisabled && setSelectedAccountId(account.id)}
              disabled={isDisabled}
              className={cn(
                "flex items-center gap-2",
                !isDisabled && "cursor-pointer",
                selectedAccount?.id === account.id && "bg-accent",
                isDisabled && "opacity-50 cursor-default"
              )}
            >
              <Avatar className="h-5 w-5 shrink-0">
                <AvatarImage
                  src={account.exchange_avatar_url ?? undefined}
                  alt={account.exchange_name}
                />
                <AvatarFallback className="text-[10px]">
                  {account.exchange_name.slice(0, 2).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium truncate">{account.name}</span>
                  {account.is_demo && (
                    <span className="text-[10px] font-semibold bg-primary/10 text-primary px-1.5 py-0.5 rounded shrink-0">
                      Demo
                    </span>
                  )}
                </div>
                <span className="text-xs text-muted-foreground">
                  {account.exchange_name} · {account.account_type}
                </span>
              </div>
              {isDisabled && (
                <Crown className="h-3.5 w-3.5 text-premium shrink-0" />
              )}
            </DropdownMenuItem>
          )

          if (isDisabled) {
            return (
              <Tooltip key={account.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div>{item}</div>
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-[200px]">
                  <p className="font-medium">{disabledTooltip || "Premium feature"}</p>
                  <p className="text-xs text-muted-foreground">This page requires a premium subscription to use with real accounts.</p>
                </TooltipContent>
              </Tooltip>
            )
          }

          return item
        })}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/accounts" className="flex items-center gap-2 cursor-pointer">
            <Plus className="h-4 w-4" />
            <span>Add Account</span>
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    </TooltipProvider>
  )
}
