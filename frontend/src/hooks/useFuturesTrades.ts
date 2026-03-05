import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface DateRange {
  startDate: number | null
  endDate: number | null
}

export interface TradeListItem {
  id: string
  pair: string
  base: string
  quote: string
  side: string
  entry_date: number
  exit_date: number | null
  last_update_date: number
  mean_entry_price: number
  mean_exit_price: number | null
  entry_size: number
  exit_size: number
  entry_usd_size: number
  exit_usd_size: number
  pnl: number
  pnl_pct: number
  equity_pct_pnl: number
  fees: number
  funding_fees: number
  total_fees: number
  status: string
  leverage: number | null
  margin_mode: string
  position_mode: string
  rating: number
  notes: string
  duration_ms: number
  duration_bucket: string  // "<1h", "<1d", "<1w", ">1w"
  order_count: number
  base_image_url: string | null
  size_decimals: number
}

export interface TradeListResponse {
  trades: TradeListItem[]
  total: number
}

export function useFuturesTrades(
  accountId: string | null,
  dateRange?: DateRange
) {
  return useQuery({
    queryKey: ["futures", "trades", accountId, dateRange?.startDate, dateRange?.endDate],
    queryFn: async () => {
      if (!accountId) {
        throw new Error("No account selected")
      }
      const response = await authApi.GET(

        "/api/v1/futures/trades",
        {
          params: {
            query: {
              account_id: accountId,
              start_date: dateRange?.startDate ?? undefined,
              end_date: dateRange?.endDate ?? undefined,
              status: "closed",
              limit: 10000,
            },
          },
        }
      )
      if (response.error) {
        throw new Error("Failed to fetch trades data")
      }
      return response.data as unknown as TradeListResponse
    },
    enabled: !!accountId,
  })
}
