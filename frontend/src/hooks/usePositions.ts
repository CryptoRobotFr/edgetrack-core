import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface PositionItem {
  pair: string
  base: string
  quote: string
  side: string
  size: number
  usd_size: number
  entry_price: number
  mark_price: number
  unrealized_pnl: number
  realized_pnl: number
  leverage: number
  margin_mode: string
  liquidation_price: number | null
  margin: number | null
  created_at: number | null
  pnl_pct: number
  price_decimals: number
  size_decimals: number
  order_count: number
  matched_trade_id: string | null
  base_image_url: string | null
}

export interface AccountBalanceSummary {
  equity: number
  available_balance: number
  total_margin: number
  unrealized_pnl: number
  open_positions_count: number
}

export interface PositionsResponse {
  balance: AccountBalanceSummary
  positions: PositionItem[]
}

export function usePositions(accountId: string | null) {
  return useQuery({
    queryKey: ["futures", "positions", accountId],
    queryFn: async () => {
      if (!accountId) {
        throw new Error("No account selected")
      }
      const response = await authApi.GET(

        "/api/v1/futures/positions",
        {
          params: {
            query: {
              account_id: accountId,
            },
          },
        }
      )
      if (response.error) {
        throw new Error("Failed to fetch positions data")
      }
      return response.data as unknown as PositionsResponse
    },
    enabled: !!accountId,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
}
