import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { HelpCircle, TrendingDown } from "lucide-react"
import { EquityDrawdownCurve } from "@/components/charts/EquityDrawdownCurve"
import { formatChartDate } from "@/lib/formatters"
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

interface EquityDrawdownCardProps {
  equityCurve: EquityPoint[]
}

export function EquityDrawdownCard({ equityCurve }: EquityDrawdownCardProps) {
  if (equityCurve.length === 0) {
    return (
      <Card className="px-2 h-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              Equity Drawdown
            </CardTitle>
          </div>
          <TrendingDown className="w-3.5 h-3.5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="pt-0 h-[300px] flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  // Downsample then compute drawdown % from equity curve
  const sampled = downsample(equityCurve)
  let peak = sampled[0].equity
  const peaks: number[] = []
  const drawdownData = sampled.map((point) => {
    if (point.equity > peak) {
      peak = point.equity
    }
    peaks.push(Math.round(peak * 100) / 100)
    const ddPct = peak > 0 ? -((peak - point.equity) / peak) * 100 : 0
    return Math.round(ddPct * 100) / 100
  })

  const chartData = {
    dates: sampled.map((d) => formatChartDate(d.date)),
    dataPoints: drawdownData,
    equities: sampled.map((d) => Math.round(d.equity * 100) / 100),
    peaks,
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Equity Drawdown
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Drawdown from peak equity as percentage</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <TrendingDown className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[300px] p-4">
        <EquityDrawdownCurve data={chartData} />
      </CardContent>
    </Card>
  )
}
