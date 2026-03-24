import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { authApi, getAccessToken } from "@/api/client"
import type { components } from "@/api/schema"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"

type UserListResponse = components["schemas"]["UserListResponse"]
type InvitationListResponse = components["schemas"]["InvitationListResponse"]
type InvitationResponse = components["schemas"]["InvitationResponse"]
type AdminUserResponse = components["schemas"]["AdminUserResponse"]

export function useAdminUsers() {
  return useQuery({
    queryKey: ["admin", "users"],
    queryFn: async () => {
      const { data, error } = await authApi.GET("/api/v1/admin/users")
      if (error) throw new Error("Failed to fetch users")
      return (data as UserListResponse).users
    },
  })
}

export function useAdminInvitations() {
  return useQuery({
    queryKey: ["admin", "invitations"],
    queryFn: async () => {
      const { data, error } = await authApi.GET("/api/v1/admin/invitations")
      if (error) throw new Error("Failed to fetch invitations")
      return (data as InvitationListResponse).invitations
    },
  })
}

export function useDeactivateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (userId: string) => {
      const { data, error } = await authApi.PATCH("/api/v1/admin/users/{user_id}/deactivate", {
        params: { path: { user_id: userId } },
      })
      if (error) throw new Error("Failed to deactivate user")
      return data as AdminUserResponse
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  })
}

export function useActivateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (userId: string) => {
      const { data, error } = await authApi.PATCH("/api/v1/admin/users/{user_id}/activate", {
        params: { path: { user_id: userId } },
      })
      if (error) throw new Error("Failed to activate user")
      return data as AdminUserResponse
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  })
}

export function useDeleteUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (userId: string) => {
      const { error } = await authApi.DELETE("/api/v1/admin/users/{user_id}", {
        params: { path: { user_id: userId } },
      })
      if (error) throw new Error("Failed to delete user")
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  })
}

export function useCreateInvitation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (expiresInDays: number = 7) => {
      const { data, error } = await authApi.POST("/api/v1/admin/invitations", {
        body: { expires_in_days: expiresInDays },
      })
      if (error) throw new Error("Failed to create invitation")
      return data as InvitationResponse
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "invitations"] }),
  })
}

export function useDeleteInvitation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (invitationId: string) => {
      const { error } = await authApi.DELETE("/api/v1/admin/invitations/{invitation_id}", {
        params: { path: { invitation_id: invitationId } },
      })
      if (error) throw new Error("Failed to delete invitation")
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "invitations"] }),
  })
}

export function useSearchUserByEmail() {
  return useMutation({
    mutationFn: async (email: string) => {
      const token = getAccessToken()
      const res = await fetch(
        `${API_BASE_URL}/api/v1/admin/users/search?email=${encodeURIComponent(email)}`,
        {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        }
      )
      if (res.status === 404) return null
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Search failed: ${res.status}`)
      }
      return (await res.json()) as AdminUserResponse
    },
  })
}
