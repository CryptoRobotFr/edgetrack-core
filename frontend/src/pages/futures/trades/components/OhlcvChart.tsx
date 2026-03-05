import { useEffect, useRef, useState, useCallback, useMemo } from "react"
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type UTCTimestamp,
  ColorType,
  CrosshairMode,
} from "lightweight-charts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { useOhlcv, type OhlcvInterval, type OhlcvCandle, INTERVAL_MS } from "@/hooks/useOhlcv"
import type { TradeOrderItem } from "@/hooks/useTradeOrders"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

interface OhlcvChartProps {
  accountId: string
  base: string
  quote: string
  entryDate: number
  exitDate: number | null
  meanEntryPrice: number
  orders: TradeOrderItem[]
  side: "long" | "short"
}

const TIMEFRAMES: OhlcvInterval[] = ["1m", "5m", "15m", "1h", "4h", "1d"]
const LOAD_MORE_THRESHOLD = 10 // Trigger load when within N bars of edge
const BARS_TO_LOAD = 50
const MIN_CANDLES = 30

/**
 * Select the largest timeframe that gives >= MIN_CANDLES candles.
 * Same algorithm as backend PnL Evolution (_select_timeframe).
 */
function calculateDefaultTimeframe(
  entryDate: number,
  exitDate: number | null
): OhlcvInterval {
  const endDate = exitDate ?? Date.now()
  const durationMs = endDate - entryDate

  // Timeframes from largest to smallest
  const timeframesLargestFirst: OhlcvInterval[] = ["1d", "4h", "1h", "15m", "5m", "1m"]

  for (const tf of timeframesLargestFirst) {
    const candles = durationMs / INTERVAL_MS[tf]
    if (candles >= MIN_CANDLES) {
      return tf
    }
  }
  return "1m" // Fallback for very short trades
}

// Convert candle data to lightweight-charts format, deduplicating by timestamp
function convertToLightweightData(
  candles: OhlcvCandle[]
): CandlestickData<UTCTimestamp>[] {
  const result: CandlestickData<UTCTimestamp>[] = []
  let prevTime = -1
  for (const candle of candles) {
    const time = candle.timestamp / 1000
    if (time !== prevTime) {
      result.push({
        time: time as UTCTimestamp,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      })
      prevTime = time
    }
  }
  return result
}

// Round timestamp to candle boundary
function roundToCandleBoundary(timestamp: number, intervalMs: number): number {
  return Math.floor(timestamp / intervalMs) * intervalMs
}

