import { EChart } from "./EChart"
import { formatPercent, formatUsd } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

interface DailyReturnsBarProps {
  data: {
    dates: string[]
    tooltipDates?: string[]
    dataPoints: { value: number; itemStyle: { color: string } }[]
    pnls?: number[]
  }
}

export function DailyReturnsBar({ data }: DailyReturnsBarProps) {
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
      formatter: (params: { dataIndex: number; name: string; value: number; color: string }[]) => {
        const p = params[0]
        const idx = p.dataIndex
        const returnPct = p.value
        const color = returnPct >= 0 ? "#59C0A4" : "#EC787E"
        const lines: string[] = [
          `<div style="font-weight:600;margin-bottom:4px">${data.tooltipDates?.[idx] ?? p.name}</div>`,
          `<div style="display:flex;justify-content:space-between;gap:12px">`,
          `<span style="color:${ct.secondaryTextColor}">Return</span>`,
          `<span style="color:${color};font-weight:600">${formatPercent(returnPct, { showSign: true })}</span>`,
          `</div>`,
        ]

        const pnl = data.pnls?.[idx]
        if (pnl != null) {
          const pnlColor = pnl >= 0 ? "#59C0A4" : "#EC787E"
          lines.push(
            `<div style="display:flex;justify-content:space-between;gap:12px">`,
            `<span style="color:${ct.secondaryTextColor}">P&L</span>`,
            `<span style="color:${pnlColor}">${formatUsd(pnl, { showSign: true })}</span>`,
            `</div>`,
          )
        }

        return lines.join("")
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
