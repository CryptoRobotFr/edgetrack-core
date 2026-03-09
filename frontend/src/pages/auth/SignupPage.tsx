import { useState, useEffect } from "react"
import { useNavigate, useSearchParams, Link } from "react-router-dom"
import { ShieldX } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { api, setTokens } from "@/api/client"
import { useAuth } from "@/contexts/AuthContext"
import { AuthLayout } from "@/components/layouts/AuthLayout"

export function SignupPage() {
  const navigate = useNavigate()
  const { refreshAuth } = useAuth()
  const [searchParams] = useSearchParams()
  const inviteToken = searchParams.get("invite")
  const referralCode = searchParams.get("ref")

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Registration status check
  const [registrationClosed, setRegistrationClosed] = useState(false)
  const [isCheckingStatus, setIsCheckingStatus] = useState(true)

  useEffect(() => {
    async function checkStatus() {
      try {
        const { data } = await api.GET("/api/v1/auth/registration-status")
        if (data) {
          // Registration is open if: no users yet, or registration_enabled, or invite token present
          const isOpen = !data.has_users || data.registration_enabled || !!inviteToken
          setRegistrationClosed(!isOpen)
        }
      } catch {
        // If check fails, allow registration attempt (backend will gate it)
      } finally {
        setIsCheckingStatus(false)
      }
    }
    checkStatus()
  }, [inviteToken])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      const { data, error: apiError } = await api.POST("/api/v1/auth/register", {
        body: {
          email,
          password,
          invitation_token: inviteToken || undefined,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          referral_code: referralCode || undefined,
        } as any,
      })

      if (apiError) {
        if ("detail" in apiError && typeof apiError.detail === "string") {
          setError(apiError.detail)
        } else if ("detail" in apiError && Array.isArray(apiError.detail)) {
          const messages = apiError.detail.map((err: { msg: string }) => err.msg).join(", ")
          setError(messages)
        } else {
          setError("Registration failed. Please try again.")
        }
        return
      }

      if (data) {
        // Handle email verification required response
        const resp = data as { requires_verification?: boolean; user_id?: string; access_token?: string; refresh_token?: string }
        if (resp.requires_verification && resp.user_id) {
          navigate(`/verify-email?userId=${resp.user_id}`)
          return
        }
        // Standard token response (self-hosted, no verification)
        if (resp.access_token && resp.refresh_token) {
          setTokens(resp.access_token, resp.refresh_token)
          refreshAuth()
          navigate("/futures/positions")
        }
      }
    } catch {
      setError("An unexpected error occurred. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  if (isCheckingStatus) {
    return (
      <AuthLayout>
        <div className="w-full max-w-md flex flex-col gap-6">
          <Card className="overflow-hidden p-0">
            <CardContent className="p-6 md:p-8">
              <div className="flex flex-col items-center gap-2 text-center">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                <p className="text-muted-foreground text-sm">Checking registration status...</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </AuthLayout>
    )
  }

  if (registrationClosed) {
    return (
      <AuthLayout>
        <div className="w-full max-w-md flex flex-col gap-6">
          <Card className="overflow-hidden p-0">
            <CardContent className="p-6 md:p-8">
              <div className="flex flex-col items-center gap-4 text-center">
                <ShieldX className="h-12 w-12 text-muted-foreground" />
                <div>
                  <h1 className="text-2xl font-bold">Registration Closed</h1>
                  <p className="mt-2 text-muted-foreground text-sm text-balance">
                    Registration is currently disabled. You need an invitation link from an administrator to create an account.
                  </p>
                </div>
                <FieldDescription className="text-center">
                  Already have an account?{" "}
                  <Link to="/login" className="underline underline-offset-4 hover:text-primary">
                    Sign in
                  </Link>
                </FieldDescription>
              </div>
            </CardContent>
          </Card>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <div className="w-full max-w-md flex flex-col gap-6">
        <Card className="overflow-hidden p-0">
          <CardContent className="p-0">
            <form className="p-6 md:p-8" onSubmit={handleSubmit}>
              <FieldGroup>
                <div className="flex flex-col items-center gap-2 text-center">
                  <h1 className="text-2xl font-bold">Create your account</h1>
                  <p className="text-muted-foreground text-sm text-balance">
                    {inviteToken
                      ? "You have been invited to create an account"
                      : "Enter your email below to create your account"}
                  </p>
                </div>

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
                  <FieldDescription>
                    We&apos;ll use this to contact you. We will not share your
                    email with anyone else.
                  </FieldDescription>
                </Field>

                <Field>
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <Input
                    id="password"
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isLoading}
                  />
                  <FieldDescription>
                    Must be at least 8 characters long.
                  </FieldDescription>
                </Field>

                <Field>
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading ? "Creating account..." : "Create Account"}
                  </Button>
                </Field>

                <FieldDescription className="text-center">
                  Already have an account?{" "}
                  <Link to="/login" className="underline underline-offset-4 hover:text-primary">
                    Sign in
                  </Link>
                </FieldDescription>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>

        <FieldDescription className="px-6 text-center">
          By clicking continue, you agree to our{" "}
          <a href="#" className="underline underline-offset-4 hover:text-primary">
            Terms of Service
          </a>{" "}
          and{" "}
          <a href="#" className="underline underline-offset-4 hover:text-primary">
            Privacy Policy
          </a>
          .
        </FieldDescription>
      </div>
    </AuthLayout>
  )
}

export default SignupPage
