import { useMutation, useQueryClient } from "@tanstack/react-query"
import { authApi } from "@/api/client"
import { useAccount } from "@/contexts/AccountContext"
import type { components } from "@/api/schema"

type AccountCreateRequest = components["schemas"]["AccountCreateRequest"]
type ApiKeyCreateRequest = components["schemas"]["ApiKeyCreateRequest"]

interface AccountDeleteResponse {
  deleted: boolean
  orphaned_api_key_id: string | null
  orphaned_api_key_name: string | null
}

export function useCreateAccount() {
  const queryClient = useQueryClient()
  const { refreshAccounts } = useAccount()

  return useMutation({
    mutationFn: async (data: AccountCreateRequest) => {
      const { data: result, error } = await authApi.POST("/api/v1/accounts", {
        body: data,
      })
      if (error) {
        const err = error as { detail?: string }
        throw new Error(err.detail || "Failed to create account")
      }
      return result
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
      refreshAccounts()
    },
  })
}

export function useUpdateAccount() {
  const queryClient = useQueryClient()
  const { refreshAccounts } = useAccount()

  return useMutation({
    mutationFn: async ({
      accountId,
      data,
    }: {
      accountId: string
      data: { name?: string; api_key_id?: string }
    }) => {
      const { data: result, error } = await authApi.PATCH(
        "/api/v1/accounts/{account_id}",
        {
          params: { path: { account_id: accountId } },
          body: data,
        }
      )
      if (error) {
        const err = error as { detail?: string }
        throw new Error(err.detail || "Failed to update account")
      }
      return result
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
      refreshAccounts()
    },
  })
}

export function useDeleteAccount() {
  return useMutation({
    mutationFn: async (accountId: string) => {
      const response = await authApi.DELETE(
        "/api/v1/accounts/{account_id}",
        {
          params: { path: { account_id: accountId } },
        }
      )
      if (response.error) {
        const err = response.error as { detail?: string }
        throw new Error(err.detail || "Failed to delete account")
      }
      // The response now returns JSON with orphaned key info
      return response.data as unknown as AccountDeleteResponse
    },
    // No onSuccess here — the DeleteAccountDialog handles invalidation
    // after the full flow (including orphaned key prompt) is complete.
  })
}

export function useCreateApiKey() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: ApiKeyCreateRequest) => {
      const { data: result, error } = await authApi.POST("/api/v1/api-keys", {
        body: data,
      })
      if (error) {
        const err = error as { detail?: string }
        throw new Error(err.detail || "Failed to create API key")
      }
      return result
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    },
  })
}

export function useDeleteApiKey() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (apiKeyId: string) => {
      const response = await authApi.DELETE(
        "/api/v1/api-keys/{api_key_id}",
        {
          params: { path: { api_key_id: apiKeyId } },
        }
      )
      if (response.error) {
        const err = response.error as { detail?: string }
        throw new Error(err.detail || "Failed to delete API key")
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    },
  })
}
