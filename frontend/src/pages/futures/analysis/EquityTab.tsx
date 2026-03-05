import { useOutletContext } from "react-router-dom"
import { useAccount } from "@/contexts/AccountContext"
import { useFuturesEquityAnalysis } from "@/hooks/useFuturesEquityAnalysis"
import { EquitySummaryCard } from "@/components/cards/EquitySummaryCard"
import { EquityCurveCard } from "@/components/cards/EquityCurveCard"
import { DailyReturnsCard } from "@/components/cards/DailyReturnsCard"
import { EquityDrawdownCard } from "@/components/cards/EquityDrawdownCard"
import { ReturnsDistributionCard } from "@/components/cards/ReturnsDistributionCard"
import { ShareFab } from "@/components/share/ShareFab"
import { EquityShareCard } from "@/components/share/EquityShareCard"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"
import { AlertCircle } from "lucide-react"
import type { AnalysisDateRange } from "../AnalysisPage"

function SummaryCardSkeleton() {
  return (
    <div className="grid gap-4 grid-cols-2 @md:grid-cols-3 @xl:grid-cols-5">
      {[...Array(5)].map((_, i) => (
        <Card key={i} className={i >= 3 ? "hidden @xl:block" : ""}>
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
      <SummaryCardSkeleton />
      <ChartCardSkeleton />
      <div className="grid grid-cols-1 @md:grid-cols-2 gap-4">
        <ChartCardSkeleton />
        <ChartCardSkeleton />
      </div>
      <ChartCardSkeleton />
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
          Select an account to view equity analysis
        </p>
      </CardContent>
    </Card>
  )
}

export default function EquityTab() {
  const { selectedAccountId, selectedAccount } = useAccount()
  const dateRange = useOutletContext<AnalysisDateRange>()
  const { data, isLoading, error } = useFuturesEquityAnalysis(
    selectedAccountId,
    dateRange
  )

  if (!selectedAccountId) {
    return <NoAccountState />
  }

  if (isLoading) {
    return <LoadingSkeleton />
  }

  if (error) {
    return <ErrorState message="Failed to load equity analysis data" />
  }

  if (!data) {
    return <ErrorState message="No data available" />
  }

  return (
    <div className="space-y-4">
      <EquitySummaryCard data={data} />

      <EquityCurveCard equityCurve={data.equity_curve} startingEquity={data.starting_equity} />

      <div className="grid grid-cols-1 @md:grid-cols-2 gap-4">
        <DailyReturnsCard dailyReturns={data.daily_returns} />
        <EquityDrawdownCard equityCurve={data.equity_curve} />
      </div>

      <ReturnsDistributionCard dailyReturns={data.daily_returns} />

      <ShareFab
        cardComponent={EquityShareCard}
        cardProps={{
          currentEquity: data.current_equity,
          equityChange: data.equity_change,
          equityChangePct: data.equity_change_pct,
          sharpeRatio: data.sharpe_ratio,
          profitFactor: data.profit_factor,
          equityCurve: data.equity_curve,
          startingEquity: data.starting_equity,
          accountName: selectedAccount?.name ?? "Unknown",
          exchangeName: selectedAccount?.exchange_name ?? "Unknown",
          exchangeAvatarUrl: selectedAccount?.exchange_avatar_url ?? null,
          startDate: dateRange.startDate,
          endDate: dateRange.endDate,
        }}
        exchangeName={selectedAccount?.exchange_name ?? "Unknown"}
        filenamePrefix="edgetrack-equity"
      />
    </div>
  )
}
