import { useRef, useCallback, useMemo } from "react"
import { EChart } from "./EChart"
import { useContainerBreakpoint } from "@/hooks/useContainerBreakpoint"
import { formatUsd, formatPercent, formatDuration } from "@/lib/formatters"
import { useTheme } from "@/contexts/ThemeContext"
import { getChartTheme } from "@/lib/chart-theme"

export interface AggregatedSide {
  pnl: number
  tradeCount: number
  avgPnlPct: number
  totalFees: number
  avgDurationMs: number
  avgSize: number
}

export interface PairData {
  pair: string
  imageUrl: string | null
  long: AggregatedSide
  short: AggregatedSide
}

export interface PnlByPairBarClickEvent {
  pair: string
  side: "long" | "short"
}

interface PnlByPairBarProps {
  data: PairData[]
  onBarClick?: (event: PnlByPairBarClickEvent) => void
}

// Trading colors from design system
const LONG_COLOR = "#59C0A4"
const SHORT_COLOR = "#EC787E"

// Tooltip formatter for individual bar hover
function formatTooltip(
  seriesName: string,
  pairName: string,
  imageUrl: string | null,
  side: AggregatedSide,
  textColor: string,
  secondaryTextColor: string,
  borderColor: string,
): string {
  const color = seriesName === "Long" ? LONG_COLOR : SHORT_COLOR
  const pnlColor = side.pnl >= 0 ? LONG_COLOR : SHORT_COLOR
  const imgHtml = imageUrl
    ? `<img src="${imageUrl}" style="width: 16px; height: 16px; border-radius: 50%;" />`
    : ""

  return `
    <div style="min-width: 180px;">
      <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid ${borderColor};">
        ${imgHtml}
        <span style="font-weight: 600; color: ${textColor};">${pairName}</span>
        <span style="color: ${color}; font-weight: 500;">${seriesName}</span>
      </div>
      <div style="display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; font-size: 12px;">
        <span style="color: ${secondaryTextColor};">PnL</span>
        <span style="text-align: right; font-weight: 600; color: ${pnlColor};">${formatUsd(side.pnl, { showSign: true })}</span>
        <span style="color: ${secondaryTextColor};">Trades</span>
        <span style="text-align: right; font-weight: 500; color: ${textColor};">${side.tradeCount}</span>
        <span style="color: ${secondaryTextColor};">Avg PnL%</span>
        <span style="text-align: right; font-weight: 500; color: ${side.avgPnlPct >= 0 ? LONG_COLOR : SHORT_COLOR};">${formatPercent(side.avgPnlPct, { showSign: true })}</span>
        <span style="color: ${secondaryTextColor};">Total Fees</span>
        <span style="text-align: right; color: ${textColor};">${formatUsd(side.totalFees)}</span>
        <span style="color: ${secondaryTextColor};">Avg Duration</span>
        <span style="text-align: right; color: ${textColor};">${formatDuration(side.avgDurationMs)}</span>
        <span style="color: ${secondaryTextColor};">Avg Size</span>
        <span style="text-align: right; color: ${textColor};">${formatUsd(side.avgSize)}</span>
      </div>
    </div>
  `
}

