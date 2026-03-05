import { useOutletContext } from "react-router-dom"
import { useAccount } from "@/contexts/AccountContext"
import { useFuturesAnalysis } from "@/hooks/useFuturesAnalysis"
import { GlobalCard } from "@/components/cards/GlobalCard"
import { PositionCard } from "@/components/cards/PositionCard"
import { PnlChartCard } from "@/components/cards/PnlChartCard"
import { DailyPnlChartCard } from "@/components/cards/DailyPnlChartCard"
import { DrawdownChartCard } from "@/components/cards/DrawdownChartCard"
import { TradeDurationChartCard } from "@/components/cards/TradeDurationChartCard"
import { TradesTableCard } from "@/components/cards/TradesTableCard"
import { ShareFab } from "@/components/share/ShareFab"
import { PnlShareCard } from "@/components/share/PnlShareCard"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"
import { AlertCircle } from "lucide-react"
import { formatDuration } from "@/lib/formatters"
import type { AnalysisDateRange } from "../AnalysisPage"

function GlobalCardSkeleton() {
  return (
    <div className="grid gap-4 grid-cols-2 @md:grid-cols-4 @xl:grid-cols-5">
      {[...Array(5)].map((_, i) => (
        <Card key={i} className={i === 4 ? "hidden @xl:block" : ""}>
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

function PositionCardSkeleton() {
  return (
    <Card className="px-2 h-full">
      <div className="p-6 pb-1">
        <Skeleton className="h-5 w-32" />
      </div>
      <div className="p-6 pt-0">
        <div className="grid gap-4 grid-cols-2">
          {[...Array(4)].map((_, i) => (
            <div key={i}>
              <Skeleton className="h-4 w-20 mb-2" />
              <Skeleton className="h-8 w-28" />
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function ChartCardSkeleton() {
  return (
    <Card className="px-2 h-full">
      <div className="p-6 pb-1">
        <Skeleton className="h-5 w-32" />
      </div>
      <div className="p-6 pt-0 h-[200px]">
        <Skeleton className="h-full w-full" />
      </div>
    </Card>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <GlobalCardSkeleton />
      <div className="grid grid-cols-1 @lg:grid-cols-2 gap-4">
        <PositionCardSkeleton />
        <PositionCardSkeleton />
      </div>
      <div className="grid grid-cols-1 @lg:grid-cols-3 gap-4">
        <ChartCardSkeleton />
        <ChartCardSkeleton />
        <ChartCardSkeleton />
      </div>
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
          Select an account to view analysis
        </p>
      </CardContent>
    </Card>
  )
}

export default function PnlTab() {
  const { selectedAccountId, selectedAccount } = useAccount()
  const dateRange = useOutletContext<AnalysisDateRange>()
  const { data, isLoading, error } = useFuturesAnalysis(selectedAccountId, dateRange)

  if (!selectedAccountId) {
    return <NoAccountState />
  }

  if (isLoading) {
    return <LoadingSkeleton />
  }

  if (error) {
    return <ErrorState message="Failed to load analysis data" />
  }

  if (!data) {
    return <ErrorState message="No data available" />
  }

  return (
    <div className="space-y-4">
      <GlobalCard
        totalPositions={data.total_trades}
        longPositions={data.long_trades}
        shortPositions={data.short_trades}
        profitAndLoss={data.total_pnl}
        meanPerDay={data.average_daily_pnl}
        winRate={data.win_rate}
        wins={data.winning_trades}
        losses={data.losing_trades}
        drawdown={data.current_drawdown}
        worstDrawdown={data.max_drawdown}
        avgTradeDuration={formatDuration(data.average_trade_duration_ms)}
      />

      <div className="grid grid-cols-1 @md:grid-cols-2 gap-4">
        <PositionCard
          positionType="long"
          total={data.long_stats.total_trades}
          wins={data.long_stats.winning_trades}
          losses={data.long_stats.losing_trades}
          winRate={data.long_stats.win_rate}
          pnl={data.long_stats.pnl}
          topPairs={data.long_stats.top_pairs}
        />
        <PositionCard
          positionType="short"
          total={data.short_stats.total_trades}
          wins={data.short_stats.winning_trades}
          losses={data.short_stats.losing_trades}
          winRate={data.short_stats.win_rate}
          pnl={data.short_stats.pnl}
          topPairs={data.short_stats.top_pairs}
        />
      </div>

      <div className="grid grid-cols-1 @md:grid-cols-2 gap-4">
        <PnlChartCard dailyAnalysis={data.daily_analysis} />
        <DailyPnlChartCard dailyAnalysis={data.daily_analysis} />
      </div>

      <div className="grid grid-cols-1 @md:grid-cols-2 gap-4">
        <DrawdownChartCard dailyAnalysis={data.daily_analysis} />
        <TradeDurationChartCard tradeAnalysis={data.trade_analysis} />
      </div>

      <TradesTableCard trades={data.trade_analysis} />

      <ShareFab
        cardComponent={PnlShareCard}
        cardProps={{
          totalPnl: data.total_pnl,
          totalTrades: data.total_trades,
          longTrades: data.long_trades,
          shortTrades: data.short_trades,
          winRate: data.win_rate,
          wins: data.winning_trades,
          losses: data.losing_trades,
          dailyAnalysis: data.daily_analysis,
          accountName: selectedAccount?.name ?? "Unknown",
          exchangeName: selectedAccount?.exchange_name ?? "Unknown",
          exchangeAvatarUrl: selectedAccount?.exchange_avatar_url ?? null,
          startDate: dateRange.startDate,
          endDate: dateRange.endDate,
        }}
        exchangeName={selectedAccount?.exchange_name ?? "Unknown"}
        filenamePrefix="edgetrack-pnl"
      />
    </div>
  )
}
