import { EChart } from "./EChart"
import { formatUsd, formatPercent } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

interface EquityCurveProps {
  data: {
    dates: string[]
    tooltipDates?: string[]
    dataPoints: number[]
    realized?: (number | null)[]
    unrealized?: (number | null)[]
    startingEquity?: number
  }
}

export function EquityCurve({ data }: EquityCurveProps) {
  const { theme } = useTheme()
  const ct = getChartTheme(theme)

  const borderColor = theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"

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
        const equity = p.value
        const lines: string[] = [
          `<div style="font-weight:600;margin-bottom:4px">${data.tooltipDates?.[idx] ?? p.name}</div>`,
          `<div style="display:flex;justify-content:space-between;gap:12px">`,
          `<span style="color:${ct.secondaryTextColor}">Equity</span>`,
          `<span style="font-weight:600">${formatUsd(equity)}</span>`,
          `</div>`,
        ]

        const realized = data.realized?.[idx]
        const unrealized = data.unrealized?.[idx]
        if (realized != null) {
          lines.push(
            `<div style="display:flex;justify-content:space-between;gap:12px">`,
            `<span style="color:${ct.secondaryTextColor}">Realized</span>`,
            `<span>${formatUsd(realized)}</span>`,
            `</div>`,
          )
        }
        if (unrealized != null) {
          const uColor = unrealized >= 0 ? "#59C0A4" : "#EC787E"
          lines.push(
            `<div style="display:flex;justify-content:space-between;gap:12px">`,
            `<span style="color:${ct.secondaryTextColor}">Unrealized</span>`,
            `<span style="color:${uColor}">${formatUsd(unrealized, { showSign: true })}</span>`,
            `</div>`,
          )
        }

        if (data.startingEquity && data.startingEquity !== 0) {
          const change = equity - data.startingEquity
          const changePct = (change / data.startingEquity) * 100
          const color = change >= 0 ? "#59C0A4" : "#EC787E"
          lines.push(
            `<div style="display:flex;justify-content:space-between;gap:12px;margin-top:4px;padding-top:4px;border-top:1px solid ${borderColor}">`,
            `<span style="color:${ct.secondaryTextColor}">P&L</span>`,
            `<span style="color:${color}">${formatUsd(change, { showSign: true })} (${formatPercent(changePct, { showSign: true })})</span>`,
            `</div>`,
          )
        }

        return lines.join("")
      },
    },
    yAxis: {
      type: "value",
      splitLine: {
        lineStyle: {
          color: "rgba(100, 116, 139, 0.15)",
        },
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
          color: "#3B82F6",
        },
        itemStyle: {
          color: "#3B82F6",
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(59, 130, 246, 0.3)" },
              { offset: 1, color: "rgba(59, 130, 246, 0.02)" },
            ],
          },
        },
        ...(data.startingEquity != null
          ? {
              markLine: {
                silent: true,
                symbol: "none",
                label: { show: false },
                lineStyle: {
                  type: "dashed",
                  color: "#64748b",
                  width: 1,
                },
                data: [{ yAxis: data.startingEquity }],
              },
            }
          : {}),
      },
    ],
  }

  return <EChart option={option} style={{ height: "100%", width: "100%" }} />
}
