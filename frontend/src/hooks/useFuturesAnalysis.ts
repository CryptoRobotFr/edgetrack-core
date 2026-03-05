import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface DateRange {
  startDate: number | null
  endDate: number | null
}

export function useFuturesAnalysis(
  accountId: string | null,
  dateRange?: DateRange
) {
  return useQuery({
    queryKey: ["futures", "analysis", accountId, dateRange?.startDate, dateRange?.endDate],
    queryFn: async () => {
      if (!accountId) {
        throw new Error("No account selected")
      }
      const { data, error } = await authApi.GET("/api/v1/futures/analysis", {
        params: {
          query: {
            account_id: accountId,
            start_date: dateRange?.startDate ?? undefined,
            end_date: dateRange?.endDate ?? undefined,
          },
        },
      })
      if (error) {
        throw new Error("Failed to fetch analysis data")
      }
      return data
    },
    enabled: !!accountId,
  })
}
