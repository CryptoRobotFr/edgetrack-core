import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react"
import { authApi } from "@/api/client"
import { useAuth } from "@/contexts/AuthContext"
import { setLocale, type SupportedLocale } from "@/lib/formatters"

export type { SupportedLocale }

export interface User {
  id: string
  masked_email: string
  is_active: boolean
  is_superuser: boolean
  locale: SupportedLocale
  plan?: string | null
  created_at: number
  updated_at: number
}

interface UserContextType {
  user: User | null
  isLoading: boolean
  error: string | null
  updatePassword: (currentPassword: string, newPassword: string) => Promise<boolean>
  updatePreferences: (locale: SupportedLocale) => Promise<boolean>
  refreshUser: () => Promise<void>
}

const UserContext = createContext<UserContextType | null>(null)

export function UserProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchUser = useCallback(async () => {
    if (!isAuthenticated) {
      setUser(null)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const { data, error: apiError } = await authApi.GET("/api/v1/auth/me")

      if (apiError) {
        setError("Failed to fetch user information")
        setUser(null)
        return
      }

      if (data) {
        setUser({
          id: data.id,
          masked_email: data.masked_email,
          is_active: data.is_active,
          is_superuser: data.is_superuser,
          locale: (data.locale as SupportedLocale) || "en-US",
          plan: (data as { plan?: string | null }).plan ?? null,
          created_at: data.created_at,
          updated_at: data.updated_at,
        })
      }
    } catch {
      setError("An unexpected error occurred")
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [isAuthenticated])

  const refreshUser = useCallback(async () => {
    await fetchUser()
  }, [fetchUser])

  const updatePassword = useCallback(
    async (currentPassword: string, newPassword: string): Promise<boolean> => {
      try {
        const { data, error: apiError } = await authApi.PATCH("/api/v1/auth/me/password", {
          body: {
            current_password: currentPassword,
            new_password: newPassword,
          },
        })

        if (apiError) {
          return false
        }

        if (data) {
          setUser({
            id: data.id,
            masked_email: data.masked_email,
            is_active: data.is_active,
            is_superuser: data.is_superuser,
            locale: (data.locale as SupportedLocale) || "en-US",
            plan: (data as { plan?: string | null }).plan ?? null,
            created_at: data.created_at,
            updated_at: data.updated_at,
          })
          return true
        }

        return false
      } catch {
        return false
      }
    },
    []
  )

  const updatePreferences = useCallback(
    async (locale: SupportedLocale): Promise<boolean> => {
      try {
        const { data, error: apiError } = await authApi.PATCH("/api/v1/auth/me/preferences", {
          body: { locale },
        })

        if (apiError) {
          return false
        }

        if (data) {
          setUser({
            id: data.id,
            masked_email: data.masked_email,
            is_active: data.is_active,
            is_superuser: data.is_superuser,
            locale: (data.locale as SupportedLocale) || "en-US",
            plan: (data as { plan?: string | null }).plan ?? null,
            created_at: data.created_at,
            updated_at: data.updated_at,
          })
          return true
        }

        return false
      } catch {
        return false
      }
    },
    []
  )

  // Sync locale with formatters module when user changes
  useEffect(() => {
    if (user?.locale) {
      setLocale(user.locale)
    }
  }, [user?.locale])

  useEffect(() => {
    fetchUser()
  }, [fetchUser])

  return (
    <UserContext.Provider
      value={{
        user,
        isLoading,
        error,
        updatePassword,
        updatePreferences,
        refreshUser,
      }}
    >
      {children}
    </UserContext.Provider>
  )
}

export function useUser() {
  const context = useContext(UserContext)
  if (!context) {
    throw new Error("useUser must be used within a UserProvider")
  }
  return context
}
