import { forwardRef } from "react"
import { EChart } from "@/components/charts/EChart"
import { clamp } from "@/lib/chart-utils"
import { formatUsd, formatPercent, formatDate, formatPrice } from "@/lib/formatters"
import { EDGETRACK_LOGO } from "./exchange-icons"

export interface PositionsShareCardProps {
  equity: number
  unrealizedPnl: number
  realizedPnl: number
  positions: Array<{
    pair: string
    side: string
    unrealized_pnl: number
    size: number
    usd_size: number
    leverage: number
    entry_price: number
    mark_price: number
    pnl_pct: number
    price_decimals: number
    size_decimals: number
  }>
  hourlyPnl: Array<{
    timestamp: number
    pnl: number
  }>
  accountName: string
  exchangeName: string
  exchangeAvatarUrl: string | null
  exchangeAvatarDataUrl?: string | null
}

// Colors (always dark theme)
const BG = "#0f172a"
const SURFACE = "#1e293b"
const TEXT_PRIMARY = "#f8fafc"
const TEXT_SECONDARY = "#94a3b8"
const PROFIT = "#34d399"
const LOSS = "#f87171"

const MAX_POSITIONS = 5

function formatHourLabel(timestampMs: number): string {
  const date = new Date(timestampMs)
  const month = date.toLocaleDateString("en-US", { month: "short" })
  const day = date.getUTCDate()
  const hours = String(date.getUTCHours()).padStart(2, "0")
  return `${month} ${day} ${hours}:00`
}

