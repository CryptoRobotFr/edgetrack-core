import { forwardRef } from "react"
import { EChart } from "@/components/charts/EChart"
import { clamp } from "@/lib/chart-utils"
import { formatUsd, formatPercent, formatDate, formatChartDate } from "@/lib/formatters"
import { EDGETRACK_LOGO } from "./exchange-icons"
import type { components } from "@/api/schema"

type DailyAnalysis = components["schemas"]["DailyAnalysis"]

export interface PnlShareCardProps {
  totalPnl: number
  totalTrades: number
  longTrades: number
  shortTrades: number
  winRate: number
  wins: number
  losses: number
  dailyAnalysis: DailyAnalysis[]
  accountName: string
  exchangeName: string
  exchangeAvatarUrl: string | null
  /** Base64 data URL of the exchange avatar, pre-fetched for image capture compatibility */
  exchangeAvatarDataUrl?: string | null
  startDate: number | null
  endDate: number | null
}

// Colors (always dark theme)
const BG = "#0f172a"
const SURFACE = "#1e293b"
const TEXT_PRIMARY = "#f8fafc"
const TEXT_SECONDARY = "#94a3b8"
const PROFIT = "#34d399"
const LOSS = "#f87171"

function buildPnlChartOption(dailyAnalysis: DailyAnalysis[]) {
  if (dailyAnalysis.length === 0) return null

  const cumulativeValues = dailyAnalysis.map((d) => d.cumulative_pnl)
  const maxPnl = Math.max(...cumulativeValues)
  const minPnl = Math.min(...cumulativeValues)

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
      data: dailyAnalysis.map((d) => formatChartDate(d.date)),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: TEXT_SECONDARY, fontSize: 14 },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { color: TEXT_SECONDARY, fontSize: 14 },
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
        data: dailyAnalysis.map((d) => ({
          value: Math.round(d.cumulative_pnl * 100) / 100,
          itemStyle: { color: d.cumulative_pnl >= 0 ? PROFIT : LOSS },
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

export const PnlShareCard = forwardRef<HTMLDivElement, PnlShareCardProps>(
  function PnlShareCard(props, ref) {
    const {
      totalPnl,
      longTrades,
      shortTrades,
      winRate,
      wins,
      losses,
      dailyAnalysis,
      accountName,
      exchangeAvatarDataUrl,
      startDate,
      endDate,
    } = props

    const pnlColor = totalPnl >= 0 ? PROFIT : LOSS
    const chartOption = buildPnlChartOption(dailyAnalysis)

    const periodLabel =
      startDate && endDate
        ? `${formatDate(startDate)} - ${formatDate(endDate)}`
        : "All Time"

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

        {/* Period */}
        <div
          style={{
            color: TEXT_SECONDARY,
            fontSize: 18,
            marginBottom: 24,
          }}
        >
          {periodLabel}
        </div>

        {/* Metrics Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
            marginBottom: 24,
          }}
        >
          {/* Total PnL */}
          <div
            style={{
              backgroundColor: SURFACE,
              borderRadius: 16,
              padding: 24,
            }}
          >
            <div style={{ color: TEXT_SECONDARY, fontSize: 16, marginBottom: 8 }}>
              Total P&L
            </div>
            <div
              style={{
                color: pnlColor,
                fontSize: 40,
                fontWeight: 700,
                fontFamily: "'JetBrains Mono', monospace",
                lineHeight: 1.2,
              }}
            >
              {formatUsd(totalPnl, { showSign: true })}
            </div>
            <div style={{ fontSize: 15, marginTop: 6 }}>
              <span style={{ color: PROFIT }}>{longTrades} Long</span>
              <span style={{ color: TEXT_SECONDARY }}> / </span>
              <span style={{ color: LOSS }}>{shortTrades} Short</span>
            </div>
          </div>

          {/* Win Rate */}
          <div
            style={{
              backgroundColor: SURFACE,
              borderRadius: 16,
              padding: 24,
            }}
          >
            <div style={{ color: TEXT_SECONDARY, fontSize: 16, marginBottom: 8 }}>
              Win Rate
            </div>
            <div
              style={{
                color: TEXT_PRIMARY,
                fontSize: 40,
                fontWeight: 700,
                fontFamily: "'JetBrains Mono', monospace",
                lineHeight: 1.2,
              }}
            >
              {formatPercent(winRate, { decimals: 1 })}
            </div>
            <div style={{ color: TEXT_SECONDARY, fontSize: 15, marginTop: 6 }}>
              {wins}W / {losses}L
            </div>
          </div>
        </div>

        {/* PnL Chart */}
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
            Cumulative PnL
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
