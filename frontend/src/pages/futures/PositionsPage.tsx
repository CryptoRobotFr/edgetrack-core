import { Outlet } from "react-router-dom"
import { AlertCircle } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAccount } from "@/contexts/AccountContext"
import { useHourlyPnl } from "@/hooks/useHourlyPnl"
import { usePositions } from "@/hooks/usePositions"
import { ShareFab } from "@/components/share/ShareFab"
import { PositionsShareCard } from "@/components/share/PositionsShareCard"
import { AccountSummaryCard } from "./positions/AccountSummaryCard"
import { HourlyPnlCard } from "./positions/HourlyPnlCard"
import { PairPnlRaceCard } from "./positions/PairPnlRaceCard"
import { PositionsList } from "./positions/PositionsList"

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      {/* Summary cards skeleton */}
      <div className="grid gap-4 grid-cols-2 @sm:grid-cols-3 @md:grid-cols-4 @lg:grid-cols-5">
        {[...Array(5)].map((_, i) => (
          <Card key={i} className={i === 4 ? "hidden @lg:block" : ""}>
            <CardContent className="p-4 space-y-2">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-8 w-28" />
              <Skeleton className="h-4 w-24" />
            </CardContent>
          </Card>
        ))}
      </div>
      {/* Positions list skeleton */}
      <Card>
        <CardContent className="p-4 space-y-3">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <Card>
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
    <Card>
      <CardContent className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">
          Select an account to view positions
        </p>
      </CardContent>
    </Card>
  )
}

function ChartsSkeleton() {
  return (
    <div className="grid grid-cols-1 @md:grid-cols-2 gap-4">
      <Card className="h-[350px]">
        <CardContent className="p-4 space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-[280px] w-full" />
        </CardContent>
      </Card>
      <Card className="h-[350px]">
        <CardContent className="p-4 space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-[280px] w-full" />
        </CardContent>
      </Card>
    </div>
  )
}

export default function PositionsPage() {
  const { selectedAccountId, selectedAccount } = useAccount()
  const { data, isLoading, error, refetch } = usePositions(selectedAccountId)
  const { data: hourlyPnlData, isLoading: isHourlyPnlLoading } =
    useHourlyPnl(selectedAccountId)

  if (!selectedAccountId) {
    return <NoAccountState />
  }

  if (isLoading && !data) {
    return <LoadingSkeleton />
  }

  if (error) {
    return <ErrorState message="Failed to load positions data" />
  }

  if (!data) {
    return <ErrorState message="No data available" />
  }

  return (
    <div className="space-y-4">
      <AccountSummaryCard balance={data.balance} positions={data.positions} />
      <PositionsList
        positions={data.positions}
        isLoading={isLoading}
        onRefresh={refetch}
      />
      {isHourlyPnlLoading && !hourlyPnlData ? (
        <ChartsSkeleton />
      ) : (
        <div className="grid grid-cols-1 @md:grid-cols-2 gap-4">
          <HourlyPnlCard data={hourlyPnlData?.hourly_pnl} />
          <PairPnlRaceCard data={hourlyPnlData?.pair_pnl} />
        </div>
      )}
      <Outlet />

      {data && (
        <ShareFab
          cardComponent={PositionsShareCard}
          cardProps={{
            equity: data.balance.equity,
            unrealizedPnl: data.balance.unrealized_pnl,
            realizedPnl: data.positions.reduce((sum, p) => sum + p.realized_pnl, 0),
            positions: data.positions.map((p) => ({
              pair: p.pair,
              side: p.side,
              unrealized_pnl: p.unrealized_pnl,
              size: p.size,
              usd_size: p.usd_size,
              leverage: p.leverage,
              entry_price: p.entry_price,
              mark_price: p.mark_price,
              pnl_pct: p.pnl_pct,
              price_decimals: p.price_decimals,
              size_decimals: p.size_decimals,
            })),
            hourlyPnl: (hourlyPnlData?.hourly_pnl ?? []).map((d) => ({
              timestamp: d.timestamp,
              pnl: d.pnl,
            })),
            accountName: selectedAccount?.name ?? "Unknown",
            exchangeName: selectedAccount?.exchange_name ?? "Unknown",
            exchangeAvatarUrl: selectedAccount?.exchange_avatar_url ?? null,
          }}
          exchangeName={selectedAccount?.exchange_name ?? "Unknown"}
          filenamePrefix="edgetrack-positions"
        />
      )}
    </div>
  )
}
