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
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"
import type { HourlyPnlPoint } from "@/hooks/useHourlyPnl"

function formatHourLabel(timestampMs: number): string {
  const date = new Date(timestampMs)
  const month = date.toLocaleDateString("en-US", { month: "short" })
  const day = date.getUTCDate()
  const hours = String(date.getUTCHours()).padStart(2, "0")
  return `${month} ${day} ${hours}:00`
}

interface HourlyPnlCardProps {
  data: HourlyPnlPoint[] | undefined
}

export function HourlyPnlCard({ data }: HourlyPnlCardProps) {
  const { theme } = useTheme()
  const ct = getChartTheme(theme)

  if (!data || data.length === 0) {
    return (
      <Card className="h-[350px]">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              Account PnL (7d)
            </CardTitle>
          </div>
          <TrendingUp className="w-3.5 h-3.5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="pt-0 h-[280px] flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  const pnlValues = data.map((d) => d.pnl)
  const maxPnl = Math.max(...pnlValues)
  const minPnl = Math.min(...pnlValues)

  let colorStops: { offset: number; color: string }[]

  if (minPnl >= 0) {
    colorStops = [
      { offset: 0, color: ct.areaGradient.profit.start },
      { offset: 1, color: ct.areaGradient.profit.end },
    ]
  } else if (maxPnl <= 0) {
    colorStops = [
      { offset: 0, color: ct.areaGradient.loss.start },
      { offset: 1, color: ct.areaGradient.loss.end },
    ]
  } else {
    const pctOffset = clamp(maxPnl / (maxPnl - minPnl), 0, 1)
    colorStops = [
      { offset: 0, color: ct.areaGradient.profit.start },
      { offset: clamp(pctOffset - 0.001, 0, 1), color: ct.areaGradient.profit.end },
      { offset: pctOffset, color: ct.zeroCrossingColor },
      { offset: clamp(pctOffset + 0.001, 0, 1), color: ct.areaGradient.loss.start },
      { offset: 1, color: ct.areaGradient.loss.end },
    ]
  }

  const chartData = {
    dates: data.map((d) => formatHourLabel(d.timestamp)),
    dataPoints: data.map((d) => ({
      value: Math.round(d.pnl * 100) / 100,
      itemStyle: { color: d.pnl >= 0 ? "#59C0A4" : "#EC787E" },
    })),
    colorStops,
  }

  return (
    <Card className="h-[350px]">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Account PnL (7d)
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Hourly cumulative PnL over the last 7 days</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <TrendingUp className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[280px] px-4 pt-2 pb-1">
        <PnlCurve
          data={chartData}
          showYAxisLabel={false}
          grid={{ left: 0, top: 10, right: 10, bottom: 0, containLabel: true }}
        />
      </CardContent>
    </Card>
  )
}
