import { Card, CardContent } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { LayoutGrid, DollarSign, Target, TrendingDown, Clock, HelpCircle } from "lucide-react"
import { PositionPie } from "@/components/charts/PositionPie"
import { WinRateGauge } from "@/components/charts/WinRateGauge"
import { formatUsd, formatPercent } from "@/lib/formatters"

interface GlobalCardProps {
  totalPositions: number
  longPositions: number
  shortPositions: number
  profitAndLoss: number
  meanPerDay: number
  winRate: number
  wins: number
  losses: number
  drawdown: number
  worstDrawdown: number
  avgTradeDuration: string
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

export function GlobalCard({
  totalPositions,
  longPositions,
  shortPositions,
  profitAndLoss,
  meanPerDay,
  winRate,
  wins,
  losses,
  drawdown,
  worstDrawdown,
  avgTradeDuration,
}: GlobalCardProps) {
  return (
    <div className="grid gap-4 grid-cols-2 @md:grid-cols-4 @xl:grid-cols-5">
      {/* Total Positions */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Total Positions" tooltip="Total closed trades in the selected period" icon={LayoutGrid} />
          <div className="flex items-center">
            <div className="size-12 mr-3">
              <PositionPie longPositions={longPositions} shortPositions={shortPositions} />
            </div>
            <div>
              <p className="font-bold text-2xl">{totalPositions}</p>
              <div className="flex text-sm font-medium">
                <p>
                  <span className="text-emerald-700 dark:text-emerald-400">{longPositions} Long</span>
                  <span className="text-muted-foreground"> / </span>
                  <span className="text-red-700 dark:text-red-400">{shortPositions} Short</span>
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* P&L */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="P&L" tooltip="Cumulative realized profit and loss" icon={DollarSign} />
          <div className="flex items-center">
            <p
              className={`font-mono font-bold text-2xl ${
                profitAndLoss >= 0
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-red-700 dark:text-red-400"
              }`}
            >
              {formatUsd(profitAndLoss, { showSign: true, withSuffix: false })}
            </p>
            <p className="pl-1 font-semibold text-md hidden @md:block @md:hidden @xl:block">
              USD
            </p>
          </div>
          <div className="flex items-center">
            <p className="text-sm text-muted-foreground">
              Mean per day: {formatUsd(meanPerDay, { showSign: true, withSuffix: false })}
            </p>
            <p className="pl-1 text-muted-foreground text-xs hidden @md:block @lg:hidden @xl:block">
              USD
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Win Rate */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Win Rate" tooltip="Percentage of trades closed in profit" icon={Target} />
          <div className="flex items-center">
            <div className="size-12 mr-3">
              <WinRateGauge winRate={winRate} />
            </div>
            <div>
              <p className="font-bold text-2xl">{formatPercent(winRate, { decimals: 0 })}</p>
              <div className="flex text-sm font-medium">
                <p className="text-muted-foreground">
                  {wins} Win / {losses} Loss
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Drawdown */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Drawdown" tooltip="Current and worst peak-to-trough decline" icon={TrendingDown} />
          <div className="flex items-center">
            <p className="font-mono font-bold text-2xl text-red-700 dark:text-red-400">
              {formatUsd(drawdown, { withSuffix: false })}
            </p>
            <p className="pl-1 font-semibold text-md hidden @md:block @md:hidden @xl:block">
              USD
            </p>
          </div>
          <div className="flex items-center">
            <p className="text-sm text-muted-foreground">
              Worst Drawdown: {formatUsd(worstDrawdown, { withSuffix: false })}
            </p>
            <p className="pl-1 text-muted-foreground text-xs hidden @md:block @md:hidden @xl:block">
              USD
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Avg Trade Duration - hidden below @xl */}
      <Card className="hidden @xl:block">
        <CardContent className="p-4">
          <CardHeader label="Avg. Trade Duration" tooltip="Average time from entry to close" icon={Clock} />
          <div className="flex items-center pt-2">
            <p className="font-bold text-2xl">{avgTradeDuration}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
