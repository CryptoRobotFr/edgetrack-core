import { Navigate } from "react-router-dom"
import { useAuth } from "@/contexts/AuthContext"

export function RootRedirect() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return null

  return isAuthenticated
    ? <Navigate to="/futures/positions" replace />
    : <Navigate to="/login" replace />
}
