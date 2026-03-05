import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface DateRange {
  startDate: number | null
  endDate: number | null
}

export function useCalendarGlobalMetrics(
  accountId: string | null,
  dateRange?: DateRange
) {
  return useQuery({
    queryKey: [
      "futures",
      "calendar-metrics",
      accountId,
      dateRange?.startDate,
      dateRange?.endDate,
    ],
    queryFn: async () => {
      if (!accountId) {
        throw new Error("No account selected")
      }
      const { data, error } = await authApi.GET(
        "/api/v1/futures/calendar/global-metrics",
        {
          params: {
            query: {
              account_id: accountId,
              start_date: dateRange?.startDate ?? undefined,
              end_date: dateRange?.endDate ?? undefined,
            },
          },
        }
      )
      if (error) {
        throw new Error("Failed to fetch calendar global metrics")
      }
      return data
    },
    enabled: !!accountId,
  })
}
