import { forwardRef } from "react"
import { EChart } from "@/components/charts/EChart"
import { formatUsd, formatPercent } from "@/lib/formatters"
import { EDGETRACK_LOGO } from "./exchange-icons"

export interface CalendarShareCardProps {
  totalPnl: number
  winRate: number
  winningDays: number
  losingDays: number
  meanPnlPerDay: number
  calendarDays: Array<{
    date: number // timestamp ms
    total_pnl: number
  }>
  monthLabel: string // e.g. "March 2026"
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
const CELL_PROFIT = "rgba(52, 211, 153, 0.3)"
const CELL_LOSS = "rgba(248, 113, 113, 0.3)"
const CELL_EMPTY = "#1a2332"
const CELL_OUTSIDE = "rgba(30, 41, 59, 0.5)"
const TEXT_OUTSIDE = "rgba(148, 163, 184, 0.35)"

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

interface CalendarCell {
  day: number | null
  pnl: number | null
  isOutsideMonth?: boolean
}

function buildCalendarGrid(
  calendarDays: CalendarShareCardProps["calendarDays"],
  monthLabel: string
): CalendarCell[][] {
  const parsed = new Date(`${monthLabel} 1`)
  const year = parsed.getFullYear()
  const month = parsed.getMonth()

  if (isNaN(year) || isNaN(month)) return []

  const daysInMonth = new Date(year, month + 1, 0).getDate()
  // Day of week for first day (0=Sun → convert to Mon-based: 0=Mon..6=Sun)
  const firstDayOfWeek = (new Date(year, month, 1).getDay() + 6) % 7

  // Build lookup from day-of-month → data
  const dayMap = new Map<number, number>()
  for (const d of calendarDays) {
    const dateObj = new Date(d.date)
    if (dateObj.getUTCFullYear() === year && dateObj.getUTCMonth() === month) {
      dayMap.set(dateObj.getUTCDate(), d.total_pnl)
    }
  }

  // Previous month's day count for leading cells
  const daysInPrevMonth = new Date(year, month, 0).getDate()

  // Build grid rows
  const rows: CalendarCell[][] = []
  let currentRow: CalendarCell[] = []

  // Leading cells: days from previous month
  for (let i = 0; i < firstDayOfWeek; i++) {
    const prevDay = daysInPrevMonth - firstDayOfWeek + 1 + i
    currentRow.push({ day: prevDay, pnl: null, isOutsideMonth: true })
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const pnl = dayMap.get(day) ?? null
    currentRow.push({ day, pnl })
    if (currentRow.length === 7) {
      rows.push(currentRow)
      currentRow = []
    }
  }

  // Trailing cells: days from next month
  if (currentRow.length > 0) {
    let nextDay = 1
    while (currentRow.length < 7) {
      currentRow.push({ day: nextDay++, pnl: null, isOutsideMonth: true })
    }
    rows.push(currentRow)
  }

  return rows
}

function getCellColor(pnl: number | null): string {
  if (pnl === null || pnl === 0) return CELL_EMPTY
  return pnl > 0 ? CELL_PROFIT : CELL_LOSS
}

/** Inline ECharts gauge matching WinRateGauge.tsx (dark theme only) */
function getGaugeOption(winRate: number) {
  const normalizedRate = Math.max(0, Math.min(100, winRate))
  const color = `rgb(${255 - (normalizedRate / 100) * 255}, ${(normalizedRate / 100) * 255}, 0)`

  return {
    animation: false,
    series: [
      {
        type: "gauge",
        progress: {
          show: true,
          width: 8,
          itemStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 1,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: "#b91c1c" },
                { offset: 1, color },
              ],
            },
          },
        },
        axisLine: { lineStyle: { width: 8 } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        anchor: {
          show: true,
          showAbove: true,
          size: 4,
          itemStyle: { borderWidth: 6, borderColor: "#ea580c" },
        },
        pointer: {
          show: true,
          width: 3,
          itemStyle: { color: "#ea580c" },
        },
        title: { show: false },
        detail: { show: false },
        data: [{ value: normalizedRate }],
      },
    ],
  }
}

