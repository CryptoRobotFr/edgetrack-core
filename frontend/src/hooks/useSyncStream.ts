import { useCallback, useEffect, useRef, useState } from "react"
import { getAccessToken } from "@/api/client"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"

/** Sync progress event types from backend */
export type SyncEventType =
  | "started"
  | "validating"
  | "equity_fetching"
  | "equity_calculated"
  | "positions_fetched"
  | "orders_progress"
  | "orders_fetched"
  | "grouping"
  | "trades_built"
  | "ohlcv_fetching"
  | "ohlcv_fetched"
  | "funding_fetching"
  | "funding_fetched"
  | "daily_pnl_calculating"
  | "daily_pnl_calculated"
  | "saving"
  | "completed"
  | "error"
  | "heartbeat"
  // Live feed progress events (granular streaming)
  | "ledger_progress"
  | "orders_item_progress"
  | "ohlcv_progress"
  | "funding_progress"

/** Live feed item types */
export interface LedgerFeedItem {
  date: number
  type: string
  amount: string // Decimal as string
  coin: string
}

export interface OrderFeedItem {
  date: number
  pair: string
  side: string
  size: string // Decimal as string
  price: string // Decimal as string
}

export interface OhlcvFeedItem {
  pair: string
  timestamp: number
  close: string // Decimal as string
}

export interface FundingFeedItem {
  pair: string
  timestamp: number
  rate: string // Decimal as string
}

/** Sync progress event from SSE stream */
export interface SyncProgressEvent {
  event_type: SyncEventType
  message: string
  sync_id?: string
  orders_fetched?: number
  positions_count?: number
  trades_count?: number
  pairs_processed?: string[]
  candles_fetched?: number
  funding_rates_fetched?: number
  daily_pnl_records?: number
  equity_records?: number
  error_message?: string
  // Live feed data
  ledger_items?: LedgerFeedItem[]
  order_items?: OrderFeedItem[]
  ohlcv_items?: OhlcvFeedItem[]
  funding_items?: FundingFeedItem[]
}

/** System message for frontend-generated waiting messages */
export interface SystemFeedItem {
  message: string
}

/** Unified feed item for the single console */
export interface UnifiedFeedItem {
  id: string
  timestamp: number
  type: "ledger" | "orders" | "ohlcv" | "funding" | "system"
  data: LedgerFeedItem | OrderFeedItem | OhlcvFeedItem | FundingFeedItem | SystemFeedItem
}

/** Live feed state for streaming data */
export interface LiveFeedState {
  ledger: LedgerFeedItem[]
  orders: OrderFeedItem[]
  ohlcv: OhlcvFeedItem[]
  funding: FundingFeedItem[]
}

/** Maximum items to keep in unified feed */
const MAX_FEED_ITEMS = 50

/** Current state of the sync process */
export interface SyncState {
  status: "idle" | "connecting" | "syncing" | "completed" | "error"
  currentStep: SyncEventType | null
  syncId: string | null
  positionsCount: number
  ordersFetched: number
  tradesCount: number
  pairsProcessed: string[]
  candlesFetched: number
  fundingRatesFetched: number
  dailyPnlRecords: number
  equityRecords: number
  errorMessage: string | null
  events: SyncProgressEvent[]
  liveFeed: LiveFeedState
  unifiedFeed: UnifiedFeedItem[]
}

const initialLiveFeed: LiveFeedState = {
  ledger: [],
  orders: [],
  ohlcv: [],
  funding: [],
}

const initialState: SyncState = {
  status: "idle",
  currentStep: null,
  syncId: null,
  positionsCount: 0,
  ordersFetched: 0,
  tradesCount: 0,
  pairsProcessed: [],
  candlesFetched: 0,
  fundingRatesFetched: 0,
  dailyPnlRecords: 0,
  equityRecords: 0,
  errorMessage: null,
  events: [],
  liveFeed: initialLiveFeed,
  unifiedFeed: [],
}

