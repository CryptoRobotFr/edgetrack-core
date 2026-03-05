import { EChart } from "./EChart"
import { formatPercent, formatUsd } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

interface EquityDrawdownCurveProps {
  data: {
    dates: string[]
    dataPoints: number[]
    equities?: number[]
    peaks?: number[]
  }
}

export function EquityDrawdownCurve({ data }: EquityDrawdownCurveProps) {
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
    tooltip: {
      trigger: "axis",
      ...ct.tooltip,
      formatter: (params: { dataIndex: number; name: string; value: number; color: string }[]) => {
        const p = params[0]
        const idx = p.dataIndex
        const dd = p.value
        const ddColor = dd === 0 ? "#59C0A4" : "#EC787E"
        const lines: string[] = [
          `<div style="font-weight:600;margin-bottom:4px">${p.name}</div>`,
          `<div style="display:flex;justify-content:space-between;gap:12px">`,
          `<span style="color:${ct.secondaryTextColor}">Drawdown</span>`,
          `<span style="color:${ddColor};font-weight:600">${formatPercent(dd)}</span>`,
          `</div>`,
        ]

        const equity = data.equities?.[idx]
        if (equity != null) {
          lines.push(
            `<div style="display:flex;justify-content:space-between;gap:12px">`,
            `<span style="color:${ct.secondaryTextColor}">Equity</span>`,
            `<span>${formatUsd(equity)}</span>`,
            `</div>`,
          )
        }

        const peak = data.peaks?.[idx]
        if (peak != null) {
          lines.push(
            `<div style="display:flex;justify-content:space-between;gap:12px">`,
            `<span style="color:${ct.secondaryTextColor}">Peak</span>`,
            `<span>${formatUsd(peak)}</span>`,
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
        data: data.dataPoints,
        type: "line",
        smooth: false,
        showSymbol: false,
        lineStyle: {
          color: "#EC787E",
        },
        itemStyle: {
          color: "#EC787E",
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(236, 120, 126, 0.05)" },
              { offset: 1, color: "rgba(236, 120, 126, 0.3)" },
            ],
          },
        },
      },
    ],
  }

  return <EChart option={option} style={{ height: "100%", width: "100%" }} />
}
