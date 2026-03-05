import { useMutation, useQueryClient } from "@tanstack/react-query"
import { authApi } from "@/api/client"
import type { TradeDetail } from "./useTradeDetail"

interface UpdateTradeParams {
  tradeId: string
  rating?: number
  notes?: string
}

/**
 * Mutation hook for updating trade rating and/or notes.
 * Automatically invalidates related queries on success.
 */
export function useUpdateTrade() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ tradeId, rating, notes }: UpdateTradeParams) => {
      const response = await authApi.PATCH(

        `/api/v1/futures/trades/{trade_id}`,
        {
          params: {
            path: {
              trade_id: tradeId,
            },
          },
          body: {
            rating,
            notes,
          },
        }
      )
      if (response.error) {
        throw new Error("Failed to update trade")
      }
      return response.data as unknown as TradeDetail
    },
    onSuccess: (data, variables) => {
      // Update the trade-detail cache directly
      queryClient.setQueryData(["futures", "trade-detail", variables.tradeId], data)

      // Invalidate the trades list to reflect changes
      queryClient.invalidateQueries({ queryKey: ["futures", "trades"] })
    },
  })
}
