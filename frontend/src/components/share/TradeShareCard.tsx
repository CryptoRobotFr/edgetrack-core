import { forwardRef } from "react"
import { EChart } from "@/components/charts/EChart"
import { clamp } from "@/lib/chart-utils"
import { formatUsd, formatPercent, formatPrice } from "@/lib/formatters"
import { EDGETRACK_LOGO } from "./exchange-icons"

export interface TradeShareCardProps {
  // Trade identity
  pair: string
  base: string
  side: "long" | "short"
  leverage: number | null
  marginMode: string

  // Performance
  pnlPct: number
  pnl: number

  // Prices
  meanEntryPrice: number
  exitOrMarkPrice: number
  exitOrMarkLabel: string

  // PnL evolution chart data
  pnlPoints: { timestamp: number; pnl: number }[]
  pnlInterval: string
  entryUsdSize: number

  // Trade status
  isRunning: boolean

  // Display mode
  showUsdPnl?: boolean

  // Account / branding
  accountName: string
  exchangeName: string
  exchangeAvatarDataUrl?: string | null
}

// Colors (always dark theme)
const BG = "#0f172a"
const SURFACE = "#1e293b"
const TEXT_PRIMARY = "#f8fafc"
const TEXT_SECONDARY = "#94a3b8"
const PROFIT = "#34d399"
const LOSS = "#f87171"

function formatAxisLabel(timestamp: number, interval: string): string {
  const date = new Date(timestamp)

  if (interval === "1d") {
    return date.toLocaleDateString("en-US", { month: "2-digit", day: "2-digit" })
  }

  if (interval === "1h" || interval === "4h") {
    const datePart = date.toLocaleDateString("en-US", { month: "2-digit", day: "2-digit" })
    const timePart = date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })
    return `${datePart} ${timePart}`
  }

  return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })
}

function buildPnlChartOption(
  points: { timestamp: number; pnl: number }[],
  interval: string,
  showUsdPnl: boolean,
  entryUsdSize: number
) {
  if (points.length === 0) return null

  const values = points.map((p) =>
    showUsdPnl ? Math.round(p.pnl * 100) / 100 : Math.round((p.pnl / entryUsdSize) * 10000) / 100
  )

  const maxVal = Math.max(...values)
  const minVal = Math.min(...values)

  let colorStops: { offset: number; color: string }[]
  if (minVal >= 0) {
    colorStops = [
      { offset: 0, color: "rgba(52, 211, 153, 0.6)" },
      { offset: 1, color: "rgba(52, 211, 153, 0.05)" },
    ]
  } else if (maxVal <= 0) {
    colorStops = [
      { offset: 0, color: "rgba(248, 113, 113, 0.05)" },
      { offset: 1, color: "rgba(248, 113, 113, 0.6)" },
    ]
  } else {
    const pctOffset = clamp(maxVal / (maxVal - minVal), 0, 1)
    colorStops = [
      { offset: 0, color: "rgba(52, 211, 153, 0.6)" },
      { offset: clamp(pctOffset - 0.001, 0, 1), color: "rgba(52, 211, 153, 0.05)" },
      { offset: pctOffset, color: "transparent" },
      { offset: clamp(pctOffset + 0.001, 0, 1), color: "rgba(248, 113, 113, 0.05)" },
      { offset: 1, color: "rgba(248, 113, 113, 0.6)" },
    ]
  }

  return {
    animation: false,
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((p) => formatAxisLabel(p.timestamp, interval)),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: TEXT_SECONDARY, fontSize: 14 },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: {
        color: TEXT_SECONDARY,
        fontSize: 14,
        formatter: showUsdPnl ? (v: number) => `${v}$` : (v: number) => `${v}%`,
      },
    },
    grid: { left: 10, top: 10, right: 10, bottom: 10, containLabel: true },
    visualMap: {
      show: false,
      pieces: [
        { min: -999999999, max: 0, color: LOSS },
        { min: 0, color: PROFIT },
      ],
      outOfRange: { color: LOSS },
    },
    series: [
      {
        data: values.map((v) => ({
          value: v,
          itemStyle: { color: v >= 0 ? PROFIT : LOSS },
        })),
        type: "line",
        smooth: true,
        showSymbol: false,
        lineWidth: 3,
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops,
          },
        },
      },
    ],
  }
}

