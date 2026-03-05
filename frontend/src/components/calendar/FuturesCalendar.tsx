import { useEffect, useState, useRef, useCallback, useMemo } from "react"
import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  addMonths,
  subMonths,
  addWeeks,
  subWeeks,
} from "date-fns"
import { CalendarHeader } from "./CalendarHeader"
import { MemoizedDayCard } from "./DayCard"
import { Maximize2, Minimize2, LayoutList, List, LayoutGrid, CalendarDays, CalendarRange, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  CalendarDay,
  ViewMode,
  CalendarViewMode,
  CalendarDayResponse,
  TradeWithPosition,
  DailyData,
} from "@/types/calendar"
import { useMainContainerBreakpoint } from "@/hooks/useContainerBreakpoint"

interface FuturesCalendarProps {
  calendarData: CalendarDayResponse[] | undefined
  isLoading: boolean
  onDateRangeChange: (startDate: number, endDate: number) => void
}

export function FuturesCalendar({
  calendarData,
  isLoading,
  onDateRangeChange,
}: FuturesCalendarProps) {
  const [currentMonth, setCurrentMonth] = useState(new Date())
  const [currentWeek, setCurrentWeek] = useState(new Date())
  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([])
  const [displayMode, setDisplayMode] = useState<ViewMode>("minimal")
  const [hoveredTradeId, setHoveredTradeId] = useState<string | null>(null)
  const [manualViewMode, setManualViewMode] = useState<CalendarViewMode | null>(null)
  const [bestDayDate, setBestDayDate] = useState<number | null>(null)
  const [worstDayDate, setWorstDayDate] = useState<number | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const calendarRef = useRef<HTMLDivElement>(null)
  const dayScrollRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  // Use container-based breakpoint instead of viewport width
  const { isMd } = useMainContainerBreakpoint()

  // Derived view mode: manual override takes precedence, otherwise based on container width
  const autoViewMode: CalendarViewMode = isMd ? "month" : "week"
  const viewMode: CalendarViewMode = useMemo(() => {
    return manualViewMode ?? autoViewMode
  }, [manualViewMode, autoViewMode])

  // Reset manual override when auto mode changes (user resizes past breakpoint)
  useEffect(() => {
    setManualViewMode(null)
  }, [autoViewMode])

  // Calculate date range and notify parent when month/week changes
  useEffect(() => {
    let start: Date, end: Date
    if (viewMode === "month") {
      start = startOfWeek(startOfMonth(currentMonth), { weekStartsOn: 1 })
      end = endOfWeek(endOfMonth(currentMonth), { weekStartsOn: 1 })
    } else {
      start = startOfWeek(currentWeek, { weekStartsOn: 1 })
      end = endOfWeek(currentWeek, { weekStartsOn: 1 })
    }
    onDateRangeChange(start.getTime(), end.getTime())
  }, [currentMonth, currentWeek, viewMode, onDateRangeChange])

  // Generate calendar days when data changes
  useEffect(() => {
    generateCalendarDays()
  }, [calendarData, currentMonth, currentWeek, viewMode])

  const findBestAndWorstDays = (days: CalendarDay[]) => {
    const activeDays = days.filter(
      (day) =>
        day.isCurrentMonth &&
        day.dailyData?.totalPnL !== undefined &&
        day.dailyData?.totalPnL !== 0
    )

    if (activeDays.length === 0) {
      setBestDayDate(null)
      setWorstDayDate(null)
      return
    }

    const bestDay = activeDays.reduce((prev, current) =>
      (current.dailyData!.totalPnL > prev.dailyData!.totalPnL) ? current : prev
    )
    const worstDay = activeDays.reduce((prev, current) =>
      (current.dailyData!.totalPnL < prev.dailyData!.totalPnL) ? current : prev
    )

    setBestDayDate(bestDay.date.getTime())
    setWorstDayDate(worstDay.date.getTime())
  }

  const generateCalendarDays = () => {
    let start: Date, end: Date
    if (viewMode === "month") {
      start = startOfMonth(currentMonth)
      end = endOfMonth(currentMonth)
    } else {
      start = startOfWeek(currentWeek, { weekStartsOn: 1 })
      end = endOfWeek(currentWeek, { weekStartsOn: 1 })
    }

    const days = eachDayOfInterval({
      start: startOfWeek(start, { weekStartsOn: 1 }),
      end: endOfWeek(end, { weekStartsOn: 1 }),
    })

    // Create a map of date -> daily data from API response
    const dataMap = new Map<string, CalendarDayResponse>()
    if (calendarData) {
      for (const day of calendarData) {
        const dateStr = format(new Date(day.date), "yyyy-MM-dd")
        dataMap.set(dateStr, day)
      }
    }

    // First pass: collect trade positions per week for alignment in detailed view
    const weekTradePositions = new Map<number, Map<string, number>>()
    let currentWeekIdx = -1

    days.forEach((day, index) => {
      const weekIndex = Math.floor(index / 7)
      if (weekIndex !== currentWeekIdx) {
        currentWeekIdx = weekIndex
        weekTradePositions.set(weekIndex, new Map())
      }

      const dayStr = format(day, "yyyy-MM-dd")
      const dayData = dataMap.get(dayStr)

      if (dayData?.trades) {
        const weekPositions = weekTradePositions.get(weekIndex)!
        dayData.trades.forEach((trade) => {
          if (!weekPositions.has(trade.trade_id)) {
            weekPositions.set(trade.trade_id, weekPositions.size)
          }
        })
      }
    })

    // Second pass: create calendar days
    const newCalendarDays: CalendarDay[] = days.map((day, index) => {
      const weekIndex = Math.floor(index / 7)
      const weekPositions = weekTradePositions.get(weekIndex)!

      const dayStr = format(day, "yyyy-MM-dd")
      const dayData = dataMap.get(dayStr)

      let dailyStats: DailyData | undefined
      if (dayData) {
        const processedTrades: TradeWithPosition[] = dayData.trades
          .map((trade) => ({
            ...trade,
            position: weekPositions.get(trade.trade_id),
          }))
          .sort((a, b) => a.start_date - b.start_date)

        dailyStats = {
          totalPnL: dayData.total_pnl,
          longCount: dayData.long_count,
          shortCount: dayData.short_count,
          longPnL: dayData.long_pnl,
          shortPnL: dayData.short_pnl,
          trades: processedTrades,
          maxPositions: weekPositions.size,
        }
      }

      return {
        date: day,
        isCurrentMonth: viewMode === "month" ? day >= start && day <= end : true,
        dailyData: dailyStats,
      }
    })

    setCalendarDays(newCalendarDays)
    findBestAndWorstDays(newCalendarDays)
  }

  const navigateMonth = (direction: "next" | "previous") => {
    const newDate =
      direction === "next"
        ? addMonths(currentMonth, 1)
        : subMonths(currentMonth, 1)
    setCurrentMonth(newDate)
    if (viewMode === "week") {
      setCurrentWeek(newDate)
    }
  }

  const navigateWeek = (direction: "next" | "previous") => {
    const newDate =
      direction === "next" ? addWeeks(currentWeek, 1) : subWeeks(currentWeek, 1)
    setCurrentWeek(newDate)
  }

  const calculateDisplayedPeriodPnL = () => {
    if (!calendarDays.length) return 0
    return calendarDays.reduce((total, day) => {
      if (day.isCurrentMonth && day.dailyData?.totalPnL) {
        return total + day.dailyData.totalPnL
      }
      return total
    }, 0)
  }

  // Handle synchronized scroll across days when hovering a trade
  // sourceDateKey identifies the day where the hover originates, so we skip scrolling it
  const handleTradeHover = useCallback((tradeId: string | null, sourceDateKey?: string) => {
    setHoveredTradeId(tradeId)

    if (!tradeId || displayMode !== "detailed") return

    // For each day, find the index of the hovered trade and scroll to it
    calendarDays.forEach((day) => {
      if (!day.dailyData?.trades) return

      const dateKey = format(day.date, "yyyy-MM-dd")

      // Skip the day where the hover originates to avoid jarring self-scroll
      if (dateKey === sourceDateKey) return

      const scrollContainer = dayScrollRefs.current.get(dateKey)
      if (!scrollContainer) return

      // Trades are already sorted by start_date in generateCalendarDays
      const tradeIndex = day.dailyData.trades.findIndex((t) => t.trade_id === tradeId)
      if (tradeIndex === -1) return

      // Scroll to position (each trade row is 28px - h-7)
      const scrollTop = tradeIndex * 28
      scrollContainer.scrollTo({ top: scrollTop, behavior: "smooth" })
    })
  }, [calendarDays, displayMode])

  // Register a day's scroll container ref
  const registerDayScrollRef = useCallback((dateKey: string, ref: HTMLDivElement | null) => {
    if (ref) {
      dayScrollRefs.current.set(dateKey, ref)
    } else {
      dayScrollRefs.current.delete(dateKey)
    }
  }, [])

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      calendarRef.current
        ?.requestFullscreen()
        .then(() => {
          setIsFullscreen(true)
        })
        .catch((err) => {
          console.error(`Error enabling fullscreen: ${err.message}`)
        })
    } else {
      document.exitFullscreen().then(() => {
        setIsFullscreen(false)
      })
    }
  }

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }
    document.addEventListener("fullscreenchange", handleFullscreenChange)
    return () =>
      document.removeEventListener("fullscreenchange", handleFullscreenChange)
  }, [])

  // View mode options for dropdown
  const viewModeOptions: { mode: ViewMode; icon: typeof LayoutGrid; label: string }[] = [
    { mode: "minimal", icon: LayoutGrid, label: "Minimal" },
    { mode: "simple", icon: LayoutList, label: "Long/Short" },
    { mode: "detailed", icon: List, label: "Trades" },
  ]

  const currentViewModeOption = viewModeOptions.find((opt) => opt.mode === displayMode)!

  return (
    <div
      ref={calendarRef}
      className={`w-full min-w-0 overflow-hidden flex flex-col relative ${
        isFullscreen ? "bg-background h-screen p-8" : ""
      }`}
      style={{ isolation: "isolate" }}
    >
      {/* Fullscreen toggle button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleFullscreen}
        className="absolute top-0 right-0 h-8 w-8 z-10"
      >
        {isFullscreen ? (
          <Minimize2 className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <Maximize2 className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </Button>

      {/* Control Card */}
      <Card
        className={`relative overflow-hidden ${isFullscreen ? "z-50" : ""}`}
      >
        <div className="pt-2 px-4 pb-2">
          <div className="flex justify-between items-center gap-2">
            {/* View mode selector - Desktop: 3 buttons, Mobile: dropdown (using container query) */}
            <div className="@md:w-[180px] relative">
              {/* Desktop: 3 icon buttons (container >= md) */}
              <div className="hidden @md:flex gap-1 justify-start">
                {viewModeOptions.map(({ mode, icon: Icon, label }) => (
                  <Button
                    key={mode}
                    variant={displayMode === mode ? "secondary" : "ghost"}
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setDisplayMode(mode)}
                    title={label}
                  >
                    <Icon className="h-4 w-4" />
                  </Button>
                ))}
              </div>

              {/* Mobile: dropdown menu (container < md) */}
              <div className="@md:hidden">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <currentViewModeOption.icon className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start">
                    {viewModeOptions.map(({ mode, icon: Icon, label }) => (
                      <DropdownMenuItem
                        key={mode}
                        onClick={() => setDisplayMode(mode)}
                        className="flex items-center gap-2"
                      >
                        <Icon className="h-4 w-4" />
                        <span>{label}</span>
                        {displayMode === mode && (
                          <Check className="h-4 w-4 ml-auto" />
                        )}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>

            {/* Calendar Header (navigation + PnL) */}
            <div className="flex-1 flex justify-center">
              <CalendarHeader
                currentMonth={viewMode === "month" ? currentMonth : currentWeek}
                onNavigate={viewMode === "month" ? navigateMonth : navigateWeek}
                onMonthSelect={(date) => {
                  setCurrentMonth(date)
                  if (viewMode === "week") {
                    setCurrentWeek(date)
                  }
                }}
                monthlyPnL={calculateDisplayedPeriodPnL()}
                viewMode={viewMode}
                isLoading={isLoading}
                isFullscreen={isFullscreen}
              />
            </div>

            {/* Week/Month toggle */}
            <div className="@md:w-[180px] flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const newMode = viewMode === "month" ? "week" : "month"
                  setManualViewMode(newMode)
                }}
                className="border-muted-foreground/30"
                title={viewMode === "month" ? "Switch to week view" : "Switch to month view"}
              >
                {viewMode === "month" ? (
                  <>
                    <CalendarRange className="h-4 w-4 @md:mr-2" />
                    <span className="hidden @md:inline-block">Week</span>
                  </>
                ) : (
                  <>
                    <CalendarDays className="h-4 w-4 @md:mr-2" />
                    <span className="hidden @md:inline-block">Month</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Calendar Grid */}
      <div
        className="flex-1 overflow-x-auto overflow-y-auto mt-2 py-1"
        style={{ contain: "inline-size" }}
      >
        {/* Weekday header row */}
        {viewMode === "month" && (
          <div className="grid grid-cols-7 min-w-[900px] gap-0.5 mb-1">
            {["Mon.", "Tue.", "Wed.", "Thu.", "Fri.", "Sat.", "Sun."].map((day) => (
              <div
                key={day}
                className="text-center text-sm font-medium text-muted-foreground py-1"
              >
                {day}
              </div>
            ))}
          </div>
        )}
        <div
          className={`${
            viewMode === "month" ? "grid grid-cols-7 min-w-[900px]" : "flex flex-col"
          } gap-0.5`}
        >
          {calendarDays.map((day) => {
            const dayTime = day.date.getTime()
            const dateKey = format(day.date, "yyyy-MM-dd")
            return (
              <MemoizedDayCard
                key={dateKey}
                day={day}
                viewMode={displayMode}
                hoveredTradeId={hoveredTradeId}
                onTradeHover={handleTradeHover}
                isBestDay={dayTime === bestDayDate}
                isWorstDay={dayTime === worstDayDate}
                calendarViewMode={viewMode}
                dateKey={dateKey}
                registerScrollRef={registerDayScrollRef}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}