function buildPnlChartOption(hourlyPnl: PositionsShareCardProps["hourlyPnl"]) {
  if (hourlyPnl.length === 0) return null

  const pnlValues = hourlyPnl.map((d) => d.pnl)
  const maxPnl = Math.max(...pnlValues)
  const minPnl = Math.min(...pnlValues)

  let colorStops: { offset: number; color: string }[]
  if (minPnl >= 0) {
    colorStops = [
      { offset: 0, color: "rgba(52, 211, 153, 0.6)" },
      { offset: 1, color: "rgba(52, 211, 153, 0.05)" },
    ]
  } else if (maxPnl <= 0) {
    colorStops = [
      { offset: 0, color: "rgba(248, 113, 113, 0.05)" },
      { offset: 1, color: "rgba(248, 113, 113, 0.6)" },
    ]
  } else {
    const pctOffset = clamp(maxPnl / (maxPnl - minPnl), 0, 1)
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
      data: hourlyPnl.map((d) => formatHourLabel(d.timestamp)),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: TEXT_SECONDARY, fontSize: 12, interval: "auto" },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { color: TEXT_SECONDARY, fontSize: 12 },
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
        data: hourlyPnl.map((d) => ({
          value: Math.round(d.pnl * 100) / 100,
          itemStyle: { color: d.pnl >= 0 ? PROFIT : LOSS },
        })),
        type: "line",
        smooth: true,
        showSymbol: false,
        lineWidth: 2,
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

function formatSizeNumber(size: number, decimals: number): string {
  return size.toLocaleString("en-US", {
    minimumFractionDigits: Math.min(decimals, 4),
    maximumFractionDigits: Math.min(decimals, 4),
  })
}

export const PositionsShareCard = forwardRef<HTMLDivElement, PositionsShareCardProps>(
  function PositionsShareCard(props, ref) {
    const {
      equity,
      unrealizedPnl,
      realizedPnl,
      positions,
      hourlyPnl,
      accountName,
      exchangeAvatarDataUrl,
    } = props

    const unrealizedColor = unrealizedPnl >= 0 ? PROFIT : LOSS
    const realizedColor = realizedPnl >= 0 ? PROFIT : LOSS
    const unrealizedPct = equity !== 0 ? (unrealizedPnl / equity) * 100 : 0
    const marketExposure = positions.reduce((sum, p) => sum + p.usd_size, 0)

    const now = new Date()
    const dateLabel = formatDate(now.getTime())

    // Sort by abs(unrealized_pnl) desc and take top 5
    const topPositions = [...positions]
      .sort((a, b) => Math.abs(b.unrealized_pnl) - Math.abs(a.unrealized_pnl))
      .slice(0, MAX_POSITIONS)
    const overflowCount = positions.length - MAX_POSITIONS

    const chartOption = buildPnlChartOption(hourlyPnl)

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
            marginBottom: 8,
          }}
        >
          {/* Left: Logo + Brand */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <img
              src={EDGETRACK_LOGO}
              width={40}
              height={40}
              style={{ borderRadius: 10 }}
            />
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
          {/* Right: Account badge */}
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
              <img
                src={exchangeAvatarDataUrl}
                width={20}
                height={20}
                style={{ borderRadius: 4 }}
              />
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

        {/* Period label */}
        <div
          style={{
            color: TEXT_SECONDARY,
            fontSize: 18,
            marginBottom: 20,
          }}
        >
          Live Snapshot &middot; {dateLabel}
        </div>

        {/* Main metrics row (2 columns) */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
            marginBottom: 16,
          }}
        >
          {/* Equity */}
          <div
            style={{
              backgroundColor: SURFACE,
              borderRadius: 16,
              padding: "20px 24px",
            }}
          >
            <div style={{ color: TEXT_SECONDARY, fontSize: 15, marginBottom: 6 }}>
              Equity
            </div>
            <div
              style={{
                color: TEXT_PRIMARY,
                fontSize: 36,
                fontWeight: 700,
                fontFamily: "'JetBrains Mono', monospace",
                lineHeight: 1.2,
              }}
            >
              {formatUsd(equity)}
            </div>
            <div style={{ color: TEXT_SECONDARY, fontSize: 14, marginTop: 6 }}>
              Market Exposure: <span style={{ color: TEXT_PRIMARY, fontWeight: 500 }}>{formatUsd(marketExposure)}</span>
            </div>
          </div>

          {/* Unrealized P&L */}
          <div
            style={{
              backgroundColor: SURFACE,
              borderRadius: 16,
              padding: "20px 24px",
            }}
          >
            <div style={{ color: TEXT_SECONDARY, fontSize: 15, marginBottom: 6 }}>
              Unrealized P&L
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <span
                style={{
                  color: unrealizedColor,
                  fontSize: 36,
                  fontWeight: 700,
                  fontFamily: "'JetBrains Mono', monospace",
                  lineHeight: 1.2,
                }}
              >
                {formatUsd(unrealizedPnl, { showSign: true })}
              </span>
              <span
                style={{
                  color: unrealizedColor,
                  fontSize: 18,
                  fontWeight: 500,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                ({formatPercent(unrealizedPct, { showSign: true, decimals: 1 })})
              </span>
            </div>
            <div style={{ fontSize: 14, marginTop: 6 }}>
              <span style={{ color: TEXT_SECONDARY }}>Realized P&L: </span>
              <span style={{ color: realizedColor, fontWeight: 500 }}>
                {formatUsd(realizedPnl, { showSign: true })}
              </span>
            </div>
          </div>
        </div>

        {/* Positions list */}
        <div
          style={{
            backgroundColor: SURFACE,
            borderRadius: 16,
            padding: "16px 20px",
            marginBottom: 16,
          }}
        >
          <div style={{ color: TEXT_SECONDARY, fontSize: 15, marginBottom: 10 }}>
            Open Positions ({positions.length})
          </div>

          {positions.length === 0 ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: TEXT_SECONDARY,
                fontSize: 16,
                padding: "20px 0",
              }}
            >
              No open positions
            </div>
          ) : (
            <>
              {/* Header row */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "2.2fr 1.8fr 1.8fr 1.2fr 1.2fr",
                  gap: 8,
                  paddingBottom: 8,
                  borderBottom: "1px solid #334155",
                  marginBottom: 2,
                }}
              >
                {["Pair", "Size", "Unrealized", "Entry", "Mark"].map((header) => (
                  <div
                    key={header}
                    style={{
                      color: TEXT_SECONDARY,
                      fontSize: 12,
                      fontWeight: 500,
                    }}
                  >
                    {header}
                  </div>
                ))}
              </div>

              {/* Position rows */}
              {topPositions.map((pos, i) => {
                const sideColor = pos.side.toUpperCase() === "LONG" ? PROFIT : LOSS
                const pnlColor = pos.unrealized_pnl >= 0 ? PROFIT : LOSS
                return (
                  <div
                    key={`${pos.pair}-${pos.side}-${i}`}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "2.2fr 1.8fr 1.8fr 1.2fr 1.2fr",
                      gap: 8,
                      padding: "9px 0",
                      borderBottom: i < topPositions.length - 1 ? "1px solid #1a2332" : "none",
                      alignItems: "center",
                    }}
                  >
                    {/* Pair + Side + Leverage */}
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span
                        style={{
                          color: TEXT_PRIMARY,
                          fontSize: 14,
                          fontWeight: 600,
                        }}
                      >
                        {pos.pair}
                      </span>
                      <span
                        style={{
                          color: sideColor,
                          fontSize: 11,
                          fontWeight: 600,
                          backgroundColor: pos.side.toUpperCase() === "LONG"
                            ? "rgba(52, 211, 153, 0.15)"
                            : "rgba(248, 113, 113, 0.15)",
                          padding: "2px 5px",
                          borderRadius: 3,
                        }}
                      >
                        {pos.side.toUpperCase()}
                      </span>
                      <span
                        style={{
                          color: TEXT_SECONDARY,
                          fontSize: 11,
                        }}
                      >
                        {pos.leverage}x
                      </span>
                    </div>

                    {/* Size: real size (usd) */}
                    <div
                      style={{
                        color: TEXT_PRIMARY,
                        fontSize: 13,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {formatSizeNumber(pos.size, pos.size_decimals)}
                      <span style={{ color: TEXT_SECONDARY, fontSize: 11, marginLeft: 4 }}>
                        ({formatUsd(pos.usd_size)})
                      </span>
                    </div>

                    {/* Unrealized P&L (%) */}
                    <div
                      style={{
                        color: pnlColor,
                        fontSize: 13,
                        fontWeight: 600,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {formatUsd(pos.unrealized_pnl, { showSign: true })}
                      <span style={{ fontSize: 11, marginLeft: 4, fontWeight: 400 }}>
                        ({formatPercent(pos.pnl_pct, { showSign: true, decimals: 1 })})
                      </span>
                    </div>

                    {/* Entry Price */}
                    <div
                      style={{
                        color: TEXT_SECONDARY,
                        fontSize: 13,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {formatPrice(pos.entry_price, { decimals: pos.price_decimals })}
                    </div>

                    {/* Mark Price */}
                    <div
                      style={{
                        color: TEXT_PRIMARY,
                        fontSize: 13,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {formatPrice(pos.mark_price, { decimals: pos.price_decimals })}
                    </div>
                  </div>
                )
              })}

              {/* Overflow text */}
              {overflowCount > 0 && (
                <div
                  style={{
                    color: TEXT_SECONDARY,
                    fontSize: 13,
                    textAlign: "center",
                    paddingTop: 8,
                  }}
                >
                  +{overflowCount} more position{overflowCount > 1 ? "s" : ""}
                </div>
              )}
            </>
          )}
        </div>

        {/* 7-day PnL chart */}
        <div
          style={{
            flex: 1,
            backgroundColor: SURFACE,
            borderRadius: 16,
            padding: "16px 20px",
            minHeight: 0,
          }}
        >
          <div style={{ color: TEXT_SECONDARY, fontSize: 15, marginBottom: 6 }}>
            Account PnL (7d)
          </div>
          <div style={{ height: "calc(100% - 28px)" }}>
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
                  fontSize: 14,
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
            marginTop: 16,
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
