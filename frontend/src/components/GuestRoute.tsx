import { Navigate } from "react-router-dom"
import { useAuth } from "@/contexts/AuthContext"

interface GuestRouteProps {
  children: React.ReactNode
}

/**
 * Redirects authenticated users to /futures/positions.
 * Use this to wrap public-only routes like login and signup.
 */
export function GuestRoute({ children }: GuestRouteProps) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/futures/positions" replace />
  }

  return <>{children}</>
}
