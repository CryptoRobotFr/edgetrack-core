/**
 * TypeScript types for the futures calendar feature.
 */

import type { components } from "@/api/schema"

// API Response Types (re-exported from generated schema)
export type CalendarTradeInfo = components["schemas"]["CalendarTradeInfo"]
export type CalendarDayResponse = components["schemas"]["CalendarDayResponse"]
export type CalendarResponse = components["schemas"]["CalendarResponse"]

// Frontend-specific types

export type ViewMode = "simple" | "detailed" | "minimal"
export type CalendarViewMode = "month" | "week"

export interface CalendarDay {
  date: Date
  isCurrentMonth: boolean
  dailyData?: DailyData
}

export interface DailyData {
  totalPnL: number
  longCount: number
  shortCount: number
  longPnL: number
  shortPnL: number
  trades: TradeWithPosition[]
  maxPositions: number
}

export interface TradeWithPosition extends CalendarTradeInfo {
  position?: number
}
