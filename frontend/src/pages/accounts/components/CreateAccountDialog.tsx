import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { useCreateAccount } from "@/hooks/useAccountMutations"
import { authApi } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Field, FieldLabel } from "@/components/ui/field"
import ApiKeySelector from "./ApiKeySelector"

interface CreateAccountDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const EXCHANGES = [
  { id: "bitget", name: "Bitget", disabled: false },
  { id: "bitmart", name: "Bitmart", disabled: false },
  { id: "hyperliquid", name: "Hyperliquid", disabled: false },
]

const ACCOUNT_TYPES = [
  { id: "usdt-futures", label: "Futures USDT", accountType: "futures" as const, exchanges: ["bitget", "bitmart"] },
  { id: "usdc-futures", label: "Futures USDC", accountType: "futures" as const, exchanges: ["hyperliquid"] },
  { id: "spot", label: "Spot (coming soon)", accountType: "spot" as const, exchanges: [] as string[] },
  { id: "coin-futures", label: "Futures COIN-M (coming soon)", accountType: "futures" as const, exchanges: [] as string[] },
]

export default function CreateAccountDialog({
  open,
  onOpenChange,
}: CreateAccountDialogProps) {
  const navigate = useNavigate()
  const createAccount = useCreateAccount()
  const [step, setStep] = useState(1)

  // Step 1 fields
  const [accountName, setAccountName] = useState("")
  const [exchange, setExchange] = useState<string | null>(null)
  const [accountTypeId, setAccountTypeId] = useState("usdt-futures")

  // Step 2 fields
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null)

  // Validation state
  const [isValidating, setIsValidating] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Step 3: countdown redirect
  const [newAccountId, setNewAccountId] = useState<string | null>(null)
  const [countdown, setCountdown] = useState(3)

  const isCreating = createAccount.isPending
  const isBusy = isCreating || isValidating

  // Countdown timer for redirect
  useEffect(() => {
    if (step !== 3 || !newAccountId) return

    if (countdown <= 0) {
      onOpenChange(false)
      navigate(`/accounts/${newAccountId}/sync`)
      return
    }

    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [step, countdown, newAccountId, navigate, onOpenChange])

  const resetForm = () => {
    setStep(1)
    setAccountName("")
    setExchange(null)
    setAccountTypeId("usdt-futures")
    setSelectedKeyId(null)
    setIsValidating(false)
    setValidationError(null)
    setNewAccountId(null)
    setCountdown(3)
  }

  const handleOpenChange = (nextOpen: boolean) => {
    if (isBusy || step === 3) {
      toast.info("Action in progress", {
        description: "Please wait for the operation to complete.",
      })
      return
    }
    if (!nextOpen) {
      resetForm()
    }
    onOpenChange(nextOpen)
  }

  const handleNext = () => {
    if (!accountName.trim() || !exchange) return
    setStep(2)
  }

  const handleBack = () => {
    setStep(1)
  }

  const handleCreate = async () => {
    if (!exchange || !selectedKeyId || !accountName.trim()) return

    const selectedType = ACCOUNT_TYPES.find((t) => t.id === accountTypeId)
    if (!selectedType) return

    // Step 1: Validate API key connection
    setIsValidating(true)
    setValidationError(null)

    try {
      const testResponse = await authApi.POST(
        "/api/v1/api-keys/test-connection" as never,
        { body: { api_key_id: selectedKeyId } } as never,
      )

      const testData = (testResponse.data as { valid: boolean; error_message: string | null } | undefined)

      if (!testData?.valid) {
        setValidationError(
          testData?.error_message ||
          "Could not connect to exchange. Please check your API key credentials."
        )
        setIsValidating(false)
        return
      }
    } catch {
      setValidationError("Failed to test connection. Please try again.")
      setIsValidating(false)
      return
    }

    setIsValidating(false)

    // Step 2: Create the account
    try {
      const result = await createAccount.mutateAsync({
        name: accountName.trim(),
        api_key_id: selectedKeyId,
        account_type: selectedType.accountType,
        product_type: selectedType.accountType === "futures" ? accountTypeId as "usdt-futures" | "usdc-futures" | "coin-futures" : undefined,
      })
      const createdId = (result as unknown as { id: string }).id
      setNewAccountId(createdId)
      setCountdown(3)
      setStep(3)
    } catch (err) {
      toast.error("Failed to create account", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="sm:max-w-[425px]"
        onInteractOutside={(e) => {
          if (isBusy || step === 3) e.preventDefault()
        }}
        onEscapeKeyDown={(e) => {
          if (isBusy || step === 3) e.preventDefault()
        }}
      >
        <DialogHeader>
          <DialogTitle>Link a New Exchange Account</DialogTitle>
          <DialogDescription>
            Connect your exchange account by providing a name, selecting an exchange, and linking your API key.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4 relative">
          {step === 1 && (
            <div className="space-y-6">
              <Field>
                <FieldLabel>Account Name</FieldLabel>
                <Input
                  placeholder="e.g., My Main Bitget Account"
                  value={accountName}
                  onChange={(e) => setAccountName(e.target.value)}
                />
              </Field>

              <Field>
                <FieldLabel>Exchange</FieldLabel>
                <Select
                  value={exchange ?? undefined}
                  onValueChange={(v) => {
                    setExchange(v)
                    setSelectedKeyId(null)
                    // Auto-select the first available account type for this exchange
                    const firstType = ACCOUNT_TYPES.find((t) => t.exchanges.includes(v))
                    if (firstType) setAccountTypeId(firstType.id)
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select an exchange" />
                  </SelectTrigger>
                  <SelectContent>
                    {EXCHANGES.map((ex) => (
                      <SelectItem key={ex.id} value={ex.id} disabled={ex.disabled}>
                        <span className="flex items-center gap-2">
                          <img src={`/exchange-icons/${ex.id}.png`} alt="" className="h-4 w-4 rounded-full" />
                          {ex.name}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <Field>
                <FieldLabel>Account Type</FieldLabel>
                <Select
                  value={accountTypeId}
                  onValueChange={setAccountTypeId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select account type" />
                  </SelectTrigger>
                  <SelectContent>
                    {ACCOUNT_TYPES.map((type) => (
                      <SelectItem
                        key={type.id}
                        value={type.id}
                        disabled={!exchange || !type.exchanges.includes(exchange)}
                      >
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <p className="text-sm text-muted-foreground pt-2">
                {exchange === "hyperliquid"
                  ? "You will be asked for your wallet address on the next step. Hyperliquid only requires a public wallet address for read-only access."
                  : <>You will be asked for your API keys on the next step. Please ensure they have{" "}
                    <strong className="text-foreground">Read-Only</strong> permissions for security.</>
                }
              </p>

              <div className="flex justify-end pt-4">
                <Button
                  type="button"
                  onClick={handleNext}
                  disabled={!accountName.trim() || !exchange}
                >
                  Next
                </Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              <ApiKeySelector
                exchangeName={exchange}
                selectedKeyId={selectedKeyId}
                onKeySelected={(id) => {
                  setSelectedKeyId(id)
                  setValidationError(null)
                }}
                onNewKeyCreated={(id) => {
                  setSelectedKeyId(id)
                  setValidationError(null)
                }}
              />

              {validationError && (
                <div className="flex items-start gap-2 rounded-md border border-red-600/30 bg-red-600/5 p-3">
                  <AlertCircle className="h-4 w-4 text-red-600 mt-0.5 shrink-0" />
                  <p className="text-sm text-red-600">{validationError}</p>
                </div>
              )}

              <div className="flex justify-between items-center pt-4">
                <Button type="button" variant="outline" onClick={handleBack} disabled={isBusy}>
                  Back
                </Button>
                <Button
                  type="button"
                  onClick={handleCreate}
                  disabled={isBusy || !selectedKeyId}
                >
                  {isValidating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {isValidating ? "Testing connection..." : "Create Account"}
                </Button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="flex flex-col items-center justify-center py-8">
              <CheckCircle2 className="h-12 w-12 text-emerald-500 mb-4" />
              <p className="text-lg font-semibold text-foreground mb-2">
                Account created!
              </p>
              <p className="text-sm text-muted-foreground">
                Redirecting to initial sync in{" "}
                <span className="font-mono font-semibold text-foreground">{countdown}</span>...
              </p>
            </div>
          )}

          {isCreating && (
            <div className="absolute inset-0 bg-background/90 backdrop-blur-sm flex flex-col items-center justify-center rounded-lg z-20 p-4">
              <Loader2 className="h-10 w-10 animate-spin text-primary mb-4" />
              <p className="text-center text-lg font-semibold text-foreground mb-2">
                Creating Account...
              </p>
              <p className="text-center text-sm text-muted-foreground">
                Please do not close this window.
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
