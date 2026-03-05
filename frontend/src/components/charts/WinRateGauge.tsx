import { EChart } from "./EChart"

interface WinRateGaugeProps {
  winRate: number // 0-100
}

export function WinRateGauge({ winRate }: WinRateGaugeProps) {
  // Dynamic color: red (0%) -> yellow (50%) -> green (100%)
  const normalizedRate = Math.max(0, Math.min(100, winRate))
  const color = `rgb(${255 - (normalizedRate / 100) * 255}, ${(normalizedRate / 100) * 255}, 0)`

  const option = {
    series: [
      {
        type: "gauge",
        progress: {
          show: true,
          width: 5,
          itemStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 1,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: "#b91c1c" }, // red-700
                { offset: 1, color: color },
              ],
            },
          },
        },
        axisLine: {
          lineStyle: {
            width: 5,
          },
        },
        axisTick: {
          show: false,
        },
        splitLine: {
          show: false,
        },
        axisLabel: {
          show: false,
        },
        anchor: {
          show: true,
          showAbove: true,
          size: 2,
          itemStyle: {
            borderWidth: 5,
            borderColor: "#ea580c", // orange-600
          },
        },
        pointer: {
          show: true,
          width: 2,
          itemStyle: {
            color: "#ea580c", // orange-600
          },
        },
        title: {
          show: false,
        },
        detail: {
          show: false,
        },
        data: [
          {
            value: normalizedRate,
          },
        ],
      },
    ],
  }

  return <EChart option={option} style={{ height: "100%", width: "100%" }} />
}
