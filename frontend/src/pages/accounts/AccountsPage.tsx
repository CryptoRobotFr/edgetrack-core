import { useState } from "react"
import { RefreshCw } from "lucide-react"
import { useAccountsOverview } from "@/hooks/useAccountsOverview"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import AccountCard from "./components/AccountCard"
import NewAccountCard from "./components/NewAccountCard"
import WelcomeCard from "./components/WelcomeCard"
import CreateAccountDialog from "./components/CreateAccountDialog"

function LoadingSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <Skeleton key={i} className="h-[220px] rounded-lg" />
      ))}
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <p className="text-destructive text-lg font-medium">Failed to load accounts</p>
      <p className="mt-1 text-muted-foreground text-sm">{message}</p>
    </div>
  )
}

export default function AccountsPage() {
  const { data: accounts, isLoading, error, refetch, isFetching } = useAccountsOverview()
  const [dialogOpen, setDialogOpen] = useState(false)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Accounts</h1>
          <p className="mt-1 text-muted-foreground">
            Manage your exchange accounts and API keys
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {isLoading && <LoadingSkeleton />}
      {error && <ErrorState message={(error as Error).message} />}
      {!isLoading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {accounts?.length === 0 && <WelcomeCard onLinkAccount={() => setDialogOpen(true)} />}
          {accounts?.map((account) => (
            <AccountCard key={account.id} account={account} allAccounts={accounts} />
          ))}
          <NewAccountCard onLinkAccount={() => setDialogOpen(true)} />
        </div>
      )}

      <CreateAccountDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  )
}
