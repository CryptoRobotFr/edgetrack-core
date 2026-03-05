import { useCallback, useEffect, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface SyncStatus {
  lastSyncDate: number | null
  syncInProgress: boolean
  hasInitialSync: boolean
}

interface SyncStatusResponse {
  last_sync_date: number | null
  sync_in_progress: boolean
  has_initial_sync: boolean
}

export interface UseSyncStatusReturn {
  status: SyncStatus | null
  isLoading: boolean
  error: Error | null
  triggerSync: (mode: "sync" | "sync-bg") => Promise<void>
  isSyncing: boolean
  pollForCompletion: () => void
  stopPolling: () => void
}

export function useSyncStatus(accountId: string | null): UseSyncStatusReturn {
  const queryClient = useQueryClient()
  const [isPolling, setIsPolling] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const prevSyncInProgressRef = useRef<boolean | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ["futures", "sync-status", accountId],
    queryFn: async () => {
      if (!accountId) {
        throw new Error("No account selected")
      }
      const response = await authApi.GET(
        "/api/v1/futures/sync/status",
        {
          params: {
            query: {
              account_id: accountId,
            },
          },
        }
      )
      if (response.error) {
        throw new Error("Failed to fetch sync status")
      }
      const raw = response.data as unknown as SyncStatusResponse
      return {
        lastSyncDate: raw.last_sync_date,
        syncInProgress: raw.sync_in_progress,
        hasInitialSync: raw.has_initial_sync,
      } as SyncStatus
    },
    enabled: !!accountId,
    refetchInterval: isPolling ? 5_000 : false,
    refetchIntervalInBackground: false,
  })

  // Detect sync completion: syncInProgress transitions from true to false
  useEffect(() => {
    if (!data) return

    const prev = prevSyncInProgressRef.current
    if (prev === true && data.syncInProgress === false) {
      // Sync just completed - invalidate all futures queries
      queryClient.invalidateQueries({ queryKey: ["futures"] })
      setIsPolling(false)
      setIsSyncing(false)
    }

    prevSyncInProgressRef.current = data.syncInProgress
  }, [data, queryClient])

  const triggerSync = useCallback(
    async (mode: "sync" | "sync-bg") => {
      if (!accountId) return
      setIsSyncing(true)

      const endpoint =
        mode === "sync"
          ? "/api/v1/futures/sync"
          : "/api/v1/futures/sync-bg"

      try {
        const response = await authApi.POST(
          endpoint,
          {
            body: {
              account_id: accountId,
            },
          }
        )

        if (response.error) {
          const errorData = response.error as { detail?: string }
          // 409 = sync already in progress, just start polling
          if (response.response?.status === 409) {
            prevSyncInProgressRef.current = true
            setIsPolling(true)
            return
          }
          throw new Error(errorData.detail || "Failed to trigger sync")
        }

        if (mode === "sync") {
          // Synchronous sync completed - invalidate caches
          queryClient.invalidateQueries({ queryKey: ["futures"] })
          setIsSyncing(false)
        } else {
          // Background sync started - start polling for completion
          // Set prev to true so that when the next poll sees sync_in_progress=false,
          // it detects the true→false transition (even if sync completes before first poll)
          prevSyncInProgressRef.current = true
          setIsPolling(true)
        }
      } catch (err) {
        setIsSyncing(false)
        throw err
      }
    },
    [accountId, queryClient]
  )

  const pollForCompletion = useCallback(() => {
    prevSyncInProgressRef.current = true
    setIsPolling(true)
  }, [])

  const stopPolling = useCallback(() => {
    setIsPolling(false)
  }, [])

  return {
    status: data ?? null,
    isLoading,
    error: error as Error | null,
    triggerSync,
    isSyncing,
    pollForCompletion,
    stopPolling,
  }
}
