import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { HelpCircle, TrendingUp } from "lucide-react"
import { PnlCurve } from "@/components/charts/PnlCurve"
import { clamp } from "@/lib/chart-utils"
import { formatChartDate, formatChartTooltipDate } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"
import type { components } from "@/api/schema"

type DailyAnalysis = components["schemas"]["DailyAnalysis"]

interface PnlChartCardProps {
  dailyAnalysis: DailyAnalysis[]
}

export function PnlChartCard({ dailyAnalysis }: PnlChartCardProps) {
  const { theme } = useTheme()
  const ct = getChartTheme(theme)

  if (dailyAnalysis.length === 0) {
    return (
      <Card className="px-2 h-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              Cumulative PnL
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

  // Calculate bounds for gradient
  const cumulativeValues = dailyAnalysis.map((d) => d.cumulative_pnl)
  const maxPnl = Math.max(...cumulativeValues)
  const minPnl = Math.min(...cumulativeValues)

  // Determine gradient color stops based on data range
  let colorStops: { offset: number; color: string }[]

  if (minPnl >= 0) {
    // All positive: solid green gradient
    colorStops = [
      { offset: 0, color: ct.areaGradient.profit.start },
      { offset: 1, color: ct.areaGradient.profit.end },
    ]
  } else if (maxPnl <= 0) {
    // All negative: solid red gradient
    colorStops = [
      { offset: 0, color: ct.areaGradient.loss.start },
      { offset: 1, color: ct.areaGradient.loss.end },
    ]
  } else {
    // Mixed: gradient with zero crossing
    const pctOffset = clamp(maxPnl / (maxPnl - minPnl), 0, 1)
    colorStops = [
      { offset: 0, color: ct.areaGradient.profit.start },
      { offset: clamp(pctOffset - 0.001, 0, 1), color: ct.areaGradient.profit.end },
      { offset: pctOffset, color: ct.zeroCrossingColor },
      { offset: clamp(pctOffset + 0.001, 0, 1), color: ct.areaGradient.loss.start },
      { offset: 1, color: ct.areaGradient.loss.end },
    ]
  }

  // Build chart data
  const chartData = {
    dates: dailyAnalysis.map((d) => formatChartDate(d.date)),
    tooltipDates: dailyAnalysis.map((d) => formatChartTooltipDate(d.date)),
    dataPoints: dailyAnalysis.map((d) => ({
      value: Math.round(d.cumulative_pnl * 100) / 100,
      itemStyle: { color: d.cumulative_pnl >= 0 ? "#59C0A4" : "#EC787E" },
    })),
    colorStops,
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Cumulative PnL
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Cumulative profit and loss over time</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <TrendingUp className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[300px] p-4">
        <PnlCurve data={chartData} />
      </CardContent>
    </Card>
  )
}
