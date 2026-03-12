import { EChart } from "./EChart"
import { formatUsd } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

interface PnlCurveProps {
  data: {
    dates: string[]
    tooltipDates?: string[]
    dataPoints: { value: number; itemStyle: { color: string } }[]
    colorStops: { offset: number; color: string }[]
  }
  grid?: { left: number; top: number; right: number; bottom: number; containLabel: boolean }
  showYAxisLabel?: boolean
}

export function PnlCurve({ data, grid, showYAxisLabel = true }: PnlCurveProps) {
  const { theme } = useTheme()
  const ct = getChartTheme(theme)

  const option = {
    xAxis: {
      type: "category",
      boundaryGap: false,
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
      formatter: (params: { dataIndex: number; name: string; value: number }[]) => {
        const date = data.tooltipDates?.[params[0].dataIndex] ?? params[0].name
        return `${date}<br/>PnL: ${formatUsd(params[0].value, { showSign: true })}`
      },
    },
    yAxis: {
      type: "value",
      splitLine: {
        show: false,
      },
      axisLabel: {
        show: showYAxisLabel,
        ...ct.axis.axisLabel,
      },
    },
    grid: grid ?? {
      left: 0,
      top: 10,
      right: 10,
      bottom: 0,
      containLabel: true,
    },
    series: [
      {
        data: data.dataPoints,
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
            colorStops: data.colorStops,
          },
        },
      },
    ],
  }

  return <EChart option={option} style={{ height: "100%", width: "100%" }} />
}
