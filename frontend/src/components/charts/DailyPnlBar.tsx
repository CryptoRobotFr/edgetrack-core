import { EChart } from "./EChart"
import { formatUsd } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

interface DailyPnlBarProps {
  data: {
    dates: string[]
    dataPoints: { value: number; itemStyle: { color: string } }[]
  }
}

export function DailyPnlBar({ data }: DailyPnlBarProps) {
  const { theme } = useTheme()
  const ct = getChartTheme(theme)

  const option = {
    xAxis: {
      type: "category",
      boundaryGap: true,
      data: data.dates,
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
          min: -9999,
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
      formatter: (params: { name: string; value: number }[]) => {
        return `${params[0].name}<br/>PnL: ${formatUsd(params[0].value, { showSign: true })}`
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
        data: data.dataPoints.map((point) => ({
          value: point.value,
          itemStyle: point.itemStyle,
        })),
        type: "bar",
      },
    ],
  }

  return <EChart option={option} style={{ height: "100%", width: "100%" }} />
}
