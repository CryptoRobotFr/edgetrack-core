import { useEffect, useRef, useState } from "react"
import { Navigate, Outlet } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { DemoBanner } from "@/components/DemoBanner"
import { useAccount } from "@/contexts/AccountContext"
import { useSyncStatus } from "@/hooks/useSyncStatus"

const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000

function RedirectToAccounts() {
  useEffect(() => {
    toast.info("Please create an account first to access this page.")
  }, [])
  return <Navigate to="/accounts" replace />
}

export default function FuturesLayout() {
  const { selectedAccountId, selectedAccount, isLoading: isAccountsLoading } = useAccount()
  const isDemo = selectedAccount?.is_demo === true
  const { status, isLoading, triggerSync, isSyncing, pollForCompletion } =
    useSyncStatus(isDemo ? null : selectedAccountId)
  const [blockingSync, setBlockingSync] = useState(false)
  const [blockingSyncError, setBlockingSyncError] = useState<string | null>(null)
  const syncTriggeredRef = useRef(false)

  // Determine freshness once status is available
  const isStale =
    status &&
    status.hasInitialSync &&
    (status.lastSyncDate === null ||
      Date.now() - status.lastSyncDate > TWENTY_FOUR_HOURS_MS)

  const isFresh =
    status &&
    status.hasInitialSync &&
    status.lastSyncDate !== null &&
    Date.now() - status.lastSyncDate <= TWENTY_FOUR_HOURS_MS

  // Trigger sync based on freshness (once per mount/account change)
  useEffect(() => {
    if (!status || isLoading || syncTriggeredRef.current) return

    // Already syncing elsewhere
    if (status.syncInProgress) {
      pollForCompletion()
      syncTriggeredRef.current = true
      return
    }

    if (!status.hasInitialSync) return

    if (isStale) {
      // >24h stale: blocking synchronous sync
      syncTriggeredRef.current = true
      setBlockingSync(true)
      setBlockingSyncError(null)
      triggerSync("sync")
        .then(() => {
          setBlockingSync(false)
        })
        .catch((err: Error) => {
          setBlockingSync(false)
          setBlockingSyncError(err.message)
        })
    } else if (isFresh) {
      // <24h: background sync, render children immediately
      syncTriggeredRef.current = true
      triggerSync("sync-bg").catch(() => {
        // Background sync failure is not critical
      })
    }
  }, [status, isLoading, isStale, isFresh, triggerSync, pollForCompletion])

  // Reset trigger ref when account changes
  useEffect(() => {
    syncTriggeredRef.current = false
    setBlockingSync(false)
    setBlockingSyncError(null)
  }, [selectedAccountId])

  // Wait for accounts to load before deciding
  if (isAccountsLoading && !selectedAccountId) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // No account selected — redirect to accounts page
  if (!selectedAccountId) {
    return <RedirectToAccounts />
  }

  // Demo accounts: skip all sync logic, render content directly
  if (isDemo) {
    return (
      <>
        <DemoBanner />
        <Outlet />
      </>
    )
  }

  // Loading sync status
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // No initial sync yet
  if (status && !status.hasInitialSync) {
    // Sync is running in background (e.g. user clicked "Continue in background")
    // Show a waiting UI instead of redirecting to sync page (which would error)
    if (status.syncInProgress) {
      return (
        <div className="flex flex-col items-center justify-center py-24">
          <Loader2 className="h-10 w-10 animate-spin text-primary mb-4" />
          <p className="text-lg font-medium text-foreground">
            Initial sync in progress...
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Data will appear once synchronization is complete
          </p>
        </div>
      )
    }
    // No sync running - redirect to sync page to start one
    return <Navigate to={`/accounts/${selectedAccountId}/sync`} replace />
  }

  // Blocking sync in progress (>24h stale)
  if (blockingSync) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <Loader2 className="h-10 w-10 animate-spin text-primary mb-4" />
        <p className="text-lg font-medium text-foreground">
          Synchronization in progress...
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          Fetching latest trading data from exchange
        </p>
      </div>
    )
  }

  // Blocking sync error
  if (blockingSyncError) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <p className="text-lg font-medium text-destructive">
          Sync failed
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {blockingSyncError}
        </p>
      </div>
    )
  }

  // Render children with optional background sync indicator
  return (
    <>
      {isSyncing && (
        <div className="flex items-center gap-2 px-4 py-1.5 text-xs text-muted-foreground bg-muted/50 border-b">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Syncing...</span>
        </div>
      )}
      <Outlet />
    </>
  )
}
