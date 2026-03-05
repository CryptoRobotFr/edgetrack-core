import { ChevronDown, Plus, Wallet } from "lucide-react"
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
import { cn } from "@/lib/utils"

export function AccountSelector() {
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
            </>
          )}
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Select Account</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {filteredAccounts.map((account) => (
          <DropdownMenuItem
            key={account.id}
            onClick={() => setSelectedAccountId(account.id)}
            className={cn(
              "flex items-center gap-2 cursor-pointer",
              selectedAccount?.id === account.id && "bg-accent"
            )}
          >
            <Avatar className="h-5 w-5">
              <AvatarImage
                src={account.exchange_avatar_url ?? undefined}
                alt={account.exchange_name}
              />
              <AvatarFallback className="text-[10px]">
                {account.exchange_name.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="flex flex-col">
              <span className="text-sm font-medium">{account.name}</span>
              <span className="text-xs text-muted-foreground">
                {account.exchange_name} · {account.account_type}
              </span>
            </div>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/accounts" className="flex items-center gap-2 cursor-pointer">
            <Plus className="h-4 w-4" />
            <span>Add Account</span>
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
