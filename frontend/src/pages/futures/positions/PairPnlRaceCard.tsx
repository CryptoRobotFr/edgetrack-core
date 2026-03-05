import { EChart } from "@/components/charts/EChart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Trophy } from "lucide-react"
import { formatUsd } from "@/lib/formatters"
import type { PairHourlyPnl } from "@/hooks/useHourlyPnl"

function formatHourLabel(timestampMs: number): string {
  const date = new Date(timestampMs)
  const month = date.toLocaleDateString("en-US", { month: "short" })
  const day = date.getUTCDate()
  const hours = String(date.getUTCHours()).padStart(2, "0")
  return `${month} ${day} ${hours}:00`
}

interface PairPnlRaceCardProps {
  data: PairHourlyPnl[] | undefined
}

export function PairPnlRaceCard({ data }: PairPnlRaceCardProps) {
  if (!data || data.length === 0) {
    return (
      <Card className="h-[350px]">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            PnL by Pair (7d)
          </CardTitle>
          <Trophy className="w-3.5 h-3.5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="pt-0 h-[280px] flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  // Keep only top 10 pairs by absolute final PnL
  const pairsWithFinalPnl = data.map((pair) => {
    const lastPoint = pair.data_points[pair.data_points.length - 1]
    return { pair, absPnl: lastPoint ? Math.abs(lastPoint.pnl) : 0 }
  })
  pairsWithFinalPnl.sort((a, b) => b.absPnl - a.absPnl)
  const topPairs = pairsWithFinalPnl.slice(0, 10).map((p) => p.pair)

  // Collect all unique timestamps across top pairs
  const allTimestamps = new Set<number>()
  for (const pair of topPairs) {
    for (const point of pair.data_points) {
      allTimestamps.add(point.timestamp)
    }
  }
  const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b)
  const categories = sortedTimestamps.map(formatHourLabel)

  // Build series per pair
  const series = topPairs.map((pair) => {
    const pnlByTimestamp = new Map(
      pair.data_points.map((p) => [p.timestamp, p.pnl])
    )

    // Forward-fill: for each timestamp, use the last known value
    const values: (number | null)[] = []
    let lastValue: number | null = null
    for (const ts of sortedTimestamps) {
      const val = pnlByTimestamp.get(ts)
      if (val !== undefined) {
        lastValue = val
      }
      values.push(lastValue)
    }

    const baseName = pair.pair.replace(/\/(USDT|USDC)$/i, "")
    const finalPnl = lastValue ?? 0

    return {
      name: baseName,
      type: "line" as const,
      showSymbol: false,
      smooth: true,
      data: values,
      endLabel: {
        show: true,
        formatter: (params: { seriesName: string; value: number | null }) => {
          const val = params.value ?? 0
          return `${params.seriesName}: ${formatUsd(val, { showSign: true })}`
        },
        fontSize: 11,
        color: finalPnl >= 0 ? "#059669" : "#dc2626",
      },
      emphasis: {
        focus: "series" as const,
      },
      animationDuration: 3000,
    }
  })

  const option = {
    tooltip: {
      trigger: "axis",
      order: "valueDesc",
      formatter: (params: { seriesName: string; value: number | null; color: string }[]) => {
        const header = params[0] ? `<strong>${(params[0] as { axisValueLabel?: string }).axisValueLabel || ""}</strong><br/>` : ""
        const lines = params
          .filter((p) => p.value !== null)
          .map(
            (p) =>
              `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${p.color};margin-right:5px;"></span>${p.seriesName}: ${formatUsd(p.value ?? 0, { showSign: true })}`
          )
          .join("<br/>")
        return header + lines
      },
    },
    legend: {
      show: false,
    },
    grid: {
      left: 0,
      top: 10,
      right: 105,
      bottom: 0,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: categories,
      axisTick: { show: false },
      axisLabel: {
        interval: Math.max(Math.floor(categories.length / 6) - 1, 0),
      },
    },
    yAxis: {
      type: "value",
      splitLine: { show: false },
      axisLabel: { show: false },
    },
    series,
    labelLayout: {
      moveOverlap: "shiftY",
    },
  }

  return (
    <Card className="h-[350px]">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <CardTitle className="text-lg font-semibold text-muted-foreground">
          PnL by Pair (7d)
        </CardTitle>
        <Trophy className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[280px] px-4 pt-2 pb-1">
        <EChart
          option={option}
          style={{ height: "100%", width: "100%" }}
        />
      </CardContent>
    </Card>
  )
}
