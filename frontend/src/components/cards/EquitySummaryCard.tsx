import { Card, CardContent } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Wallet, BarChart3, TrendingDown, Scale, ArrowLeftRight, HelpCircle } from "lucide-react"
import { formatUsd, formatPercent } from "@/lib/formatters"
import type { EquityAnalysisData } from "@/hooks/useFuturesEquityAnalysis"

interface EquitySummaryCardProps {
  data: EquityAnalysisData
}

function formatRatio(value: number | null): string {
  if (value === null) return "N/A"
  return value.toFixed(2)
}

function ratioColor(value: number | null): string {
  if (value === null) return "text-muted-foreground"
  if (value > 1) return "text-emerald-700 dark:text-emerald-400"
  if (value >= 0) return "text-orange-600 dark:text-orange-500"
  return "text-red-700 dark:text-red-400"
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

export function EquitySummaryCard({ data }: EquitySummaryCardProps) {
  return (
    <div className="grid gap-4 grid-cols-2 @md:grid-cols-3 @xl:grid-cols-5">
      {/* Equity */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Equity" tooltip="Current account equity value" icon={Wallet} />
          <div className="flex items-center">
            <p className="font-mono font-bold text-2xl">
              {formatUsd(data.current_equity, { withSuffix: false })}
            </p>
            <p className="pl-1 font-semibold text-md hidden @md:block @md:hidden @xl:block">
              USD
            </p>
          </div>
          <div className="flex items-center gap-1">
            <p
              className={`text-sm font-medium ${
                data.equity_change >= 0
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-red-700 dark:text-red-400"
              }`}
            >
              {formatUsd(data.equity_change, { showSign: true, withSuffix: false })}
            </p>
            <p
              className={`text-sm ${
                data.equity_change_pct >= 0
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-red-700 dark:text-red-400"
              }`}
            >
              ({formatPercent(data.equity_change_pct, { showSign: true, decimals: 1 })})
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Sharpe + Sortino */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Sharpe Ratio" tooltip="Risk-adjusted return (annualized)" icon={BarChart3} />
          <div className="flex items-baseline gap-1.5">
            <p className={`font-mono font-bold text-2xl ${ratioColor(data.sharpe_ratio)}`}>
              {formatRatio(data.sharpe_ratio)}
            </p>
            <span className="text-xs text-muted-foreground">Annualized</span>
          </div>
          <p className={`text-sm ${ratioColor(data.sortino_ratio)}`}>
            Sortino: {formatRatio(data.sortino_ratio)}
          </p>
        </CardContent>
      </Card>

      {/* Max Drawdown */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Max Drawdown" tooltip="Largest peak-to-trough equity decline" icon={TrendingDown} />
          <div className="flex items-baseline gap-1.5">
            <p className="font-mono font-bold text-2xl text-red-700 dark:text-red-400">
              -{formatPercent(data.max_drawdown_pct, { decimals: 1 })}
            </p>
            <span className="text-sm text-red-700 dark:text-red-400">
              ({formatUsd(data.max_drawdown_amount, { withSuffix: false })})
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            {data.max_drawdown_duration_days}d duration
          </p>
        </CardContent>
      </Card>

      {/* Profit Factor - hidden below @xl */}
      <Card className="hidden @xl:block">
        <CardContent className="p-4">
          <CardHeader label="Profit Factor" tooltip="Ratio of gross gains to gross losses" icon={Scale} />
          <p className={`font-mono font-bold text-2xl ${ratioColor(data.profit_factor)}`}>
            {data.profit_factor !== null ? data.profit_factor.toFixed(2) : "N/A"}
          </p>
          <p className="text-sm text-muted-foreground">Gains / Losses ratio</p>
        </CardContent>
      </Card>

      {/* Net Transfers - hidden below @xl */}
      <Card className="hidden @xl:block">
        <CardContent className="p-4">
          <CardHeader label="Net Transfers" tooltip="Total deposits minus withdrawals" icon={ArrowLeftRight} />
          <p
            className={`font-mono font-bold text-2xl ${
              data.net_transfers > 0
                ? "text-emerald-700 dark:text-emerald-400"
                : data.net_transfers < 0
                  ? "text-red-700 dark:text-red-400"
                  : "text-muted-foreground"
            }`}
          >
            {formatUsd(data.net_transfers, { showSign: true, withSuffix: false })}
            <span className="pl-1 font-semibold text-md">USD</span>
          </p>
          <p className="text-sm text-muted-foreground">
            In: {formatUsd(data.total_transfers_in, { withSuffix: false })} / Out:{" "}
            {formatUsd(data.total_transfers_out, { withSuffix: false })}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
