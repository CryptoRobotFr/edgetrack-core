import { Calendar, DollarSign, Target, BarChart3, HelpCircle } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { WinRateGauge } from "@/components/charts/WinRateGauge"
import { PositionPie } from "@/components/charts/PositionPie"
import { formatUsd, formatPercent, formatNumber } from "@/lib/formatters"

interface GlobalMetricsCardProps {
  totalDaysRecorded: number
  activeDaysRecorded: number
  inactiveDaysRecorded: number
  totalPnl: number
  meanPnlPerDays: number
  winRate: number
  winningDays: number
  losingDays: number
  meanTradePerDays: number
  meanOrdersPerDays: number
  meanTradeDurationString: string
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

export function GlobalMetricsCard({
  totalDaysRecorded,
  activeDaysRecorded,
  inactiveDaysRecorded,
  totalPnl,
  meanPnlPerDays,
  winRate,
  winningDays,
  losingDays,
  meanTradePerDays,
  meanOrdersPerDays,
  meanTradeDurationString,
}: GlobalMetricsCardProps) {
  return (
    <div className="grid gap-4 grid-cols-2 @lg:grid-cols-4">
      {/* Days Recorded */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Days Recorded" tooltip="Total trading days in the period" icon={Calendar} />
          <div className="flex items-center">
            <div className="size-12 mr-3">
              <PositionPie
                longPositions={activeDaysRecorded}
                shortPositions={inactiveDaysRecorded}
              />
            </div>
            <div>
              <p className="font-bold text-2xl">{totalDaysRecorded}</p>
              <div className="flex text-sm font-medium">
                <p>
                  <span className="text-emerald-700 dark:text-emerald-400">
                    {activeDaysRecorded} Active
                  </span>
                  <span className="text-muted-foreground"> / </span>
                  <span className="text-red-700 dark:text-red-400">
                    {inactiveDaysRecorded} Inactive
                  </span>
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* PnL */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="P&L" tooltip="Cumulative realized profit and loss" icon={DollarSign} />
          <div className="flex items-center">
            <p
              className={`font-mono font-bold text-2xl ${
                totalPnl >= 0
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-red-700 dark:text-red-400"
              }`}
            >
              {formatUsd(totalPnl, { showSign: true, withSuffix: false })}
            </p>
            <p className="pl-1 font-semibold text-md hidden @md:block @lg:hidden @xl:block">
              USD
            </p>
          </div>
          <div className="flex items-center">
            <p className="text-sm text-muted-foreground">
              Mean per day: {formatUsd(meanPnlPerDays, { showSign: true, withSuffix: false })}
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
          <CardHeader label="Win Rate" tooltip="Percentage of profitable trading days" icon={Target} />
          <div className="flex items-center">
            <div className="size-12 mr-3">
              <WinRateGauge winRate={winRate} />
            </div>
            <div>
              <p className="font-bold text-2xl">{formatPercent(winRate, { decimals: 0 })}</p>
              <div className="flex text-sm font-medium">
                <p className="text-muted-foreground">
                  {winningDays} Win / {losingDays} Loss
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Trading Activity */}
      <Card>
        <CardContent className="p-4">
          <CardHeader label="Mean Trades / Day" tooltip="Average trades and orders per active day" icon={BarChart3} />
          <div className="flex items-center gap-x-1">
            <p className="font-bold text-2xl">{formatNumber(meanTradePerDays, 1)}</p>
            <p className="text-sm text-muted-foreground">
              ({formatNumber(meanOrdersPerDays, 1)} orders/day)
            </p>
          </div>
          <div className="flex items-center gap-x-1">
            <p className="text-sm text-muted-foreground">
              Mean trade duration:
            </p>
            <p className="text-sm text-muted-foreground">
              {meanTradeDurationString}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
