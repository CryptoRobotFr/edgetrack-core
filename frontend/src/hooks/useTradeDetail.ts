import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface TradeDetail {
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
  order_count: number
  base_image_url: string | null
  size_decimals: number
  price_decimals: number
}

export function useTradeDetail(tradeId: string | null) {
  return useQuery({
    queryKey: ["futures", "trade-detail", tradeId],
    queryFn: async () => {
      if (!tradeId) {
        throw new Error("No trade ID provided")
      }
      const response = await authApi.GET(

        `/api/v1/futures/trades/{trade_id}`,
        {
          params: {
            path: {
              trade_id: tradeId,
            },
          },
        }
      )
      if (response.error) {
        throw new Error("Failed to fetch trade detail")
      }
      return response.data as unknown as TradeDetail
    },
    enabled: !!tradeId,
  })
}
