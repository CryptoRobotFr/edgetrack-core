import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"

export interface AccountOverviewItem {
  id: string
  name: string
  account_type: string
  product_type: string | null
  exchange_name: string
  exchange_avatar_url: string | null
  api_key_id: string
  api_key_name: string
  is_connected: boolean
  equity: number | null
  total_trades: number
  last_sync_date: number | null
  sync_in_progress: boolean
  is_demo: boolean
  created_at: number
  updated_at: number
}

interface AccountsOverviewResponse {
  accounts: AccountOverviewItem[]
}

export function useAccountsOverview() {
  return useQuery({
    queryKey: ["accounts", "overview"],
    queryFn: async () => {
      const response = await authApi.GET("/api/v1/accounts/overview" as never)
      if (response.error) {
        throw new Error("Failed to fetch accounts overview")
      }
      return (response.data as unknown as AccountsOverviewResponse).accounts
    },
  })
}
