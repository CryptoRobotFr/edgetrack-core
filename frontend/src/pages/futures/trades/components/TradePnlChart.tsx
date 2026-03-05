import { EChart } from "@/components/charts/EChart"
import { TrendingUp } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useTradePnlEvolution } from "@/hooks/useTradePnlEvolution"
import { clamp } from "@/lib/chart-utils"
import { formatUsd, getDateLocale } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

/**
 * Format timestamp for chart axis based on interval.
 * - 1m, 5m, 15m: show time only (HH:mm)
 * - 1h, 4h: show date + time (MM/DD HH:mm)
 * - 1d: show date only (MM/DD)
 */
function formatAxisLabel(timestamp: number, interval: string): string {
  const date = new Date(timestamp)
  const locale = getDateLocale()

  if (interval === "1d") {
    return date.toLocaleDateString(locale, { month: "2-digit", day: "2-digit" })
  }

  if (interval === "1h" || interval === "4h") {
    const datePart = date.toLocaleDateString(locale, { month: "2-digit", day: "2-digit" })
    const timePart = date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false })
    return `${datePart} ${timePart}`
  }

  // 1m, 5m, 15m - time only
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false })
}

/**
 * Format timestamp for tooltip (always show full date + time).
 */
function formatTooltipDate(timestamp: number): string {
  const date = new Date(timestamp)
  const locale = getDateLocale()
  const datePart = date.toLocaleDateString(locale, { month: "short", day: "numeric", year: "numeric" })
  const timePart = date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false })
  return `${datePart} ${timePart}`
}

interface TradePnlChartProps {
  tradeId: string
}

export function TradePnlChart({ tradeId }: TradePnlChartProps) {
  const { theme } = useTheme()
  const ct = getChartTheme(theme)
  const { data, isLoading, error } = useTradePnlEvolution(tradeId)

  if (isLoading) {
    return (
      <Card className="h-[300px]">
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm">Trade PnL Evolution</CardTitle>
        </CardHeader>
        <CardContent className="h-[240px] p-2">
          <Skeleton className="h-full w-full" />
        </CardContent>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card className="h-[300px]">
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm">Trade PnL Evolution</CardTitle>
        </CardHeader>
        <CardContent className="h-[240px] p-2 flex items-center justify-center">
          <p className="text-muted-foreground text-sm">Failed to load PnL data</p>
        </CardContent>
      </Card>
    )
  }

  if (data.points.length === 0) {
    return (
      <Card className="h-[300px]">
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm">Trade PnL Evolution</CardTitle>
        </CardHeader>
        <CardContent className="h-[240px] p-2 flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  // Calculate bounds for gradient
  const pnlValues = data.points.map((p) => p.pnl)
  const maxPnl = Math.max(...pnlValues)
  const minPnl = Math.min(...pnlValues)

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
  const dates = data.points.map((p) => formatAxisLabel(p.timestamp, data.interval))
  const dataPoints = data.points.map((p) => ({
    value: Math.round(p.pnl * 100) / 100,
    itemStyle: { color: p.pnl >= 0 ? "#59C0A4" : "#EC787E" },
  }))

  const option = {
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: dates,
      axisTick: {
        show: false,
      },
      axisLabel: {
        marginRight: 20,
        ...ct.axis.axisLabel,
      },
    },
    visualMap: {
      show: false,
      pieces: [
        {
          min: -9999999,
          max: 0,
          color: "#EC787E",
        },
        {
          min: 0,
          color: "#59C0A4",
        },
      ],
      outOfRange: {
        color: "#EC787E",
      },
    },
    tooltip: {
      trigger: "axis",
      ...ct.tooltip,
      formatter: (params: { name: string; value: number; dataIndex: number }[]) => {
        const point = data.points[params[0].dataIndex]
        const dateStr = formatTooltipDate(point.timestamp)
        return `${dateStr}<br/>PnL: ${formatUsd(params[0].value, { showSign: true })}`
      },
    },
    yAxis: {
      type: "value",
      splitLine: {
        show: false,
      },
      axisLabel: ct.axis.axisLabel,
    },
    grid: {
      left: 0,
      top: 10,
      right: 10,
      bottom: 0,
      containLabel: true,
    },
    series: [
      {
        data: dataPoints,
        type: "line",
        smooth: true,
        showSymbol: false,
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: colorStops,
          },
        },
      },
    ],
  }

  return (
    <Card className="h-[300px]">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-2">
        <CardTitle className="text-sm">Trade PnL Evolution</CardTitle>
        <TrendingUp className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[240px] p-2">
        <EChart option={option} style={{ height: "100%", width: "100%" }} />
      </CardContent>
    </Card>
  )
}