export function OhlcvChart({
  accountId,
  base,
  quote,
  entryDate,
  exitDate,
  meanEntryPrice,
  orders,
  side,
}: OhlcvChartProps) {
  const { theme } = useTheme()
  const ct = getChartTheme(theme)
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
  const entryPriceLineRef = useRef<ReturnType<ISeriesApi<"Candlestick">["createPriceLine"]> | null>(null)
  const isInitialLoadRef = useRef(true)
  // Ref to track loading state in subscription callback without recreating it
  const isLoadingMoreRef = useRef(false)
  // Ref to store loadMore function for use in chart subscription
  const loadMoreRef = useRef<(direction: "past" | "future", n: number) => void>(() => {})
  // Ref to track total number of candles for edge detection
  const totalCandlesRef = useRef(0)

  // Calculate default timeframe based on trade duration
  const defaultTimeframe = useMemo(
    () => calculateDefaultTimeframe(entryDate, exitDate),
    [entryDate, exitDate]
  )

  const [interval, setInterval] = useState<OhlcvInterval>(defaultTimeframe)
  // State to track when chart is ready for subscription
  const [chartReady, setChartReady] = useState(false)

  const {
    candles,
    isLoading,
    isLoadingMore,
    error,
    loadMore,
    reset,
  } = useOhlcv({
    accountId,
    base,
    quote,
    interval,
    entryDate,
    exitDate,
  })

  // Sync loading state to ref for use in subscription callback
  useEffect(() => {
    isLoadingMoreRef.current = isLoadingMore
  }, [isLoadingMore])

  // Sync loadMore to ref for use in subscription callback
  useEffect(() => {
    loadMoreRef.current = loadMore
  }, [loadMore])

  // Track total candles for edge detection
  useEffect(() => {
    totalCandlesRef.current = candles.length
  }, [candles.length])

  // Reset to auto-calculated timeframe when trade changes
  useEffect(() => {
    setInterval(defaultTimeframe)
    isInitialLoadRef.current = true
    reset()
  }, [defaultTimeframe, reset])

  // Handle timeframe change
  const handleTimeframeChange = useCallback(
    (newInterval: OhlcvInterval) => {
      setInterval(newInterval)
      isInitialLoadRef.current = true
      reset()
    },
    [reset]
  )

  // Initialize chart - wait for loading to complete
  useEffect(() => {
    // Don't initialize while loading
    if (isLoading) return
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: ct.chartTextColor,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: ct.chartBorderColor,
      },
      timeScale: {
        borderColor: ct.chartBorderColor,
        timeVisible: true,
        secondsVisible: false,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
    })

    // Add candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#10b981",
      wickDownColor: "#ef4444",
      wickUpColor: "#10b981",
    })

    chartRef.current = chart
    candlestickSeriesRef.current = candlestickSeries

    // Mark chart as ready for subscription
    setChartReady(true)

    return () => {
      chart.remove()
      chartRef.current = null
      candlestickSeriesRef.current = null
      entryPriceLineRef.current = null
      setChartReady(false)
    }
  }, [isLoading, theme]) // eslint-disable-line react-hooks/exhaustive-deps

  // Update chart data when candles change
  useEffect(() => {
    if (!chartRef.current || !candlestickSeriesRef.current) {
      return
    }

    if (candles.length === 0) return

    const candlestickData = convertToLightweightData(candles)
    candlestickSeriesRef.current.setData(candlestickData)

    // Add mean entry price line (only once)
    if (!entryPriceLineRef.current) {
      entryPriceLineRef.current = candlestickSeriesRef.current.createPriceLine({
        price: meanEntryPrice,
        color: "#3b82f6",
        lineWidth: 2,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: "Entry",
      })
    }

    // Add order markers
    const intervalMs = INTERVAL_MS[interval]
    const isLong = side === "long"
    const markers = orders.map((order) => {
      const roundedTime = roundToCandleBoundary(order.execution_date, intervalMs)
      const isOpen = order.open_or_close === "open"
      // Long: OPEN below (arrow up), CLOSE above (arrow down)
      // Short: OPEN above (arrow down), CLOSE below (arrow up)
      const below = isLong ? isOpen : !isOpen
      return {
        time: (roundedTime / 1000) as UTCTimestamp,
        position: below ? "belowBar" : "aboveBar",
        color: isOpen ? "#10b981" : "#ef4444",
        shape: below ? "arrowUp" : "arrowDown",
        text: isOpen ? "OPEN" : "CLOSE",
      }
    })

    candlestickSeriesRef.current.setMarkers(markers as never)

    // On initial load, center the view on the trade
    if (isInitialLoadRef.current && candles.length > 0) {
      const intervalMs = INTERVAL_MS[interval]
      // Calculate the time range of the trade
      const tradeStartTime = (entryDate / 1000) as UTCTimestamp
      const tradeEndTime = ((exitDate ?? entryDate) / 1000) as UTCTimestamp

      // Add some padding around the trade (in seconds)
      const paddingSeconds = (10 * intervalMs) / 1000
      const visibleFrom = tradeStartTime - paddingSeconds
      const visibleTo = tradeEndTime + paddingSeconds

      chartRef.current.timeScale().setVisibleRange({
        from: visibleFrom as UTCTimestamp,
        to: visibleTo as UTCTimestamp,
      })
      isInitialLoadRef.current = false
    }
  }, [candles, meanEntryPrice, orders, interval, entryDate, exitDate])

  // Subscribe to visible range changes for bidirectional infinite scroll
  useEffect(() => {
    // Wait for chart to be ready
    if (!chartReady || !chartRef.current) {
      console.log("[Chart] Subscription skipped - chart not ready")
      return
    }

    const chart = chartRef.current
    console.log("[Chart] Setting up subscription")

    const handleVisibleRangeChange = (logicalRange: { from: number; to: number } | null) => {
      // Check ref to avoid triggering during loading (ref doesn't cause re-subscription)
      if (!logicalRange || isLoadingMoreRef.current) {
        return
      }

      const totalCandles = totalCandlesRef.current
      console.log("[Chart] Visible range:", logicalRange.from.toFixed(1), "-", logicalRange.to.toFixed(1), "total:", totalCandles)

      // If user is near the beginning (scrolling into the past)
      if (logicalRange.from < LOAD_MORE_THRESHOLD) {
        console.log("[Chart] Triggering loadMore past, from:", logicalRange.from)
        loadMoreRef.current("past", BARS_TO_LOAD)
      }

      // If user is near the end (scrolling into the future)
      if (logicalRange.to > totalCandles - LOAD_MORE_THRESHOLD) {
        console.log("[Chart] Triggering loadMore future, to:", logicalRange.to)
        loadMoreRef.current("future", BARS_TO_LOAD)
      }
    }

    chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange)

    return () => {
      console.log("[Chart] Cleaning up subscription")
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
    }
  }, [chartReady]) // Only depend on chartReady, use refs for other values

  if (error) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          Failed to load chart data
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="p-4 pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            {base}/{quote} Chart
            {isLoadingMore && (
              <span className="ml-2 text-xs text-muted-foreground font-normal">
                Loading...
              </span>
            )}
          </CardTitle>
          <Select value={interval} onValueChange={(v) => handleTimeframeChange(v as OhlcvInterval)}>
            <SelectTrigger className="h-7 w-16 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIMEFRAMES.map((tf) => (
                <SelectItem key={tf} value={tf} className="text-xs">
                  {tf}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="p-0 pl-4">
        {isLoading ? (
          <Skeleton className="h-[500px] w-full" />
        ) : (
          <div
            ref={chartContainerRef}
            className="h-[500px] w-full"
          />
        )}
      </CardContent>
    </Card>
  )
}
