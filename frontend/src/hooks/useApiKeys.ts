import { useQuery } from "@tanstack/react-query"
import { authApi } from "@/api/client"
import type { components } from "@/api/schema"

type ApiKeyResponse = components["schemas"]["ApiKeyResponse"]

export function useApiKeys() {
  return useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => {
      const { data, error } = await authApi.GET("/api/v1/api-keys")
      if (error) {
        throw new Error("Failed to fetch API keys")
      }
      return data as ApiKeyResponse[]
    },
  })
}
