import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/contexts/AuthContext"

export function HomePage() {
  const { isAuthenticated } = useAuth()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background">
      <h1 className="text-4xl font-bold text-foreground">EdgeTrack</h1>
      <p className="mt-2 text-muted-foreground">Track your crypto trades</p>
      <div className="mt-8 flex gap-4">
        {isAuthenticated ? (
          <Button asChild>
            <Link to="/futures/positions">Go to Positions</Link>
          </Button>
        ) : (
          <>
            <Button asChild>
              <Link to="/login">Login</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/signup">Sign up</Link>
            </Button>
          </>
        )}
      </div>
    </div>
  )
}

export default HomePage
