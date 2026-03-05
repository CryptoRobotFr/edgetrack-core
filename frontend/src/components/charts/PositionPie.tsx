import { EChart } from "./EChart"

interface PositionPieProps {
  longPositions: number
  shortPositions: number
}

export function PositionPie({ longPositions, shortPositions }: PositionPieProps) {
  const total = longPositions + shortPositions
  const longPart = total > 0 ? (longPositions / total) * 100 : 0
  const shortPart = total > 0 ? (shortPositions / total) * 100 : 0

  const option = {
    tooltip: {
      show: false,
    },
    legend: {
      show: false,
    },
    series: [
      {
        name: "Positions",
        type: "pie",
        radius: ["40%", "70%"],
        avoidLabelOverlap: false,
        padAngle: 0,
        itemStyle: {
          borderRadius: 10,
        },
        label: {
          show: false,
          position: "center",
        },
        emphasis: {
          label: {
            show: false,
          },
        },
        labelLine: {
          show: false,
        },
        data: [
          { value: longPart, name: "Long", itemStyle: { color: "#047857" } }, // emerald-700
          { value: shortPart, name: "Short", itemStyle: { color: "#b91c1c" } }, // red-700
        ],
      },
    ],
  }

  return <EChart option={option} style={{ height: "100%", width: "100%" }} />
}
