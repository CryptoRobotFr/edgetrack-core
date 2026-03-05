import { useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ChartBar, HelpCircle } from "lucide-react"
import { PnlByPairBar, type PairData, type AggregatedSide, type PnlByPairBarClickEvent } from "@/components/charts/PnlByPairBar"
import type { TradeListItem } from "@/hooks/useFuturesTrades"

interface PnlByPairChartCardProps {
  trades: TradeListItem[]
  onBarClick?: (event: PnlByPairBarClickEvent) => void
}

function createEmptySide(): AggregatedSide {
  return {
    pnl: 0,
    tradeCount: 0,
    avgPnlPct: 0,
    totalFees: 0,
    avgDurationMs: 0,
    avgSize: 0,
  }
}

export function PnlByPairChartCard({ trades, onBarClick }: PnlByPairChartCardProps) {
  const aggregatedData = useMemo(() => {
    // Group trades by pair and side
    const pairMap = new Map<
      string,
      {
        imageUrl: string | null
        long: { pnl: number; count: number; pnlPctSum: number; fees: number; durationSum: number; sizeSum: number }
        short: { pnl: number; count: number; pnlPctSum: number; fees: number; durationSum: number; sizeSum: number }
      }
    >()

    for (const trade of trades) {
      const pair = trade.pair
      const side = trade.side.toLowerCase()

      if (!pairMap.has(pair)) {
        pairMap.set(pair, {
          imageUrl: trade.base_image_url,
          long: { pnl: 0, count: 0, pnlPctSum: 0, fees: 0, durationSum: 0, sizeSum: 0 },
          short: { pnl: 0, count: 0, pnlPctSum: 0, fees: 0, durationSum: 0, sizeSum: 0 },
        })
      }

      const pairData = pairMap.get(pair)!
      const sideData = side === "long" ? pairData.long : pairData.short

      // Update imageUrl if not set (in case first trade had null)
      if (!pairData.imageUrl && trade.base_image_url) {
        pairData.imageUrl = trade.base_image_url
      }

      sideData.pnl += trade.pnl
      sideData.count += 1
      sideData.pnlPctSum += trade.pnl_pct
      sideData.fees += trade.total_fees
      sideData.durationSum += trade.duration_ms
      sideData.sizeSum += trade.entry_usd_size
    }

    // Convert to array and compute averages
    const result: PairData[] = []

    for (const [pair, data] of pairMap) {
      const longSide: AggregatedSide =
        data.long.count > 0
          ? {
              pnl: data.long.pnl,
              tradeCount: data.long.count,
              avgPnlPct: data.long.pnlPctSum / data.long.count,
              totalFees: data.long.fees,
              avgDurationMs: data.long.durationSum / data.long.count,
              avgSize: data.long.sizeSum / data.long.count,
            }
          : createEmptySide()

      const shortSide: AggregatedSide =
        data.short.count > 0
          ? {
              pnl: data.short.pnl,
              tradeCount: data.short.count,
              avgPnlPct: data.short.pnlPctSum / data.short.count,
              totalFees: data.short.fees,
              avgDurationMs: data.short.durationSum / data.short.count,
              avgSize: data.short.sizeSum / data.short.count,
            }
          : createEmptySide()

      result.push({
        pair,
        imageUrl: data.imageUrl,
        long: longSide,
        short: shortSide,
      })
    }

    // Sort by total absolute PnL (|long PnL| + |short PnL|) descending, keep top 20
    result.sort((a, b) => {
      const absPnlA = Math.abs(a.long.pnl) + Math.abs(a.short.pnl)
      const absPnlB = Math.abs(b.long.pnl) + Math.abs(b.short.pnl)
      return absPnlB - absPnlA
    })

    return result.slice(0, 30)
  }, [trades])

  if (trades.length === 0) {
    return (
      <Card className="h-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              PnL by Pair
            </CardTitle>
          </div>
          <ChartBar className="w-3.5 h-3.5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="pt-0 h-[400px] flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            PnL by Pair
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Profit and loss grouped by trading pair and position side (top 30 by absolute PnL)</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <ChartBar className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[400px] p-4 @container">
        <PnlByPairBar data={aggregatedData} onBarClick={onBarClick} />
      </CardContent>
    </Card>
  )
}
