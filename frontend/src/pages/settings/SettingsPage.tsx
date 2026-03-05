import { useState } from "react"
import { User, Mail, Lock, Globe, Check, Copy, Fingerprint } from "lucide-react"
import { toast } from "sonner"
import { useUser, type SupportedLocale } from "@/contexts/UserContext"
import { formatDate, formatNumber, LOCALE_OPTIONS } from "@/lib/formatters"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Field, FieldLabel, FieldDescription, FieldError } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"

function ProfileSection() {
  const { user, isLoading } = useUser()

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <User className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-lg">Profile</CardTitle>
          </div>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-4 w-48" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <User className="h-5 w-5 text-muted-foreground" />
          <CardTitle className="text-lg">Profile</CardTitle>
        </div>
        <CardDescription>Your account information</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Field>
          <FieldLabel>Email</FieldLabel>
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">{user?.masked_email}</span>
          </div>
          <FieldDescription>
            Email is partially masked for privacy
          </FieldDescription>
        </Field>
        <Separator />
        <Field>
          <FieldLabel>User ID</FieldLabel>
          <div className="flex items-center gap-2">
            <Fingerprint className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-mono text-muted-foreground">
              {user?.id ? `${user.id.slice(0, 8)}...${user.id.slice(-4)}` : "—"}
            </span>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={() => {
                if (user?.id) {
                  navigator.clipboard.writeText(user.id)
                  toast.success("User ID copied to clipboard")
                }
              }}
              title="Copy full user ID"
            >
              <Copy className="h-3 w-3" />
            </Button>
          </div>
          <FieldDescription>
            Your unique identifier
          </FieldDescription>
        </Field>
        <Separator />
        <div className="text-xs text-muted-foreground">
          Account created on {user?.created_at ? formatDate(user.created_at, { full: true }) : "—"}
        </div>
      </CardContent>
    </Card>
  )
}

function SecuritySection() {
  const { updatePassword } = useUser()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match")
      return
    }

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters")
      return
    }

    setIsSubmitting(true)

    const result = await updatePassword(currentPassword, newPassword)

    if (result) {
      setSuccess(true)
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000)
    } else {
      setError("Current password is incorrect")
    }

    setIsSubmitting(false)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Lock className="h-5 w-5 text-muted-foreground" />
          <CardTitle className="text-lg">Security</CardTitle>
        </div>
        <CardDescription>Update your password</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-md bg-emerald-500/15 p-3 text-sm text-emerald-700 dark:text-emerald-400 flex items-center gap-2">
              <Check className="h-4 w-4" />
              Password updated successfully
            </div>
          )}

          <Field>
            <FieldLabel htmlFor="current-password">Current Password</FieldLabel>
            <Input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              disabled={isSubmitting}
              required
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="new-password">New Password</FieldLabel>
            <Input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              disabled={isSubmitting}
              required
              minLength={8}
            />
            <FieldDescription>Minimum 8 characters</FieldDescription>
          </Field>

          <Field>
            <FieldLabel htmlFor="confirm-password">Confirm New Password</FieldLabel>
            <Input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={isSubmitting}
              required
            />
            {confirmPassword && newPassword !== confirmPassword && (
              <FieldError>Passwords do not match</FieldError>
            )}
          </Field>

          <Button
            type="submit"
            disabled={isSubmitting || !currentPassword || !newPassword || !confirmPassword}
          >
            {isSubmitting ? "Updating..." : "Update Password"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function DisplaySection() {
  const { user, updatePreferences, isLoading } = useUser()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  const handleLocaleChange = async (value: string) => {
    setIsSubmitting(true)
    setSuccess(false)

    const result = await updatePreferences(value as SupportedLocale)

    if (result) {
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    }

    setIsSubmitting(false)
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-lg">Display</CardTitle>
          </div>
          <CardDescription>Customize how numbers and dates are displayed</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Globe className="h-5 w-5 text-muted-foreground" />
          <CardTitle className="text-lg">Display</CardTitle>
        </div>
        <CardDescription>Customize how numbers and dates are displayed</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {success && (
          <div className="rounded-md bg-emerald-500/15 p-3 text-sm text-emerald-700 dark:text-emerald-400 flex items-center gap-2">
            <Check className="h-4 w-4" />
            Preferences saved
          </div>
        )}

        <Field>
          <FieldLabel>Number & Date Format</FieldLabel>
          <Select
            value={user?.locale || "en-US"}
            onValueChange={handleLocaleChange}
            disabled={isSubmitting}
          >
            <SelectTrigger className="w-full @sm:w-[280px]">
              <SelectValue placeholder="Select a format" />
            </SelectTrigger>
            <SelectContent>
              {LOCALE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  <div className="flex items-center justify-between gap-4">
                    <span>{option.label}</span>
                    <span className="text-muted-foreground font-mono text-xs">
                      {option.example}
                    </span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldDescription>
            This affects how numbers, currencies, and dates are formatted throughout the app
          </FieldDescription>
        </Field>

        <Separator />

        <div className="space-y-2">
          <p className="text-sm font-medium">Preview</p>
          <div className="rounded-md border bg-muted/50 p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Number:</span>
              <span className="font-mono">{formatNumber(1234567.89, 2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Date:</span>
              <span className="font-mono">{formatDate(Date.now(), { full: true })}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="mt-1 text-muted-foreground">
          Manage your account settings and preferences
        </p>
      </div>

      <div className="grid gap-6 @lg:grid-cols-2">
        <div className="space-y-6">
          <ProfileSection />
          <SecuritySection />
        </div>
        <div>
          <DisplaySection />
        </div>
      </div>
    </div>
  )
}
