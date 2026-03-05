import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"
import type { components } from "@/api/schema"

type CalendarDayResponse = components["schemas"]["CalendarDayResponse"]

export function useCalendarDays(
  accountId: string | null,
  startDate: number | null,
  endDate: number | null
) {
  return useQuery({
    queryKey: ["futures", "calendar-days", accountId, startDate, endDate],
    queryFn: async (): Promise<CalendarDayResponse[]> => {
      if (!accountId || startDate === null || endDate === null) {
        throw new Error("Missing required parameters")
      }
      const { data, error } = await authApi.GET("/api/v1/futures/calendar/days", {
        params: {
          query: {
            account_id: accountId,
            start_date: startDate,
            end_date: endDate,
          },
        },
      })
      if (error) {
        throw new Error("Failed to fetch calendar days")
      }
      return data?.days ?? []
    },
    enabled: !!accountId && startDate !== null && endDate !== null,
  })
}
