import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ChartColumnIncreasing, HelpCircle } from "lucide-react"
import { DailyPnlBar } from "@/components/charts/DailyPnlBar"
import { formatChartDate } from "@/lib/formatters"
import type { components } from "@/api/schema"

type DailyAnalysis = components["schemas"]["DailyAnalysis"]

interface DailyPnlChartCardProps {
  dailyAnalysis: DailyAnalysis[]
}

export function DailyPnlChartCard({ dailyAnalysis }: DailyPnlChartCardProps) {
  if (dailyAnalysis.length === 0) {
    return (
      <Card className="px-2 h-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              Daily PnL
            </CardTitle>
          </div>
          <ChartColumnIncreasing className="w-3.5 h-3.5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="pt-0 h-[300px] flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  // Build chart data
  const chartData = {
    dates: dailyAnalysis.map((d) => formatChartDate(d.date)),
    dataPoints: dailyAnalysis.map((d) => ({
      value: Math.round(d.pnl * 100) / 100,
      itemStyle: { color: d.pnl >= 0 ? "#59C0A4" : "#EC787E" },
    })),
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Daily PnL
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Daily profit and loss breakdown</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <ChartColumnIncreasing className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[300px] p-4">
        <DailyPnlBar data={chartData} />
      </CardContent>
    </Card>
  )
}
