import { useCallback, memo } from "react"
import { format, isToday } from "date-fns"
import { CalendarDay, ViewMode, CalendarViewMode, TradeWithPosition } from "@/types/calendar"
import { formatUsd, formatDateTime } from "@/lib/formatters"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface DayCardProps {
  day: CalendarDay
  viewMode: ViewMode
  hoveredTradeId: string | null
  onTradeHover: (id: string | null, sourceDateKey?: string) => void
  isBestDay?: boolean
  isWorstDay?: boolean
  calendarViewMode: CalendarViewMode
  dateKey: string
  registerScrollRef: (dateKey: string, ref: HTMLDivElement | null) => void
}

export function DayCard({
  day,
  viewMode,
  hoveredTradeId,
  onTradeHover,
  isBestDay,
  isWorstDay,
  calendarViewMode,
  dateKey,
  registerScrollRef,
}: DayCardProps) {
  const dailyData = day.dailyData

  const dayNumber = format(day.date, "d")
  const dailyPnL = dailyData?.totalPnL || 0
  const longCount = dailyData?.longCount || 0
  const shortCount = dailyData?.shortCount || 0
  const totalCount = longCount + shortCount

  const longWidth = totalCount > 0 ? (longCount / totalCount) * 100 : 0
  const shortWidth = totalCount > 0 ? (shortCount / totalCount) * 100 : 0

  const longPnL = dailyData?.longPnL || 0
  const shortPnL = dailyData?.shortPnL || 0

  const scrollRef = useCallback((ref: HTMLDivElement | null) => {
    registerScrollRef(dateKey, ref)
  }, [registerScrollRef, dateKey])

  const handleTradeHover = useCallback((tradeId: string) => {
    onTradeHover(tradeId, dateKey)
  }, [onTradeHover, dateKey])

  const handleTradeLeave = useCallback((e: React.MouseEvent) => {
    const relatedTarget = e.relatedTarget
    if (relatedTarget instanceof HTMLElement) {
      if (!relatedTarget.closest(".trade-item")) {
        onTradeHover(null)
      }
    } else {
      onTradeHover(null)
    }
  }, [onTradeHover])

  const getBorderClass = () => {
    if (calendarViewMode !== "month") return ""
    if (isBestDay) return "ring-2 ring-inset ring-emerald-500/50"
    if (isWorstDay) return "ring-2 ring-inset ring-red-500/50"
    return ""
  }

  return (
    <div
      className={`p-0 h-40 rounded-lg border bg-card shadow-sm overflow-hidden relative flex flex-col ${
        day.isCurrentMonth ? "bg-card" : "bg-muted/50"
      } ${getBorderClass()}`}
    >
      {/* Best/Worst day badge */}
      {calendarViewMode === "month" && (isBestDay || isWorstDay) && (
        <div
          className={`absolute px-1 text-[0.45rem] bottom-0 right-0 rounded-sm font-medium ${
            isBestDay
              ? "text-emerald-500/50"
              : "text-red-500/50"
          }`}
        >
          {isBestDay ? "Best day" : "Worst day"}
        </div>
      )}

      {viewMode === "minimal" ? (
        /* ========== MINIMAL VIEW ========== */
        <div
          className={`flex-1 w-full flex flex-col relative ${
            !day.isCurrentMonth
              ? "bg-muted/50"
              : dailyPnL > 0
                ? "bg-emerald-500/10 dark:bg-emerald-500/30"
                : dailyPnL < 0
                  ? "bg-red-500/10 dark:bg-red-500/30"
                  : "bg-card"
          }`}
        >
          {/* Day number at top */}
          <div className="p-2 flex justify-center">
            {isToday(day.date) && (
              <div className="absolute top-1 right-1">
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              </div>
            )}
            <div className="text-lg font-medium text-muted-foreground">{dayNumber}</div>
          </div>
          {/* PnL centered in remaining space */}
          <div className="flex-1 flex items-center justify-center -mt-6">
            {day.isCurrentMonth && dailyPnL !== 0 && (
              <span
                className={`text-xl font-mono ${
                  dailyPnL > 0
                    ? "text-emerald-700 dark:text-emerald-400"
                    : "text-red-700 dark:text-red-400"
                }`}
              >
                {formatUsd(dailyPnL, { showSign: true })}
              </span>
            )}
          </div>
        </div>
      ) : (
        /* ========== SIMPLE & DETAILED VIEWS ========== */
        <>
          {/* Header */}
          <div
            className={`sticky top-0 p-2 z-10 ${
              day.isCurrentMonth ? "bg-card" : "bg-muted/50"
            }`}
          >
            {viewMode === "simple" ? (
              /* Simple view: centered day number, no separator */
              <div className="flex justify-center items-center relative">
                {isToday(day.date) && (
                  <div className="absolute -top-1 -right-1">
                    <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                  </div>
                )}
                <div className="text-base font-medium text-muted-foreground">{dayNumber}</div>
              </div>
            ) : (
              /* Detailed view: day number left, PnL right, with separator */
              <>
                <div className="flex flex-row justify-between items-center relative">
                  <div className="text-sm text-muted-foreground">{dayNumber}</div>
                  {isToday(day.date) && (
                    <div className="absolute -top-1 -right-1">
                      <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                    </div>
                  )}
                  {day.isCurrentMonth && dailyPnL !== 0 && (
                    <div
                      className={`text-sm font-mono ${
                        dailyPnL > 0
                          ? "text-emerald-700 dark:text-emerald-400"
                          : "text-red-700 dark:text-red-400"
                      }`}
                    >
                      {formatUsd(dailyPnL, { showSign: true })}
                    </div>
                  )}
                </div>
                <hr className="mt-1" />
              </>
            )}
          </div>

          {/* Content */}
          <div
            ref={viewMode === "detailed" ? scrollRef : undefined}
            className={`px-3 ${viewMode === "detailed" ? "overflow-auto" : ""}`}
            style={{ height: "calc(100% - 2.5rem)" }}
          >
            <div className="relative">
              {day.isCurrentMonth &&
                (viewMode === "simple" ? (
                  /* ===== SIMPLE VIEW CONTENT ===== */
                  <div className="flex flex-col gap-2">
                    {/* Long bar */}
                    <div className="flex items-center gap-2 pb-1 pt-2">
                      <div className="relative flex-1 bg-muted rounded-full h-6 min-w-[30px]">
                        <div
                          style={{
                            width: `${Math.max(10, longWidth)}%`,
                            minWidth: "30px",
                          }}
                          className={`bg-emerald-500 h-6 rounded-full flex items-center justify-end pr-2 text-white text-xs ${
                            longWidth === 0 ? "hidden" : ""
                          }`}
                        >
                          <p
                            className={
                              longCount.toString().length === 1 ? "pr-1" : ""
                            }
                          >
                            {longCount}
                          </p>
                        </div>
                      </div>
                      <span
                        className={`text-xs font-mono w-14 text-right ${
                          longPnL > 0
                            ? "text-emerald-700 dark:text-emerald-400"
                            : longPnL < 0
                              ? "text-red-700 dark:text-red-400"
                              : "text-muted-foreground"
                        }`}
                      >
                        {formatUsd(longPnL, { showSign: longPnL !== 0 })}
                      </span>
                    </div>

                    {/* Short bar */}
                    <div className="flex items-center gap-2 pb-1">
                      <div className="relative flex-1 bg-muted rounded-full h-6 min-w-[30px]">
                        <div
                          style={{
                            width: `${Math.max(10, shortWidth)}%`,
                            minWidth: "30px",
                          }}
                          className={`bg-red-500 h-6 rounded-full flex items-center justify-end pr-2 text-white text-xs ${
                            shortWidth === 0 ? "hidden" : ""
                          }`}
                        >
                          <p
                            className={
                              shortCount.toString().length === 1 ? "pr-1" : ""
                            }
                          >
                            {shortCount}
                          </p>
                        </div>
                      </div>
                      <span
                        className={`text-xs font-mono w-14 text-right ${
                          shortPnL > 0
                            ? "text-emerald-700 dark:text-emerald-400"
                            : shortPnL < 0
                              ? "text-red-700 dark:text-red-400"
                              : "text-muted-foreground"
                        }`}
                      >
                        {formatUsd(shortPnL, { showSign: shortPnL !== 0 })}
                      </span>
                    </div>

                    {/* Total PnL */}
                    <div className="flex items-center justify-center">
                      <span
                        className={`text-md font-mono font-medium ${
                          dailyPnL > 0
                            ? "text-emerald-700 dark:text-emerald-400"
                            : dailyPnL < 0
                              ? "text-red-700 dark:text-red-400"
                              : "text-muted-foreground"
                        }`}
                      >
                        {formatUsd(dailyPnL, { showSign: dailyPnL !== 0 })}
                      </span>
                    </div>
                  </div>
                ) : (
                  /* ===== DETAILED VIEW CONTENT ===== */
                  <TooltipProvider>
                    <div className="flex flex-col">
                      {dailyData?.trades?.map((trade) => (
                        <MemoizedTradeRow
                          key={trade.trade_id}
                          trade={trade}
                          isHovered={hoveredTradeId === trade.trade_id}
                          onMouseEnter={() => handleTradeHover(trade.trade_id)}
                          onMouseLeave={handleTradeLeave}
                        />
                      ))}
                    </div>
                  </TooltipProvider>
                ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

interface TradeRowProps {
  trade: TradeWithPosition
  isHovered: boolean
  onMouseEnter: () => void
  onMouseLeave: (e: React.MouseEvent) => void
}

function TradeRow({ trade, isHovered, onMouseEnter, onMouseLeave }: TradeRowProps) {
  return (
    <Tooltip delayDuration={200}>
      <TooltipTrigger asChild>
        <div
          className={`trade-item flex flex-row items-center justify-between p-1 rounded-sm h-7 cursor-pointer ${
            isHovered ? "bg-muted" : "hover:bg-muted/50"
          }`}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
        >
          <div className="flex items-center gap-1 min-w-0 flex-1 relative">
            <div className="shrink-0 size-4 flex items-center justify-center">
              {trade.base_image_url ? (
                <img
                  src={trade.base_image_url}
                  alt={trade.pair}
                  className="size-4 rounded-full"
                  onError={(e) => {
                    ;(e.target as HTMLImageElement).src =
                      "https://assets.coingecko.com/coins/images/1/standard/bitcoin.png"
                  }}
                />
              ) : (
                <div className="size-4 rounded-full bg-muted" />
              )}
            </div>
            <div className="relative">
              <span className="text-xs whitespace-nowrap">{trade.pair}</span>
            </div>
          </div>
          <div className="flex relative flex-row items-center">
            <div
              className={`w-8 h-7 bg-gradient-to-l ${
                isHovered ? "from-muted" : "from-card"
              } to-transparent`}
            />
            <span
              className={`text-xs font-mono text-right ${
                isHovered ? "bg-muted" : "bg-card"
              } ${
                trade.day_pnl > 0
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-red-700 dark:text-red-400"
              }`}
            >
              {formatUsd(trade.day_pnl, { showSign: true })}
            </span>
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent side="right" className="p-0 overflow-hidden">
        <div className="w-64">
          {/* Header with coin icon and pair name */}
          <div className="flex items-center gap-3 p-3 border-b bg-muted/30">
            <div className="shrink-0 size-8 flex items-center justify-center">
              {trade.base_image_url ? (
                <img
                  src={trade.base_image_url}
                  alt={trade.pair}
                  className="size-8 rounded-full"
                  onError={(e) => {
                    ;(e.target as HTMLImageElement).src =
                      "https://assets.coingecko.com/coins/images/1/standard/bitcoin.png"
                  }}
                />
              ) : (
                <div className="size-8 rounded-full bg-muted" />
              )}
            </div>
            <div>
              <p className="font-semibold text-sm">{trade.pair}</p>
              <p className={`text-xs capitalize ${
                trade.side === "long"
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-red-600 dark:text-red-400"
              }`}>
                {trade.side === "long" ? "Long" : "Short"}
              </p>
            </div>
          </div>
          {/* Trade details */}
          <div className="p-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Start Date</span>
              <span>{formatDateTime(trade.start_date)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">End Date</span>
              <span>
                {trade.end_date
                  ? formatDateTime(trade.end_date)
                  : <span className="text-amber-500">Running</span>
                }
              </span>
            </div>
            <div className="flex justify-between gap-4 pt-2 border-t">
              <span className="text-muted-foreground">Total PnL</span>
              <span className={`font-mono font-medium ${
                trade.total_pnl > 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-red-600 dark:text-red-400"
              }`}>
                {formatUsd(trade.total_pnl, { showSign: true })}
              </span>
            </div>
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  )
}

const MemoizedTradeRow = memo(TradeRow)

// Memoized DayCard: only re-renders when hoveredTradeId actually affects this day's trades
export const MemoizedDayCard = memo(DayCard, (prevProps, nextProps) => {
  // Always re-render if structural props change
  if (
    prevProps.viewMode !== nextProps.viewMode ||
    prevProps.calendarViewMode !== nextProps.calendarViewMode ||
    prevProps.isBestDay !== nextProps.isBestDay ||
    prevProps.isWorstDay !== nextProps.isWorstDay ||
    prevProps.day !== nextProps.day ||
    prevProps.dateKey !== nextProps.dateKey ||
    prevProps.onTradeHover !== nextProps.onTradeHover ||
    prevProps.registerScrollRef !== nextProps.registerScrollRef
  ) {
    return false // not equal → re-render
  }

  // For hoveredTradeId: only re-render if this day contains the old or new hovered trade
  if (prevProps.hoveredTradeId !== nextProps.hoveredTradeId) {
    const trades = nextProps.day.dailyData?.trades
    if (!trades || trades.length === 0) {
      return true // no trades in this day → skip re-render
    }
    const prevRelevant = prevProps.hoveredTradeId
      ? trades.some((t) => t.trade_id === prevProps.hoveredTradeId)
      : false
    const nextRelevant = nextProps.hoveredTradeId
      ? trades.some((t) => t.trade_id === nextProps.hoveredTradeId)
      : false
    if (!prevRelevant && !nextRelevant) {
      return true // hovered trade is not in this day → skip re-render
    }
  }

  return false // re-render for safety
})
