import { useState, useEffect } from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { api, setTokens } from "@/api/client"
import { useAuth } from "@/contexts/AuthContext"
import { AuthLayout } from "@/components/layouts/AuthLayout"

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { refreshAuth } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showSignupLink, setShowSignupLink] = useState(true)

  const deactivated = (location.state as { reason?: string } | null)?.reason === "account_deactivated"

  useEffect(() => {
    async function checkRegistrationStatus() {
      try {
        const { data } = await api.GET("/api/v1/auth/registration-status")
        if (data) {
          // Show signup link if: no users yet, or registration is open
          setShowSignupLink(!data.has_users || data.registration_enabled)
        }
      } catch {
        // On error, show signup link by default
      }
    }
    checkRegistrationStatus()
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      const { data, error: apiError } = await api.POST("/api/v1/auth/token", {
        body: {
          username: email,
          password,
          scope: "",
        },
        bodySerializer: (body) => {
          const params = new URLSearchParams()
          params.append("username", body.username)
          params.append("password", body.password)
          params.append("scope", body.scope)
          return params
        },
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      })

      if (apiError) {
        setError("Invalid email or password.")
        return
      }

      if (data) {
        setTokens(data.access_token, data.refresh_token)
        refreshAuth()
        navigate("/futures/positions")
      }
    } catch {
      setError("An unexpected error occurred. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <AuthLayout>
      <div className="w-full max-w-md flex flex-col gap-6">
        <Card className="overflow-hidden p-0">
          <CardContent className="p-0">
            <form className="p-6 md:p-8" onSubmit={handleSubmit}>
              <FieldGroup>
                <div className="flex flex-col items-center gap-2 text-center">
                  <h1 className="text-2xl font-bold">Welcome back</h1>
                  <p className="text-muted-foreground text-sm text-balance">
                    Enter your credentials to access your account
                  </p>
                </div>

                {deactivated && (
                  <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
                    Your account has been deactivated. Please contact an administrator.
                  </div>
                )}

                {error && (
                  <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
                    {error}
                  </div>
                )}

                <Field>
                  <FieldLabel htmlFor="email">Email</FieldLabel>
                  <Input
                    id="email"
                    type="email"
                    placeholder="m@example.com"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isLoading}
                  />
                </Field>

                <Field>
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <Input
                    id="password"
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isLoading}
                  />
                </Field>

                <Field>
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading ? "Signing in..." : "Sign in"}
                  </Button>
                </Field>

                {showSignupLink && (
                  <FieldDescription className="text-center">
                    Don&apos;t have an account?{" "}
                    <Link to="/signup" className="underline underline-offset-4 hover:text-primary">
                      Sign up
                    </Link>
                  </FieldDescription>
                )}
              </FieldGroup>
            </form>
          </CardContent>
        </Card>
      </div>
    </AuthLayout>
  )
}

export default LoginPage
