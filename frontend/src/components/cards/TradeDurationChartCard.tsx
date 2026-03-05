import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Clock, HelpCircle } from "lucide-react"
import { TradeDurationScatter } from "@/components/charts/TradeDurationScatter"
import type { components } from "@/api/schema"

type TradeAnalysis = components["schemas"]["TradeAnalysis"]

interface TradeDurationChartCardProps {
  tradeAnalysis: TradeAnalysis[]
}

export function TradeDurationChartCard({ tradeAnalysis }: TradeDurationChartCardProps) {
  if (tradeAnalysis.length === 0) {
    return (
      <Card className="px-2 h-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              Trade Duration
            </CardTitle>
          </div>
          <Clock className="w-3.5 h-3.5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="pt-0 h-[380px] flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  // Transform trade data into chart format
  const chartData = {
    winningTrades: [] as { pnl: number; duration: number; tooltip: string }[],
    losingTrades: [] as { pnl: number; duration: number; tooltip: string }[],
  }

  tradeAnalysis.forEach((trade) => {
    // Convert duration from milliseconds to days
    const durationInDays = trade.duration_ms / (1000 * 60 * 60 * 24)

    const tradeData = {
      pnl: Math.round(trade.pnl * 100) / 100,
      duration: Math.round(durationInDays * 100) / 100,
      tooltip: trade.pair,
    }

    if (trade.pnl >= 0) {
      chartData.winningTrades.push(tradeData)
    } else {
      chartData.losingTrades.push(tradeData)
    }
  })

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Trade Duration
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Trade duration vs PnL. Toggle to see average duration.</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <Clock className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[300px] p-4">
        <TradeDurationScatter data={chartData} />
      </CardContent>
    </Card>
  )
}
