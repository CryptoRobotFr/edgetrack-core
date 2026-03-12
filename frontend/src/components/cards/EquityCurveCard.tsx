import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { HelpCircle, TrendingUp } from "lucide-react"
import { EquityCurve } from "@/components/charts/EquityCurve"
import { formatChartDate, formatChartTooltipDate } from "@/lib/formatters"
import type { EquityPoint } from "@/hooks/useFuturesEquityAnalysis"

const MAX_CHART_POINTS = 500

function downsample(data: EquityPoint[]): EquityPoint[] {
  if (data.length <= MAX_CHART_POINTS) return data
  const step = Math.ceil(data.length / MAX_CHART_POINTS)
  const result: EquityPoint[] = []
  for (let i = 0; i < data.length; i += step) {
    result.push(data[i])
  }
  if (result[result.length - 1] !== data[data.length - 1]) {
    result.push(data[data.length - 1])
  }
  return result
}

interface EquityCurveCardProps {
  equityCurve: EquityPoint[]
  startingEquity?: number
}

export function EquityCurveCard({ equityCurve, startingEquity }: EquityCurveCardProps) {
  if (equityCurve.length === 0) {
    return (
      <Card className="px-2 h-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              Equity Curve
            </CardTitle>
          </div>
          <TrendingUp className="w-3.5 h-3.5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="pt-0 h-[300px] flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  const sampled = downsample(equityCurve)
  const chartData = {
    dates: sampled.map((d) => formatChartDate(d.date)),
    tooltipDates: sampled.map((d) => formatChartTooltipDate(d.date)),
    dataPoints: sampled.map((d) => Math.round(d.equity * 100) / 100),
    realized: sampled.map((d) =>
      d.realized_equity != null ? Math.round(d.realized_equity * 100) / 100 : null
    ),
    unrealized: sampled.map((d) =>
      d.unrealized_pnl != null ? Math.round(d.unrealized_pnl * 100) / 100 : null
    ),
    startingEquity: startingEquity ?? sampled[0].equity,
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Equity Curve
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Account equity value over time</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <TrendingUp className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[300px] p-4">
        <EquityCurve data={chartData} />
      </CardContent>
    </Card>
  )
}
