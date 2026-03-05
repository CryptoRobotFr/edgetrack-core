import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface PnlEvolutionPoint {
  timestamp: number
  pnl: number
  cumulative_fees: number
  cumulative_funding: number
  avg_entry_price: number
  position_size: number
}

export interface PnlEvolutionResponse {
  points: PnlEvolutionPoint[]
  interval: string
  total_points: number
}

export function useTradePnlEvolution(tradeId: string | null) {
  return useQuery({
    queryKey: ["futures", "trade-pnl-evolution", tradeId],
    queryFn: async () => {
      if (!tradeId) {
        throw new Error("No trade ID provided")
      }
      const response = await authApi.GET(

        `/api/v1/futures/trades/{trade_id}/pnl-evolution`,
        {
          params: {
            path: {
              trade_id: tradeId,
            },
          },
        }
      )
      if (response.error) {
        throw new Error("Failed to fetch PnL evolution")
      }
      return response.data as unknown as PnlEvolutionResponse
    },
    enabled: !!tradeId,
  })
}
