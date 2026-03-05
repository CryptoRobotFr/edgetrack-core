import { useState } from "react"
import { EChart } from "./EChart"
import { Button } from "@/components/ui/button"
import { BarChart3, ScatterChart } from "lucide-react"
import { formatUsd, formatNumber } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

interface TradeDurationData {
  pnl: number
  duration: number
  tooltip: string
}

interface TradeDurationScatterProps {
  data: {
    winningTrades: TradeDurationData[]
    losingTrades: TradeDurationData[]
  }
}

function calculateAverage(trades: TradeDurationData[]): number {
  if (trades.length === 0) return 0
  const totalDuration = trades.reduce((sum, trade) => sum + trade.duration, 0)
  return totalDuration / trades.length
}

export function TradeDurationScatter({ data }: TradeDurationScatterProps) {
  const [isScatter, setIsScatter] = useState(true)
  const { theme } = useTheme()
  const ct = getChartTheme(theme)

  const winsData = data.winningTrades.map((t) => ({
    value: [t.duration, t.pnl, t.tooltip],
    itemStyle: { color: "#59C0A4" },
  }))

  const lossesData = data.losingTrades.map((t) => ({
    value: [t.duration, t.pnl, t.tooltip],
    itemStyle: { color: "#EC787E" },
  }))

  const scatterOption = {
    xAxis: {
      type: "log",
      min: 0.01,
      axisLabel: {
        ...ct.axis.axisLabel,
        formatter: (value: number) => {
          if (value < 1) return `${Math.round(value * 24)}h`
          return `${value.toFixed(0)}d`
        },
      },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: {
        ...ct.axis.axisLabel,
        formatter: (value: number) => formatUsd(value),
      },
      splitLine: {
        show: false,
      },
    },
    tooltip: {
      trigger: "item",
      ...ct.tooltip,
      formatter: (params: { value: (number | string)[] }) => {
        const [duration, pnl, pair] = params.value as [number, number, string]
        const durationStr =
          duration < 1
            ? `${formatNumber(duration * 24, 2)} hours`
            : `${formatNumber(duration, 2)} days`
        return `<strong>${pair}</strong><br/>Duration: ${durationStr}<br/>PnL: ${formatUsd(pnl, { showSign: true })}`
      },
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
        type: "scatter",
        id: "wins",
        dataGroupId: "wins",
        universalTransition: {
          enabled: true,
          delay: () => Math.random() * 400,
        },
        data: winsData,
      },
      {
        type: "scatter",
        id: "losses",
        dataGroupId: "losses",
        universalTransition: {
          enabled: true,
          delay: () => Math.random() * 400,
        },
        data: lossesData,
      },
    ],
  }

  const barOption = {
    xAxis: {
      type: "category",
      data: ["Wins", "Losses"],
      axisLabel: ct.axis.axisLabel,
    },
    yAxis: {
      type: "value",
      axisLabel: {
        ...ct.axis.axisLabel,
        formatter: (value: number) => `${formatNumber(value, 1)}d`,
      },
      splitLine: {
        show: false,
      },
    },
    tooltip: {
      trigger: "item",
      ...ct.tooltip,
      formatter: (params: { name: string; value: number }) => {
        return `${params.name}: ${formatNumber(params.value, 2)} days avg`
      },
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
        type: "bar",
        id: "total",
        data: [
          {
            value: calculateAverage(data.winningTrades),
            groupId: "wins",
            itemStyle: { color: "#59C0A4" },
          },
          {
            value: calculateAverage(data.losingTrades),
            groupId: "losses",
            itemStyle: { color: "#EC787E" },
          },
        ],
        universalTransition: {
          enabled: true,
          seriesKey: ["wins", "losses"],
          delay: () => Math.random() * 400,
        },
      },
    ],
  }

  const toggleChart = () => {
    setIsScatter(!isScatter)
  }

  const currentOption = isScatter ? scatterOption : barOption

  return (
    <div className="relative h-full w-full">
      <EChart
        option={currentOption}
        style={{ height: "100%", width: "100%" }}
      />
      <div className="absolute right-0 top-0 z-10">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleChart}
          className="h-6 w-6 p-1"
        >
          {isScatter ? (
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ScatterChart className="h-4 w-4 text-muted-foreground" />
          )}
        </Button>
      </div>
    </div>
  )
}
