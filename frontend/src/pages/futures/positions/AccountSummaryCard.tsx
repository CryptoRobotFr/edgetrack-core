import { Wallet, TrendingUp, Activity, LayoutGrid, Clock } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { HelpCircle } from "lucide-react"
import { formatUsd, formatPercent, formatDuration } from "@/lib/formatters"
import { PositionPie } from "@/components/charts/PositionPie"
import type { AccountBalanceSummary, PositionItem } from "@/hooks/usePositions"

interface AccountSummaryCardProps {
  balance: AccountBalanceSummary
  positions: PositionItem[]
}

function CardHeader({ label, tooltip, icon: Icon }: { label: string; tooltip: string; icon: React.ElementType }) {
  return (
    <div className="flex items-center justify-between mb-1">
      <div className="flex items-center gap-1.5">
        <p className="text-muted-foreground text-sm">{label}</p>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <HelpCircle className="w-3 h-3 cursor-pointer text-muted-foreground" />
            </TooltipTrigger>
            <TooltipContent>
              <p>{tooltip}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      <Icon className="w-3.5 h-3.5 text-muted-foreground" />
    </div>
  )
}

export function AccountSummaryCard({ balance, positions }: AccountSummaryCardProps) {
  const longPositions = positions.filter(p => p.side === "long")
  const shortPositions = positions.filter(p => p.side === "short")
  const longCount = longPositions.length
  const shortCount = shortPositions.length

  const totalRealizedPnl = positions.reduce((sum, p) => sum + p.realized_pnl, 0)

  const unrealizedPctOfEquity = balance.equity !== 0
    ? (balance.unrealized_pnl / balance.equity) * 100
    : 0

  const longExposure = longPositions.reduce((sum, p) => sum + p.usd_size, 0)
  const shortExposure = shortPositions.reduce((sum, p) => sum + p.usd_size, 0)
  const marketExposure = longExposure + shortExposure
  const marketExposurePct = balance.equity !== 0
    ? (marketExposure / balance.equity) * 100
    : 0

  const netExposureRaw = longExposure - shortExposure
  const netExposure = Math.abs(netExposureRaw)
  const netDirection: "Long" | "Short" | "Neutral" =
    netExposureRaw > 0 ? "Long" : netExposureRaw < 0 ? "Short" : "Neutral"

  const positionsWithAge = positions.filter(p => p.created_at !== null)
  const avgPositionAge = positionsWithAge.length > 0
    ? positionsWithAge.reduce((sum, p) => sum + (Date.now() - p.created_at!), 0) / positionsWithAge.length
    : 0

  const isUnrealizedPositive = balance.unrealized_pnl >= 0
  const isRealizedPositive = totalRealizedPnl >= 0

  const netDirectionColor =
    netDirection === "Long"
      ? "text-emerald-700 dark:text-emerald-400"
      : netDirection === "Short"
        ? "text-red-700 dark:text-red-400"
        : "text-muted-foreground"

  return (
    <div className="grid gap-4 grid-cols-2 @sm:grid-cols-3 @md:grid-cols-4 @lg:grid-cols-5">
      {/* Equity */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Equity" tooltip="Total account value including unrealized PnL" icon={Wallet} />
          <p className="font-mono font-bold text-2xl">
            {formatUsd(balance.equity)}
          </p>
          <p className="text-sm text-muted-foreground">
            Margin: <span className="font-bold">{formatUsd(balance.total_margin)}</span>
          </p>
        </CardContent>
      </Card>

      {/* Unrealized PnL */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Unrealized PnL" tooltip="Profit/loss on currently open positions" icon={TrendingUp} />
          <div className="flex items-baseline gap-1.5">
            <p
              className={`font-mono font-bold text-2xl ${
                isUnrealizedPositive
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-red-700 dark:text-red-400"
              }`}
            >
              {formatUsd(balance.unrealized_pnl, { showSign: true })}
            </p>
            <span className={`text-sm ${
              isUnrealizedPositive
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-red-700 dark:text-red-400"
            }`}>
              ({formatPercent(unrealizedPctOfEquity, { showSign: true, decimals: 1 })})
            </span>
          </div>
          <p className={`text-sm ${
            isRealizedPositive
              ? "text-emerald-700 dark:text-emerald-400"
              : "text-red-700 dark:text-red-400"
          }`}>
            Realized: <span className="font-bold">{formatUsd(totalRealizedPnl, { showSign: true })}</span>
          </p>
        </CardContent>
      </Card>

      {/* Open Positions */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Open Positions" tooltip="Currently active long and short positions" icon={LayoutGrid} />
          <div className="flex items-center">
            <div className="size-12 mr-3">
              <PositionPie longPositions={longCount} shortPositions={shortCount} />
            </div>
            <div>
              <p className="font-bold text-2xl">{positions.length}</p>
              <div className="flex text-sm font-medium">
                <p>
                  <span className="text-emerald-700 dark:text-emerald-400">{longCount} Long</span>
                  <span className="text-muted-foreground"> / </span>
                  <span className="text-red-700 dark:text-red-400">{shortCount} Short</span>
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Market Exposure */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Market Exposure" tooltip="Total USD value of all open positions" icon={Activity} />
          <div className="flex items-baseline gap-1.5">
            <p className="font-mono font-bold text-2xl">
              {formatUsd(marketExposure)}
            </p>
            <span className="text-sm text-muted-foreground">
              ({formatPercent(marketExposurePct, { decimals: 0 })})
            </span>
          </div>
          <p className={`text-sm ${netDirectionColor}`}>
            Net: <span className="font-bold">{formatUsd(netExposure)}</span> {netDirection}
          </p>
        </CardContent>
      </Card>

      {/* Avg Position Age (hidden below @lg) */}
      <Card className="hidden @lg:block">
        <CardContent className="p-4">
          <CardHeader label="Avg. Position Age" tooltip="Average time positions have been open" icon={Clock} />
          <div className="flex items-center pt-2">
            <p className="font-bold text-2xl">
              {positionsWithAge.length > 0 ? formatDuration(avgPositionAge) : "—"}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
