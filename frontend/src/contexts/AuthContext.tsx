import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { isAuthenticated as checkAuth, clearTokens, setOnUnauthorized } from "@/api/client"

interface AuthContextType {
  isAuthenticated: boolean
  isLoading: boolean
  logout: () => void
  refreshAuth: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  const refreshAuth = useCallback(() => {
    setIsAuthenticated(checkAuth())
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setIsAuthenticated(false)
  }, [])

  // Handle 401/403 responses globally - logout and redirect to login
  const handleUnauthorized = useCallback((reason?: string) => {
    logout()
    navigate("/login", { replace: true, state: reason ? { reason } : undefined })
  }, [logout, navigate])

  useEffect(() => {
    // Register the 401 handler
    setOnUnauthorized(handleUnauthorized)
  }, [handleUnauthorized])

  useEffect(() => {
    // Check auth status on mount
    refreshAuth()
    setIsLoading(false)
  }, [refreshAuth])

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, logout, refreshAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
