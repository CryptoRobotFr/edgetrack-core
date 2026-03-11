import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { HelpCircle, TrendingDown } from "lucide-react"
import { DrawdownCurve } from "@/components/charts/DrawdownCurve"
import { formatChartDate, formatChartTooltipDate } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"
import type { components } from "@/api/schema"

type DailyAnalysis = components["schemas"]["DailyAnalysis"]

interface DrawdownChartCardProps {
  dailyAnalysis: DailyAnalysis[]
}

export function DrawdownChartCard({ dailyAnalysis }: DrawdownChartCardProps) {
  if (dailyAnalysis.length === 0) {
    return (
      <Card className="px-2 h-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              Drawdown
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

  const { theme } = useTheme()
  const ct = getChartTheme(theme)

  // Drawdown is stored as positive value in API, we display as negative
  // Drawdown is always <= 0, so we use a simple red gradient
  const colorStops = [
    { offset: 0, color: ct.drawdownGradient.start },
    { offset: 1, color: ct.drawdownGradient.end },
  ]

  // Build chart data
  const chartData = {
    dates: dailyAnalysis.map((d) => formatChartDate(d.date)),
    tooltipDates: dailyAnalysis.map((d) => formatChartTooltipDate(d.date)),
    dataPoints: dailyAnalysis.map((d) => ({
      value: Math.round(-d.drawdown * 100) / 100,
      itemStyle: { color: "#EC787E" },
    })),
    colorStops,
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Drawdown
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Maximum drawdown from peak equity</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <TrendingDown className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[300px] p-4">
        <DrawdownCurve data={chartData} />
      </CardContent>
    </Card>
  )
}
