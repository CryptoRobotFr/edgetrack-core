import { useState } from "react"
import { AlertTriangle, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { useCreateApiKey } from "@/hooks/useAccountMutations"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
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
import { Field, FieldLabel, FieldDescription } from "@/components/ui/field"

interface CreateApiKeyDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const EXCHANGES = [
  { id: "bitget", name: "Bitget" },
  { id: "bitmart", name: "Bitmart" },
  { id: "hyperliquid", name: "Hyperliquid" },
]

export default function CreateApiKeyDialog({
  open,
  onOpenChange,
}: CreateApiKeyDialogProps) {
  const createApiKey = useCreateApiKey()

  const [name, setName] = useState("")
  const [exchange, setExchange] = useState<string | null>(null)
  const [publicKey, setPublicKey] = useState("")
  const [secretKey, setSecretKey] = useState("")
  const [passphrase, setPassphrase] = useState("")
  const [memo, setMemo] = useState("")

  const isCreating = createApiKey.isPending
  const isHyperliquid = exchange === "hyperliquid"
  const showPassphrase = exchange === "bitget"
  const showMemo = exchange === "bitmart"

  const resetForm = () => {
    setName("")
    setExchange(null)
    setPublicKey("")
    setSecretKey("")
    setPassphrase("")
    setMemo("")
  }

  const handleOpenChange = (nextOpen: boolean) => {
    if (isCreating) return
    if (!nextOpen) resetForm()
    onOpenChange(nextOpen)
  }

  const isFormValid =
    name.trim() &&
    exchange &&
    publicKey.trim() &&
    (isHyperliquid || secretKey.trim()) &&
    (!showPassphrase || passphrase.trim()) &&
    (!showMemo || memo.trim())

  const handleCreate = async () => {
    if (!exchange || !isFormValid) return

    try {
      await createApiKey.mutateAsync({
        name: name.trim(),
        exchange_name: exchange as "bitget" | "bitmart" | "hyperliquid",
        public_key: publicKey.trim(),
        secret_key: isHyperliquid ? "not_required" : secretKey.trim(),
        passphrase: showPassphrase ? passphrase.trim() : undefined,
        memo: showMemo ? memo.trim() : undefined,
      })
      toast.success("API key created", {
        description: `"${name.trim()}" has been created.`,
      })
      resetForm()
      onOpenChange(false)
    } catch (err) {
      toast.error("Failed to create API key", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="sm:max-w-[425px]"
        onInteractOutside={(e) => {
          if (isCreating) e.preventDefault()
        }}
        onEscapeKeyDown={(e) => {
          if (isCreating) e.preventDefault()
        }}
      >
        <DialogHeader>
          <DialogTitle>Add a New API Key</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <Field>
            <FieldLabel>Name</FieldLabel>
            <Input
              placeholder="e.g., Main Bitget Key"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
            />
          </Field>

          <Field>
            <FieldLabel>Exchange</FieldLabel>
            <Select
              value={exchange ?? undefined}
              onValueChange={(v) => {
                setExchange(v)
                setSecretKey("")
                setPassphrase("")
                setMemo("")
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select an exchange" />
              </SelectTrigger>
              <SelectContent>
                {EXCHANGES.map((ex) => (
                  <SelectItem key={ex.id} value={ex.id}>
                    <span className="flex items-center gap-2">
                      <img src={`/exchange-icons/${ex.id}.png`} alt="" className="h-4 w-4 rounded-full" />
                      {ex.name}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          {exchange && !isHyperliquid && (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-600 dark:text-amber-400">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium">Required API key permissions</p>
                  <ul className="mt-1 list-disc list-inside text-xs text-amber-600/80 dark:text-amber-400/80 space-y-0.5">
                    <li>Permissions must be <strong className="text-amber-600 dark:text-amber-400">Read-Only</strong></li>
                    <li>Enable read access for <strong className="text-amber-600 dark:text-amber-400">Futures</strong></li>
                    <li>Enable read access for <strong className="text-amber-600 dark:text-amber-400">Taxation</strong> (required for transaction history)</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {exchange && (
            <>
              <Field>
                <FieldLabel>
                  {isHyperliquid ? "Wallet Address" : "API Key"}
                </FieldLabel>
                <Input
                  placeholder={isHyperliquid ? "0x..." : "Enter your API key"}
                  value={publicKey}
                  onChange={(e) => setPublicKey(e.target.value)}
                />
                {isHyperliquid && (
                  <FieldDescription>
                    Your Ethereum wallet address (0x + 40 hex characters).
                  </FieldDescription>
                )}
              </Field>

              {!isHyperliquid && (
                <Field>
                  <FieldLabel>API Secret</FieldLabel>
                  <Input
                    type="password"
                    placeholder="Enter your API secret"
                    value={secretKey}
                    onChange={(e) => setSecretKey(e.target.value)}
                  />
                </Field>
              )}

              {showPassphrase && (
                <Field>
                  <FieldLabel>Passphrase</FieldLabel>
                  <Input
                    type="password"
                    placeholder="Required for Bitget"
                    value={passphrase}
                    onChange={(e) => setPassphrase(e.target.value)}
                  />
                  <FieldDescription>
                    Required for Bitget exchange.
                  </FieldDescription>
                </Field>
              )}

              {showMemo && (
                <Field>
                  <FieldLabel>Memo</FieldLabel>
                  <Input
                    type="password"
                    placeholder="Required for Bitmart"
                    value={memo}
                    onChange={(e) => setMemo(e.target.value)}
                  />
                  <FieldDescription>
                    Required for Bitmart exchange.
                  </FieldDescription>
                </Field>
              )}
            </>
          )}

          <div className="flex justify-end pt-4">
            <Button
              onClick={handleCreate}
              disabled={isCreating || !isFormValid}
            >
              {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Key
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