export const TradeShareCard = forwardRef<HTMLDivElement, TradeShareCardProps>(
  function TradeShareCard(props, ref) {
    const {
      pair,
      side,
      leverage,
      marginMode,
      pnlPct,
      pnl,
      meanEntryPrice,
      exitOrMarkPrice,
      exitOrMarkLabel,
      pnlPoints,
      pnlInterval,
      entryUsdSize,
      isRunning,
      showUsdPnl = false,
      accountName,
      exchangeAvatarDataUrl,
    } = props

    const isProfitable = pnl >= 0
    const pnlColor = isProfitable ? PROFIT : LOSS
    const sideColor = side === "long" ? PROFIT : LOSS
    const leveragedPct = pnlPct * (leverage ?? 1)
    const chartOption = buildPnlChartOption(pnlPoints, pnlInterval, showUsdPnl, entryUsdSize)

    return (
      <div
        ref={ref}
        style={{
          width: 1080,
          height: 1080,
          backgroundColor: BG,
          padding: 48,
          display: "flex",
          flexDirection: "column",
          fontFamily: "'Inter', system-ui, sans-serif",
          boxSizing: "border-box",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 32,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <img src={EDGETRACK_LOGO} width={40} height={40} style={{ borderRadius: 10 }} />
            <span
              style={{
                color: TEXT_PRIMARY,
                fontSize: 26,
                fontWeight: 700,
                letterSpacing: "-0.02em",
              }}
            >
              EdgeTrack
            </span>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              backgroundColor: SURFACE,
              borderRadius: 8,
              padding: "8px 16px",
            }}
          >
            {exchangeAvatarDataUrl && (
              <img src={exchangeAvatarDataUrl} width={20} height={20} style={{ borderRadius: 4 }} />
            )}
            <span
              style={{
                color: TEXT_SECONDARY,
                fontSize: 16,
                fontWeight: 500,
                maxWidth: 200,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {accountName}
            </span>
          </div>
        </div>

        {/* Pair info */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 8 }}>
            <span
              style={{
                color: TEXT_PRIMARY,
                fontSize: 42,
                fontWeight: 700,
                letterSpacing: "-0.02em",
              }}
            >
              {pair}
            </span>
            <span
              style={{
                fontSize: 14,
                fontWeight: 600,
                padding: "4px 12px",
                borderRadius: 6,
                backgroundColor: isRunning ? "rgba(59, 130, 246, 0.2)" : "rgba(251, 146, 60, 0.2)",
                color: isRunning ? "#60a5fa" : "#fb923c",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              {isRunning ? "Running" : "Closed"}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 18 }}>
            <span style={{ color: TEXT_SECONDARY }}>Perpetual</span>
            <span style={{ color: TEXT_SECONDARY }}>|</span>
            <span style={{ color: sideColor, fontWeight: 600 }}>
              {side === "long" ? "Long" : "Short"}
            </span>
            <span style={{ color: TEXT_SECONDARY }}>|</span>
            <span style={{ color: TEXT_SECONDARY }}>
              {marginMode.charAt(0).toUpperCase() + marginMode.slice(1)}
            </span>
            {leverage && (
              <>
                <span style={{ color: TEXT_SECONDARY }}>|</span>
                <span style={{ color: TEXT_PRIMARY, fontWeight: 600 }}>{leverage}x</span>
              </>
            )}
          </div>
        </div>

        {/* Big performance number */}
        <div style={{ marginBottom: 24 }}>
          {!showUsdPnl ? (
            <div
              style={{
                color: pnlColor,
                fontSize: 80,
                fontWeight: 700,
                fontFamily: "'JetBrains Mono', monospace",
                lineHeight: 1.2,
              }}
            >
              {formatPercent(leveragedPct, { showSign: true })}
            </div>
          ) : (
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 16,
              }}
            >
              <span
                style={{
                  color: pnlColor,
                  fontSize: 72,
                  fontWeight: 700,
                  fontFamily: "'JetBrains Mono', monospace",
                  lineHeight: 1.2,
                }}
              >
                {formatUsd(pnl, { showSign: true })}
              </span>
              <span
                style={{
                  color: pnlColor,
                  fontSize: 28,
                  fontFamily: "'JetBrains Mono', monospace",
                  opacity: 0.8,
                }}
              >
                ({formatPercent(leveragedPct, { showSign: true })})
              </span>
            </div>
          )}
        </div>

        {/* Price metrics row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 16,
            marginBottom: 24,
          }}
        >
          <div style={{ backgroundColor: SURFACE, borderRadius: 16, padding: 20 }}>
            <div style={{ color: TEXT_SECONDARY, fontSize: 15, marginBottom: 6 }}>
              Entry Price
            </div>
            <div
              style={{
                color: TEXT_PRIMARY,
                fontSize: 24,
                fontWeight: 600,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {formatPrice(meanEntryPrice)}$
            </div>
          </div>
          <div style={{ backgroundColor: SURFACE, borderRadius: 16, padding: 20 }}>
            <div style={{ color: TEXT_SECONDARY, fontSize: 15, marginBottom: 6 }}>
              {exitOrMarkLabel}
            </div>
            <div
              style={{
                color: TEXT_PRIMARY,
                fontSize: 24,
                fontWeight: 600,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {formatPrice(exitOrMarkPrice)}$
            </div>
          </div>
          <div style={{ backgroundColor: SURFACE, borderRadius: 16, padding: 20 }}>
            <div style={{ color: TEXT_SECONDARY, fontSize: 15, marginBottom: 6 }}>
              Perf. (w/o leverage)
            </div>
            <div
              style={{
                color: pnlColor,
                fontSize: 24,
                fontWeight: 600,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {formatPercent(pnlPct, { showSign: true })}
            </div>
          </div>
        </div>

        {/* PnL Evolution chart */}
        <div
          style={{
            flex: 1,
            backgroundColor: SURFACE,
            borderRadius: 16,
            padding: 20,
            minHeight: 0,
          }}
        >
          <div style={{ color: TEXT_SECONDARY, fontSize: 16, marginBottom: 8 }}>
            PnL Evolution
          </div>
          <div style={{ height: "calc(100% - 32px)" }}>
            {chartOption ? (
              <EChart
                option={chartOption}
                style={{ height: "100%", width: "100%" }}
              />
            ) : (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  color: TEXT_SECONDARY,
                  fontSize: 16,
                }}
              >
                No chart data
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: 20,
          }}
        >
          <span style={{ color: TEXT_SECONDARY, fontSize: 15 }}>
            edge-track.com
          </span>
          <span style={{ color: TEXT_SECONDARY, fontSize: 15 }}>
            Powered by EdgeTrack
          </span>
        </div>
      </div>
    )
  }
)
