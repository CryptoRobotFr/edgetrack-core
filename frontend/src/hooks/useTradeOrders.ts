import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface TradeOrderItem {
  id: string
  exchange_order_id: string
  side: string
  action: string
  open_or_close: string
  order_type: string
  size: number
  usd_size: number
  price: number
  fees: number
  creation_date: number
  execution_date: number
}

export interface TradeOrdersResponse {
  orders: TradeOrderItem[]
  total: number
}

export function useTradeOrders(tradeId: string | null) {
  return useQuery({
    queryKey: ["futures", "trade-orders", tradeId],
    queryFn: async () => {
      if (!tradeId) {
        throw new Error("No trade ID provided")
      }
      const response = await authApi.GET(

        `/api/v1/futures/trades/{trade_id}/orders`,
        {
          params: {
            path: {
              trade_id: tradeId,
            },
          },
        }
      )
      if (response.error) {
        throw new Error("Failed to fetch trade orders")
      }
      return response.data as unknown as TradeOrdersResponse
    },
    enabled: !!tradeId,
  })
}
