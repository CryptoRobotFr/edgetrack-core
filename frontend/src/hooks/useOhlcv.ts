import { useState, useCallback, useEffect, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export type OhlcvInterval = "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d"

export interface OhlcvCandle {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface OhlcvResponse {
  candles: OhlcvCandle[]
}

// Interval to milliseconds mapping
export const INTERVAL_MS: Record<OhlcvInterval, number> = {
  "1m": 60 * 1000,
  "5m": 5 * 60 * 1000,
  "15m": 15 * 60 * 1000,
  "30m": 30 * 60 * 1000,
  "1h": 60 * 60 * 1000,
  "4h": 4 * 60 * 60 * 1000,
  "1d": 24 * 60 * 60 * 1000,
}

// Constants for initial load and infinite scroll
// Padding candles before entry and after exit
const PADDING_CANDLES = 30
const LOAD_MORE_BATCH = 50

/**
 * Merge and deduplicate candles, ensuring ascending order by timestamp.
 * Uses a Map to deduplicate by timestamp, then sorts.
 */
function mergeCandles(existing: OhlcvCandle[], newCandles: OhlcvCandle[]): OhlcvCandle[] {
  const candleMap = new Map<number, OhlcvCandle>()

  // Add existing candles first
  for (const candle of existing) {
    candleMap.set(candle.timestamp, candle)
  }

  // Add/overwrite with new candles
  for (const candle of newCandles) {
    candleMap.set(candle.timestamp, candle)
  }

  // Convert to array and sort by timestamp ascending
  return Array.from(candleMap.values()).sort((a, b) => a.timestamp - b.timestamp)
}

interface UseOhlcvParams {
  accountId: string | null
  base: string
  quote: string
  interval: OhlcvInterval
  entryDate: number
  exitDate: number | null // null if trade is still open
}

/**
 * Hook to fetch OHLCV data with bidirectional infinite scroll.
 *
 * Initial load fetches candles around the trade:
 * - PADDING_CANDLES before entry
 * - PADDING_CANDLES after exit (or now if trade is open)
 *
 * loadMore("past") fetches older candles
 * loadMore("future") fetches newer candles
 */
export function useOhlcv({
  accountId,
  base,
  quote,
  interval,
  entryDate,
  exitDate,
}: UseOhlcvParams) {
  // Track the earliest and latest timestamps for bidirectional loading
  const earliestTimestampRef = useRef<number>(0)
  const latestTimestampRef = useRef<number>(0)

  // Track if we're loading more data (use ref to avoid recreating loadMore)
  const isLoadingMoreRef = useRef(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  // All loaded candles (accumulated)
  const [allCandles, setAllCandles] = useState<OhlcvCandle[]>([])

  // Calculate time window around the trade
  const intervalMs = INTERVAL_MS[interval]
  const startTime = entryDate - PADDING_CANDLES * intervalMs
  // Use exitDate if closed, otherwise use current time
  const tradeEndDate = exitDate ?? Date.now()
  const endTime = tradeEndDate + PADDING_CANDLES * intervalMs

  // Initial data query - loads data around the trade
  const initialQuery = useQuery({
    queryKey: ["futures", "ohlcv", accountId, base, quote, interval, entryDate, exitDate],
    queryFn: async () => {
      if (!accountId) {
        throw new Error("No account selected")
      }

      const response = await authApi.GET(

        "/api/v1/futures/ohlcv",
        {
          params: {
            query: {
              account_id: accountId,
              base: base.toUpperCase(),
              quote: quote.toUpperCase(),
              interval,
              start_time: startTime,
              end_time: endTime,
            },
          },
        }
      )
      if (response.error) {
        throw new Error("Failed to fetch OHLCV data")
      }
      const data = response.data as unknown as OhlcvResponse

      // Deduplicate and sort candles by timestamp ascending
      return mergeCandles([], data.candles)
    },
    enabled: !!accountId && !!base && !!quote,
  })

  // Sync query data to state when it changes
  useEffect(() => {
    if (initialQuery.data && initialQuery.data.length > 0) {
      setAllCandles(initialQuery.data)
      earliestTimestampRef.current = initialQuery.data[0].timestamp
      latestTimestampRef.current = initialQuery.data[initialQuery.data.length - 1].timestamp
    }
  }, [initialQuery.data])

  // Reset state when interval or entryDate changes
  useEffect(() => {
    setAllCandles([])
    earliestTimestampRef.current = 0
    latestTimestampRef.current = 0
  }, [interval, entryDate, exitDate])

  // Function to load more candles in either direction
  const loadMore = useCallback(
    async (direction: "past" | "future", numberOfCandles: number = LOAD_MORE_BATCH) => {
      // Use ref to check loading state to avoid stale closure
      if (!accountId || isLoadingMoreRef.current) {
        console.log("[loadMore] Skipping - no account or already loading")
        return
      }

      const intervalMs = INTERVAL_MS[interval]
      let loadStartTime: number
      let loadEndTime: number

      if (direction === "past") {
        if (earliestTimestampRef.current === 0) {
          console.log("[loadMore] Skipping past - no earliest timestamp")
          return
        }
        loadEndTime = earliestTimestampRef.current - intervalMs
        loadStartTime = loadEndTime - numberOfCandles * intervalMs
      } else {
        if (latestTimestampRef.current === 0) {
          console.log("[loadMore] Skipping future - no latest timestamp")
          return
        }
        loadStartTime = latestTimestampRef.current + intervalMs
        loadEndTime = loadStartTime + numberOfCandles * intervalMs
        // Don't load beyond current time
        const now = Date.now()
        if (loadStartTime > now) {
          console.log("[loadMore] Skipping future - already at current time")
          return
        }
        loadEndTime = Math.min(loadEndTime, now)
      }

      console.log(`[loadMore] Loading ${direction}:`, numberOfCandles, "candles")
      isLoadingMoreRef.current = true
      setIsLoadingMore(true)
      try {
        console.log("[loadMore] Fetching:", {
          direction,
          start: new Date(loadStartTime).toISOString(),
          end: new Date(loadEndTime).toISOString(),
        })

        const response = await authApi.GET(
  
          "/api/v1/futures/ohlcv",
          {
            params: {
              query: {
                account_id: accountId,
                base: base.toUpperCase(),
                quote: quote.toUpperCase(),
                interval,
                start_time: loadStartTime,
                end_time: loadEndTime,
              },
            },
          }
        )

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if ((response as any).error) {
          console.error("[loadMore] API error:", (response as any).error)
          throw new Error("Failed to fetch more OHLCV data")
        }

        const data = response.data as unknown as OhlcvResponse
        console.log("[loadMore] Received", data.candles.length, "candles")

        if (data.candles.length > 0) {
          // Merge new candles with existing ones (handles dedup + sorting)
          setAllCandles((prev) => {
            const merged = mergeCandles(prev, data.candles)
            console.log("[loadMore] Merged:", prev.length, "+", data.candles.length, "=", merged.length)
            // Update boundary timestamps from merged result
            if (merged.length > 0) {
              earliestTimestampRef.current = merged[0].timestamp
              latestTimestampRef.current = merged[merged.length - 1].timestamp
            }
            return merged
          })
        }
      } finally {
        isLoadingMoreRef.current = false
        setIsLoadingMore(false)
      }
    },
    [accountId, base, quote, interval]
  )

  // Reset function for when interval changes (called by component)
  const reset = useCallback(() => {
    setAllCandles([])
    earliestTimestampRef.current = 0
  }, [])

  return {
    candles: allCandles,
    isLoading: initialQuery.isLoading,
    isLoadingMore,
    error: initialQuery.error,
    loadMore,
    reset,
    refetch: initialQuery.refetch,
  }
}
