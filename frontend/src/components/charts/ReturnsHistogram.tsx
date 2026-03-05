import { EChart } from "./EChart"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

interface ReturnsHistogramProps {
  data: {
    buckets: string[]
    counts: { value: number; itemStyle: { color: string } }[]
  }
  totalDays: number
}

export function ReturnsHistogram({ data, totalDays }: ReturnsHistogramProps) {
  const { theme } = useTheme()
  const ct = getChartTheme(theme)

  const option = {
    xAxis: {
      type: "category",
      data: data.buckets,
      axisTick: {
        show: false,
      },
      axisLabel: {
        rotate: 45,
        fontSize: 10,
        ...ct.axis.axisLabel,
        // Shorten range labels for axis: "X.X% to Y.Y%" -> stacked
        formatter: (value: string) => {
          const match = value.match(/^(.+?) to (.+)$/)
          if (match) return `${match[1]}\n${match[2]}`
          return value
        },
      },
    },
    tooltip: {
      trigger: "axis",
      ...ct.tooltip,
      formatter: (params: { name: string; value: number; color: string }[]) => {
        const p = params[0]
        const pct = totalDays > 0 ? ((p.value / totalDays) * 100).toFixed(1) : "0"
        return [
          `<div style="font-weight:600;margin-bottom:4px">${p.name}</div>`,
          `<div style="display:flex;align-items:center;gap:6px">`,
          `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color}"></span>`,
          `<span>${p.value} day${p.value !== 1 ? "s" : ""}</span>`,
          `<span style="color:${ct.secondaryTextColor};margin-left:4px">(${pct}%)</span>`,
          `</div>`,
        ].join("")
      },
    },
    yAxis: {
      type: "value",
      splitLine: {
        show: false,
      },
      minInterval: 1,
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
        data: data.counts,
        type: "bar",
        barWidth: "80%",
      },
    ],
  }

  return <EChart option={option} style={{ height: "100%", width: "100%" }} />
}