export function PnlByPairBar({ data, onBarClick }: PnlByPairBarProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { isMd } = useContainerBreakpoint({ ref: containerRef })
  const isVertical = isMd
  const { theme } = useTheme()
  const ct = getChartTheme(theme)

  // Extract values
  const longValues = data.map((d) => d.long.pnl)
  const shortValues = data.map((d) => d.short.pnl)

  // Build rich text config for axis labels with images
  const richConfig: Record<string, { height: number; width: number; backgroundColor: { image: string } }> = {}
  data.forEach((d, index) => {
    if (d.imageUrl) {
      richConfig[`img${index}`] = {
        height: 16,
        width: 16,
        backgroundColor: {
          image: d.imageUrl,
        },
      }
    }
  })

  // Format axis labels with images
  const axisLabels = data.map((d, index) => {
    if (d.imageUrl) {
      return `{img${index}|} ${d.pair}`
    }
    return d.pair
  })

  // Calculate dynamic height for horizontal mode: 50px per pair, min 250px
  const horizontalHeight = Math.max(250, data.length * 50)

  const tooltipConfig = {
    trigger: "item" as const,
    ...ct.tooltip,
    padding: 12,
    formatter: (params: { seriesName: string; dataIndex: number }) => {
      const pairData = data[params.dataIndex]
      const side = params.seriesName === "Long" ? pairData.long : pairData.short
      if (side.tradeCount === 0) return ""
      return formatTooltip(
        params.seriesName,
        pairData.pair,
        pairData.imageUrl,
        side,
        ct.textColor,
        ct.secondaryTextColor,
        ct.tooltip.borderColor,
      )
    },
  }

  const option = isVertical
    ? {
        // Vertical bars (desktop >=@md)
        xAxis: {
          type: "category",
          data: axisLabels,
          axisTick: { show: false },
          axisLabel: {
            rotate: data.length > 8 ? 45 : 0,
            interval: 0,
            rich: richConfig,
            ...ct.axis.axisLabel,
          },
        },
        yAxis: {
          type: "value",
          splitLine: { show: false },
          axisLabel: ct.axis.axisLabel,
        },
        grid: {
          left: 10,
          top: 30,
          right: 10,
          bottom: data.length > 8 ? 70 : 40,
          containLabel: true,
        },
        legend: {
          data: ["Long", "Short"],
          top: 0,
          right: 0,
          textStyle: { color: ct.legendTextColor },
        },
        tooltip: tooltipConfig,
        series: [
          {
            name: "Long",
            type: "bar",
            data: longValues,
            itemStyle: { color: LONG_COLOR },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(89, 192, 164, 0.5)",
              },
            },
          },
          {
            name: "Short",
            type: "bar",
            data: shortValues,
            itemStyle: { color: SHORT_COLOR },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(236, 120, 126, 0.5)",
              },
            },
          },
        ],
      }
    : {
        // Horizontal bars (mobile <@md)
        xAxis: {
          type: "value",
          splitLine: { show: false },
          axisLabel: ct.axis.axisLabel,
        },
        yAxis: {
          type: "category",
          data: axisLabels,
          axisTick: { show: false },
          inverse: true, // Most traded at top
          axisLabel: {
            rich: richConfig,
            ...ct.axis.axisLabel,
          },
        },
        grid: {
          left: 10,
          top: 30,
          right: 10,
          bottom: 10,
          containLabel: true,
        },
        legend: {
          data: ["Long", "Short"],
          top: 0,
          right: 0,
          textStyle: { color: ct.legendTextColor },
        },
        tooltip: tooltipConfig,
        series: [
          {
            name: "Long",
            type: "bar",
            data: longValues,
            itemStyle: { color: LONG_COLOR },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(89, 192, 164, 0.5)",
              },
            },
          },
          {
            name: "Short",
            type: "bar",
            data: shortValues,
            itemStyle: { color: SHORT_COLOR },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(236, 120, 126, 0.5)",
              },
            },
          },
        ],
      }

  const handleChartClick = useCallback(
    (...args: unknown[]) => {
      const params = args[0] as { seriesName?: string; dataIndex?: number }
      if (!onBarClick || params.dataIndex === undefined || !params.seriesName) return
      const pairData = data[params.dataIndex]
      if (!pairData) return
      const side = params.seriesName === "Long" ? "long" : "short"
      onBarClick({ pair: pairData.pair, side })
    },
    [onBarClick, data]
  )

  const onEvents = useMemo(
    () => (onBarClick ? { click: handleChartClick } : undefined),
    [onBarClick, handleChartClick]
  )

  return (
    <div ref={containerRef} className="w-full h-full">
      <EChart
        option={option}
        style={{
          height: isVertical ? "100%" : `${horizontalHeight}px`,
          width: "100%",
        }}
        notMerge={true}
        onEvents={onEvents}
      />
    </div>
  )
}