export const CalendarShareCard = forwardRef<HTMLDivElement, CalendarShareCardProps>(
  function CalendarShareCard(props, ref) {
    const {
      totalPnl,
      winRate,
      winningDays,
      losingDays,
      meanPnlPerDay,
      calendarDays,
      monthLabel,
      accountName,
      exchangeAvatarDataUrl,
    } = props

    const pnlColor = totalPnl >= 0 ? PROFIT : LOSS
    const meanPnlColor = meanPnlPerDay >= 0 ? PROFIT : LOSS
    const grid = buildCalendarGrid(calendarDays, monthLabel)
    const totalRows = grid.length

    // Dynamic cell sizing based on grid rows (4-6 possible)
    const cellHeight = totalRows <= 4 ? 100 : totalRows <= 5 ? 84 : 72
    const dayFontSize = totalRows <= 5 ? 14 : 12
    const pnlFontSize = totalRows <= 4 ? 26 : totalRows <= 5 ? 22 : 18

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
          {monthLabel}
        </div>

        {/* Two metric cards (P&L + Win Rate) */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
            marginBottom: 20,
          }}
        >
          {/* P&L Card - matches GlobalMetricsCard design */}
          <div
            style={{
              backgroundColor: SURFACE,
              borderRadius: 16,
              padding: "20px 24px",
            }}
          >
            <div style={{ color: TEXT_SECONDARY, fontSize: 14, marginBottom: 6 }}>
              P&L
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
              <span
                style={{
                  color: pnlColor,
                  fontSize: 34,
                  fontWeight: 700,
                  fontFamily: "'JetBrains Mono', monospace",
                  lineHeight: 1.2,
                }}
              >
                {formatUsd(totalPnl, { showSign: true, withSuffix: false })}
              </span>
              <span style={{ color: pnlColor, fontSize: 16, fontWeight: 600 }}>
                USD
              </span>
            </div>
            <div style={{ color: TEXT_SECONDARY, fontSize: 13, marginTop: 4 }}>
              Mean per day:{" "}
              <span style={{ color: meanPnlColor }}>
                {formatUsd(meanPnlPerDay, { showSign: true, withSuffix: false })}
              </span>{" "}
              USD
            </div>
          </div>

          {/* Win Rate Card - matches GlobalMetricsCard design with gauge */}
          <div
            style={{
              backgroundColor: SURFACE,
              borderRadius: 16,
              padding: "20px 24px",
            }}
          >
            <div style={{ color: TEXT_SECONDARY, fontSize: 14, marginBottom: 6 }}>
              Win Rate
            </div>
            <div style={{ display: "flex", alignItems: "center" }}>
              <div style={{ width: 56, height: 56, marginRight: 12, flexShrink: 0 }}>
                <EChart
                  option={getGaugeOption(winRate)}
                  style={{ height: "100%", width: "100%" }}
                  renderer="svg"
                />
              </div>
              <div>
                <div
                  style={{
                    color: TEXT_PRIMARY,
                    fontSize: 34,
                    fontWeight: 700,
                    lineHeight: 1.2,
                  }}
                >
                  {formatPercent(winRate, { decimals: 0 })}
                </div>
                <div style={{ color: TEXT_SECONDARY, fontSize: 13, marginTop: 2 }}>
                  {winningDays} Win / {losingDays} Loss
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Calendar grid */}
        <div
          style={{
            flex: 1,
            backgroundColor: SURFACE,
            borderRadius: 16,
            padding: 20,
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Day-of-week headers */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(7, 1fr)",
              gap: 6,
              marginBottom: 6,
            }}
          >
            {DAY_LABELS.map((label) => (
              <div
                key={label}
                style={{
                  textAlign: "center",
                  color: TEXT_SECONDARY,
                  fontSize: 13,
                  fontWeight: 500,
                  paddingBottom: 4,
                }}
              >
                {label}
              </div>
            ))}
          </div>

          {/* Calendar rows */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            {grid.map((row, rowIdx) => (
              <div
                key={rowIdx}
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(7, 1fr)",
                  gap: 6,
                  flex: 1,
                }}
              >
                {row.map((cell, colIdx) => (
                  <div
                    key={`${rowIdx}-${colIdx}`}
                    style={{
                      backgroundColor: cell.isOutsideMonth
                        ? CELL_OUTSIDE
                        : getCellColor(cell.pnl),
                      borderRadius: 8,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      minHeight: cellHeight,
                      padding: "6px 0",
                    }}
                  >
                    {/* Day number at top */}
                    <span
                      style={{
                        color: cell.isOutsideMonth ? TEXT_OUTSIDE : TEXT_SECONDARY,
                        fontSize: dayFontSize,
                        fontWeight: 500,
                        lineHeight: 1,
                      }}
                    >
                      {cell.day}
                    </span>
                    {/* PnL centered in remaining space */}
                    {!cell.isOutsideMonth && (
                      <div
                        style={{
                          flex: 1,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        {cell.pnl !== null && cell.pnl !== 0 && (
                          <span
                            style={{
                              color: cell.pnl > 0 ? PROFIT : LOSS,
                              fontSize: pnlFontSize,
                              fontWeight: 600,
                              fontFamily: "'JetBrains Mono', monospace",
                            }}
                          >
                            {formatUsd(cell.pnl, { showSign: true })}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}
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
