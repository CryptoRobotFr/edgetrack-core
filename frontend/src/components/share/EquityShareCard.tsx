import { forwardRef } from "react"
import { EChart } from "@/components/charts/EChart"
import { formatUsd, formatPercent, formatDate, formatChartDate } from "@/lib/formatters"
import { EDGETRACK_LOGO } from "./exchange-icons"
import type { EquityPoint } from "@/hooks/useFuturesEquityAnalysis"

export interface EquityShareCardProps {
  currentEquity: number
  equityChange: number
  equityChangePct: number
  sharpeRatio: number | null
  profitFactor: number | null
  equityCurve: EquityPoint[]
  startingEquity: number
  accountName: string
  exchangeName: string
  exchangeAvatarUrl: string | null
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
const ORANGE = "#f97316"

const MAX_CHART_POINTS = 500

function downsample(data: EquityPoint[]): EquityPoint[] {
  if (data.length <= MAX_CHART_POINTS) return data
  const step = Math.ceil(data.length / MAX_CHART_POINTS)
  const result: EquityPoint[] = []
  for (let i = 0; i < data.length; i += step) {
    result.push(data[i])
  }
  if (result[result.length - 1] !== data[data.length - 1]) {
    result.push(data[data.length - 1])
  }
  return result
}

function ratioColor(value: number | null): string {
  if (value === null) return TEXT_SECONDARY
  if (value > 1) return PROFIT
  if (value >= 0) return ORANGE
  return LOSS
}

function formatRatio(value: number | null): string {
  if (value === null) return "N/A"
  return value.toFixed(2)
}

function buildEquityChartOption(equityCurve: EquityPoint[], startingEquity: number) {
  if (equityCurve.length === 0) return null

  const sampled = downsample(equityCurve)
  const dates = sampled.map((d) => formatChartDate(d.date))
  const dataPoints = sampled.map((d) => Math.round(d.equity * 100) / 100)

  return {
    animation: false,
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: dates,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: TEXT_SECONDARY, fontSize: 14 },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: SURFACE } },
      axisLabel: { color: TEXT_SECONDARY, fontSize: 14 },
    },
    grid: { left: 10, top: 10, right: 10, bottom: 10, containLabel: true },
    series: [
      {
        data: dataPoints,
        type: "line",
        smooth: false,
        showSymbol: false,
        lineStyle: { color: "#3B82F6", width: 3 },
        itemStyle: { color: "#3B82F6" },
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
        markLine: {
          silent: true,
          symbol: "none",
          label: { show: false },
          lineStyle: {
            type: "dashed",
            color: "#64748b",
            width: 1,
          },
          data: [{ yAxis: startingEquity }],
        },
      },
    ],
  }
}

export const EquityShareCard = forwardRef<HTMLDivElement, EquityShareCardProps>(
  function EquityShareCard(props, ref) {
    const {
      currentEquity,
      equityChange,
      equityChangePct,
      sharpeRatio,
      profitFactor,
      equityCurve,
      startingEquity,
      accountName,
      exchangeAvatarDataUrl,
      startDate,
      endDate,
    } = props

    const changeColor = equityChange >= 0 ? PROFIT : LOSS
    const chartOption = buildEquityChartOption(equityCurve, startingEquity)

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
          {/* Equity */}
          <div
            style={{
              backgroundColor: SURFACE,
              borderRadius: 16,
              padding: 24,
            }}
          >
            <div style={{ color: TEXT_SECONDARY, fontSize: 16, marginBottom: 8 }}>
              Equity
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
              {formatUsd(currentEquity)}
            </div>
            <div style={{ fontSize: 15, marginTop: 6 }}>
              <span style={{ color: changeColor, fontWeight: 600 }}>
                {formatUsd(equityChange, { showSign: true })}
              </span>
              <span style={{ color: changeColor, marginLeft: 6 }}>
                ({formatPercent(equityChangePct, { showSign: true, decimals: 1 })})
              </span>
            </div>
          </div>

          {/* Sharpe Ratio */}
          <div
            style={{
              backgroundColor: SURFACE,
              borderRadius: 16,
              padding: 24,
            }}
          >
            <div style={{ color: TEXT_SECONDARY, fontSize: 16, marginBottom: 8 }}>
              Sharpe Ratio
            </div>
            <div
              style={{
                color: ratioColor(sharpeRatio),
                fontSize: 40,
                fontWeight: 700,
                fontFamily: "'JetBrains Mono', monospace",
                lineHeight: 1.2,
              }}
            >
              {formatRatio(sharpeRatio)}
            </div>
            <div style={{ fontSize: 15, marginTop: 6 }}>
              <span style={{ color: ratioColor(profitFactor) }}>
                Profit Factor: {formatRatio(profitFactor)}
              </span>
            </div>
          </div>
        </div>

        {/* Equity Curve Chart */}
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
            Equity Curve
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
