import { useState, useCallback, useMemo } from "react"
import { useAccount } from "@/contexts/AccountContext"
import { useCalendarGlobalMetrics } from "@/hooks/useCalendarGlobalMetrics"
import { useCalendarDays } from "@/hooks/useCalendarDays"
import { GlobalMetricsCard } from "@/components/cards/GlobalMetricsCard"
import { FuturesCalendar } from "@/components/calendar/FuturesCalendar"
import { ShareFab } from "@/components/share/ShareFab"
import { CalendarShareCard } from "@/components/share/CalendarShareCard"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"
import { AlertCircle } from "lucide-react"

function GlobalMetricsCardSkeleton() {
  return (
    <div className="grid gap-4 grid-cols-2 @lg:grid-cols-4">
      {[...Array(4)].map((_, i) => (
        <Card key={i}>
          <CardContent className="p-4 space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-4 w-20" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function CalendarSkeleton() {
  return (
    <Card>
      <div className="p-4">
        <div className="flex justify-between items-center mb-4">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-8 w-24" />
        </div>
        <div className="grid grid-cols-7 gap-1">
          {[...Array(35)].map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-lg" />
          ))}
        </div>
      </div>
    </Card>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <GlobalMetricsCardSkeleton />
      <CalendarSkeleton />
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <Card className="px-2">
      <CardContent className="flex items-center justify-center py-12">
        <div className="text-center">
          <AlertCircle className="h-8 w-8 mx-auto mb-2 text-red-500" />
          <p className="text-muted-foreground">{message}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function NoAccountState() {
  return (
    <Card className="px-2">
      <CardContent className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">
          Select an account to view calendar
        </p>
      </CardContent>
    </Card>
  )
}

export default function CalendarPage() {
  const { selectedAccountId, selectedAccount } = useAccount()
  const [dateRange, setDateRange] = useState<{
    startDate: number | null
    endDate: number | null
  }>({ startDate: null, endDate: null })

  const handleDateRangeChange = useCallback(
    (startDate: number, endDate: number) => {
      setDateRange({ startDate, endDate })
    },
    []
  )

  const {
    data: globalMetrics,
    isLoading: isLoadingMetrics,
    error: metricsError,
  } = useCalendarGlobalMetrics(selectedAccountId)

  const {
    data: calendarDays,
    isLoading: isLoadingDays,
  } = useCalendarDays(
    selectedAccountId,
    dateRange.startDate,
    dateRange.endDate
  )

  // dateRange.startDate is the Monday BEFORE the 1st of the month (up to 6 days earlier).
  // Adding 7 days guarantees we land inside the correct month.
  const monthLabel = useMemo(() => {
    if (!dateRange.startDate) return ""
    const mid = new Date(dateRange.startDate + 7 * 86400000)
    return mid.toLocaleDateString("en", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    })
  }, [dateRange.startDate])

  // Compute month-specific metrics from calendarDays for the share card
  const monthMetrics = useMemo(() => {
    if (!calendarDays || !dateRange.startDate) {
      return { totalPnl: 0, winRate: 0, winningDays: 0, losingDays: 0, meanPnlPerDay: 0 }
    }
    const mid = new Date(dateRange.startDate + 7 * 86400000)
    const targetMonth = mid.getUTCMonth()
    const targetYear = mid.getUTCFullYear()

    const monthDays = calendarDays.filter((d) => {
      const dt = new Date(d.date)
      return dt.getUTCMonth() === targetMonth && dt.getUTCFullYear() === targetYear
    })

    const activeDays = monthDays.filter((d) => d.total_pnl !== 0)
    const winning = activeDays.filter((d) => d.total_pnl > 0).length
    const losing = activeDays.filter((d) => d.total_pnl < 0).length
    const total = activeDays.reduce((sum, d) => sum + d.total_pnl, 0)
    const wr = winning + losing > 0 ? (winning / (winning + losing)) * 100 : 0
    const mean = activeDays.length > 0 ? total / activeDays.length : 0

    return { totalPnl: total, winRate: wr, winningDays: winning, losingDays: losing, meanPnlPerDay: mean }
  }, [calendarDays, dateRange.startDate])

  if (!selectedAccountId) {
    return <NoAccountState />
  }

  if (isLoadingMetrics && !globalMetrics) {
    return <LoadingSkeleton />
  }

  if (metricsError) {
    return <ErrorState message="Failed to load calendar data" />
  }

  if (!globalMetrics) {
    return <ErrorState message="No data available" />
  }

  return (
    <div className="space-y-4 min-w-0">
      <GlobalMetricsCard
        totalDaysRecorded={globalMetrics.total_days_recorded}
        activeDaysRecorded={globalMetrics.active_days_recorded}
        inactiveDaysRecorded={globalMetrics.inactive_days_recorded}
        totalPnl={globalMetrics.total_pnl}
        meanPnlPerDays={globalMetrics.mean_pnl_per_days}
        winRate={globalMetrics.win_rate}
        winningDays={globalMetrics.winning_days}
        losingDays={globalMetrics.losing_days}
        meanTradePerDays={globalMetrics.mean_trade_per_days}
        meanOrdersPerDays={globalMetrics.mean_orders_per_days}
        meanTradeDurationString={globalMetrics.mean_trade_duration_string}
      />
      <FuturesCalendar
        calendarData={calendarDays}
        isLoading={isLoadingDays}
        onDateRangeChange={handleDateRangeChange}
      />

      {globalMetrics && calendarDays && (
        <ShareFab
          cardComponent={CalendarShareCard}
          cardProps={{
            totalPnl: monthMetrics.totalPnl,
            winRate: monthMetrics.winRate,
            winningDays: monthMetrics.winningDays,
            losingDays: monthMetrics.losingDays,
            meanPnlPerDay: monthMetrics.meanPnlPerDay,
            calendarDays: calendarDays.map((d) => ({
              date: d.date,
              total_pnl: d.total_pnl,
            })),
            monthLabel,
            accountName: selectedAccount?.name ?? "Unknown",
            exchangeName: selectedAccount?.exchange_name ?? "Unknown",
            exchangeAvatarUrl: selectedAccount?.exchange_avatar_url ?? null,
          }}
          exchangeName={selectedAccount?.exchange_name ?? "Unknown"}
          filenamePrefix="edgetrack-calendar"
        />
      )}
    </div>
  )
}
