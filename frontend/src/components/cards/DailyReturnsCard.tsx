import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { BarChart3, HelpCircle } from "lucide-react"
import { DailyReturnsBar } from "@/components/charts/DailyReturnsBar"
import { formatChartDate } from "@/lib/formatters"
import type { DailyReturn } from "@/hooks/useFuturesEquityAnalysis"

interface DailyReturnsCardProps {
  dailyReturns: DailyReturn[]
}

export function DailyReturnsCard({ dailyReturns }: DailyReturnsCardProps) {
  if (dailyReturns.length === 0) {
    return (
      <Card className="px-2 h-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              Daily Returns
            </CardTitle>
          </div>
          <BarChart3 className="w-3.5 h-3.5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="pt-0 h-[300px] flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  const chartData = {
    dates: dailyReturns.map((d) => formatChartDate(d.date)),
    dataPoints: dailyReturns.map((d) => ({
      value: Math.round(d.return_pct * 100) / 100,
      itemStyle: { color: d.return_pct >= 0 ? "#59C0A4" : "#EC787E" },
    })),
    pnls: dailyReturns.map((d) => Math.round(d.pnl * 100) / 100),
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Daily Returns
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Daily return as percentage of account equity</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <BarChart3 className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[300px] p-4">
        <DailyReturnsBar data={chartData} />
      </CardContent>
    </Card>
  )
}
