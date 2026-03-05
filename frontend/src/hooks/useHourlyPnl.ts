import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface HourlyPnlPoint {
  timestamp: number
  pnl: number
  fees: number
  funding: number
}

export interface PairHourlyPnl {
  pair: string
  data_points: HourlyPnlPoint[]
}

export interface HourlyPnlResponse {
  hourly_pnl: HourlyPnlPoint[]
  pair_pnl: PairHourlyPnl[]
  period_start: number
  period_end: number
}

export function useHourlyPnl(accountId: string | null) {
  return useQuery({
    queryKey: ["futures", "hourly-pnl", accountId],
    queryFn: async () => {
      if (!accountId) {
        throw new Error("No account selected")
      }
      const response = await authApi.GET(
        "/api/v1/futures/positions/hourly-pnl" as never,
        {
          params: {
            query: {
              account_id: accountId,
            },
          },
        } as never
      )
      if ((response as { error?: unknown }).error) {
        throw new Error("Failed to fetch hourly PnL data")
      }
      return (response as { data: unknown }).data as HourlyPnlResponse
    },
    enabled: !!accountId,
    staleTime: 5 * 60 * 1000, // 5 min stale (expensive query)
    refetchInterval: 10 * 60 * 1000, // Refresh every 10 min
  })
}
