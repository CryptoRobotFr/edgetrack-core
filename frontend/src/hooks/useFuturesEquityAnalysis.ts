import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"
import type { DateRange } from "@/hooks/useFuturesAnalysis"

// Manual interface matching backend EquityAnalysisResponse schema.
// Will be replaced by auto-generated types after running `pnpm generate:api`.
export interface EquityPoint {
  date: number
  equity: number
  realized_equity?: number
  unrealized_pnl?: number
}

export interface DailyReturn {
  date: number
  pnl: number
  return_pct: number
}

export interface EquityAnalysisData {
  current_equity: number
  starting_equity: number
  equity_change: number
  equity_change_pct: number
  sharpe_ratio: number | null
  sortino_ratio: number | null
  annualized_volatility: number | null
  max_drawdown_pct: number
  max_drawdown_duration_days: number
  current_drawdown_pct: number
  max_drawdown_amount: number
  best_day_return_pct: number
  worst_day_return_pct: number
  best_day_date: number | null
  worst_day_date: number | null
  profit_factor: number | null
  total_transfers_in: number
  total_transfers_out: number
  net_transfers: number
  equity_curve: EquityPoint[]
  daily_returns: DailyReturn[]
}

export function useFuturesEquityAnalysis(
  accountId: string | null,
  dateRange?: DateRange
) {
  return useQuery({
    queryKey: [
      "futures",
      "equity-analysis",
      accountId,
      dateRange?.startDate,
      dateRange?.endDate,
    ],
    queryFn: async () => {
      if (!accountId) {
        throw new Error("No account selected")
      }
      const { data, error } = await authApi.GET(
        "/api/v1/futures/equity-analysis" as never,
        {
          params: {
            query: {
              account_id: accountId,
              start_date: dateRange?.startDate ?? undefined,
              end_date: dateRange?.endDate ?? undefined,
            },
          },
        } as never
      )
      if (error) {
        throw new Error("Failed to fetch equity analysis data")
      }
      return data as unknown as EquityAnalysisData
    },
    enabled: !!accountId,
  })
}