/** Counter for generating unique feed item IDs */
let feedItemCounter = 0

interface UseSyncStreamOptions {
  accountId: string
  startDate?: number
  endDate?: number
  autoStart?: boolean
}

interface UseSyncStreamResult {
  state: SyncState
  start: () => void
  reset: () => void
  detach: () => void
  pushSystemMessage: (message: string) => void
}

/**
 * Custom hook for handling SSE sync stream.
 * Uses fetch with ReadableStream to support Authorization header.
 */
export function useSyncStream({
  accountId,
  startDate,
  endDate,
  autoStart = false,
}: UseSyncStreamOptions): UseSyncStreamResult {
  const [state, setState] = useState<SyncState>(initialState)
  const abortControllerRef = useRef<AbortController | null>(null)
  // Track if sync is currently running (not just started)
  const isRunningRef = useRef(false)

  const pushSystemMessage = useCallback((message: string) => {
    setState((prev) => {
      const item: UnifiedFeedItem = {
        id: `system-${feedItemCounter++}`,
        timestamp: Date.now(),
        type: "system",
        data: { message },
      }
      return {
        ...prev,
        unifiedFeed: [...prev.unifiedFeed, item].slice(-MAX_FEED_ITEMS),
      }
    })
  }, [])

  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setState(initialState)
    isRunningRef.current = false
  }, [])

  const start = useCallback(async () => {
    // Prevent multiple concurrent syncs
    if (isRunningRef.current) {
      return
    }
    isRunningRef.current = true

    // Abort any existing connection
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    const abortController = new AbortController()
    abortControllerRef.current = abortController

    setState((prev) => ({
      ...prev,
      status: "connecting",
      currentStep: null,
      errorMessage: null,
      events: [],
    }))

    const token = getAccessToken()
    if (!token) {
      setState((prev) => ({
        ...prev,
        status: "error",
        errorMessage: "Not authenticated",
      }))
      isRunningRef.current = false
      return
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/futures/sync/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          account_id: accountId,
          start_date: startDate,
          end_date: endDate,
        }),
        signal: abortController.signal,
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorText}`)
      }

      if (!response.body) {
        throw new Error("No response body")
      }

      setState((prev) => ({ ...prev, status: "syncing" }))

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events from buffer
        const lines = buffer.split("\n")
        buffer = lines.pop() || "" // Keep incomplete line in buffer

        let currentEventType: string | null = null
        let currentData: string | null = null

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEventType = line.slice(7).trim()
          } else if (line.startsWith("data: ")) {
            currentData = line.slice(6).trim()
          } else if (line === "" && currentEventType && currentData) {
            // End of event, process it
            try {
              const event = JSON.parse(currentData) as SyncProgressEvent

              // Skip heartbeats
              if (event.event_type === "heartbeat") {
                currentEventType = null
                currentData = null
                continue
              }

              setState((prev) => {
                const newState: SyncState = {
                  ...prev,
                  currentStep: event.event_type,
                  events: [...prev.events, event],
                  liveFeed: { ...prev.liveFeed },
                  unifiedFeed: [...prev.unifiedFeed],
                }

                // Update specific fields based on event type
                if (event.sync_id) {
                  newState.syncId = event.sync_id
                }
                if (event.positions_count !== undefined) {
                  newState.positionsCount = event.positions_count
                }
                if (event.orders_fetched !== undefined) {
                  newState.ordersFetched = event.orders_fetched
                }
                if (event.trades_count !== undefined) {
                  newState.tradesCount = event.trades_count
                }
                if (event.pairs_processed) {
                  newState.pairsProcessed = event.pairs_processed
                }
                if (event.candles_fetched !== undefined) {
                  newState.candlesFetched = event.candles_fetched
                }
                if (event.funding_rates_fetched !== undefined) {
                  newState.fundingRatesFetched = event.funding_rates_fetched
                }
                if (event.daily_pnl_records !== undefined) {
                  newState.dailyPnlRecords = event.daily_pnl_records
                }
                if (event.equity_records !== undefined) {
                  newState.equityRecords = event.equity_records
                }

                // Build new unified feed items
                const newUnifiedItems: UnifiedFeedItem[] = []

                // Handle live feed updates (keep last MAX_FEED_ITEMS per type)
                if (event.ledger_items?.length) {
                  newState.liveFeed.ledger = [
                    ...prev.liveFeed.ledger,
                    ...event.ledger_items,
                  ].slice(-MAX_FEED_ITEMS)
                  for (const item of event.ledger_items) {
                    newUnifiedItems.push({
                      id: `ledger-${feedItemCounter++}`,
                      timestamp: item.date,
                      type: "ledger",
                      data: item,
                    })
                  }
                }
                if (event.order_items?.length) {
                  newState.liveFeed.orders = [
                    ...prev.liveFeed.orders,
                    ...event.order_items,
                  ].slice(-MAX_FEED_ITEMS)
                  for (const item of event.order_items) {
                    newUnifiedItems.push({
                      id: `orders-${feedItemCounter++}`,
                      timestamp: item.date,
                      type: "orders",
                      data: item,
                    })
                  }
                }
                if (event.ohlcv_items?.length) {
                  newState.liveFeed.ohlcv = [
                    ...prev.liveFeed.ohlcv,
                    ...event.ohlcv_items,
                  ].slice(-MAX_FEED_ITEMS)
                  for (const item of event.ohlcv_items) {
                    newUnifiedItems.push({
                      id: `ohlcv-${feedItemCounter++}`,
                      timestamp: item.timestamp,
                      type: "ohlcv",
                      data: item,
                    })
                  }
                }
                if (event.funding_items?.length) {
                  newState.liveFeed.funding = [
                    ...prev.liveFeed.funding,
                    ...event.funding_items,
                  ].slice(-MAX_FEED_ITEMS)
                  for (const item of event.funding_items) {
                    newUnifiedItems.push({
                      id: `funding-${feedItemCounter++}`,
                      timestamp: item.timestamp,
                      type: "funding",
                      data: item,
                    })
                  }
                }

                // Append new items to unified feed and cap
                if (newUnifiedItems.length > 0) {
                  newState.unifiedFeed = [
                    ...newState.unifiedFeed,
                    ...newUnifiedItems,
                  ].slice(-MAX_FEED_ITEMS)
                }

                // Handle final states
                if (event.event_type === "completed") {
                  newState.status = "completed"
                } else if (event.event_type === "error") {
                  newState.status = "error"
                  newState.errorMessage = event.error_message || event.message
                }

                return newState
              })
            } catch {
              console.error("Failed to parse SSE event:", currentData)
            }

            currentEventType = null
            currentData = null
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        // Don't set error state for aborts, and allow restart
        isRunningRef.current = false
        return
      }

      setState((prev) => ({
        ...prev,
        status: "error",
        errorMessage: error instanceof Error ? error.message : "Unknown error",
      }))
    } finally {
      // Only mark as not running if we completed normally (not aborted)
      // Aborted case is handled above
      if (!abortController.signal.aborted) {
        isRunningRef.current = false
      }
    }
  }, [accountId, startDate, endDate])

  // Auto-start if enabled - use empty deps to only run once on mount
  useEffect(() => {
    if (autoStart) {
      // Small delay to handle React StrictMode double-mount
      const timeoutId = setTimeout(() => {
        if (!isRunningRef.current) {
          start()
        }
      }, 50)

      return () => {
        clearTimeout(timeoutId)
        if (abortControllerRef.current) {
          abortControllerRef.current.abort()
        }
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const detach = useCallback(() => {
    // Abort the SSE connection without resetting state.
    // The backend sync task continues running independently.
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    isRunningRef.current = false
  }, [])

  return { state, start, reset, detach, pushSystemMessage }
}
