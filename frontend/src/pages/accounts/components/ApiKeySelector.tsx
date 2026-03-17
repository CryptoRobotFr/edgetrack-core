import { forwardRef, useEffect, useImperativeHandle, useState } from "react"
import { AlertTriangle, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { useApiKeys } from "@/hooks/useApiKeys"
import { useCreateApiKey } from "@/hooks/useAccountMutations"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Field, FieldLabel, FieldDescription } from "@/components/ui/field"

export interface ApiKeySelectorHandle {
  /** Create the key from current form values. Returns the new key ID or null on failure. */
  createKey: () => Promise<string | null>
  /** Whether the inline create form is currently shown. */
  isCreating: boolean
  /** Whether the create form has all required fields filled. */
  isFormValid: boolean
}

interface ApiKeySelectorProps {
  exchangeName: string | null
  selectedKeyId: string | null
  onKeySelected: (keyId: string) => void
  onNewKeyCreated: (keyId: string) => void
  /** Pre-fill the key name field when creating a new key. */
  defaultKeyName?: string
  /** Called when the inline create form is shown/hidden. */
  onCreateFormToggle?: (isShown: boolean) => void
  /** When true, form renders flat (no border) and hides Cancel/Create buttons. Parent handles creation via ref. */
  inline?: boolean
}

const CREATE_NEW_KEY = "__create_new__"

const ApiKeySelector = forwardRef<ApiKeySelectorHandle, ApiKeySelectorProps>(
  function ApiKeySelector(
    {
      exchangeName,
      selectedKeyId,
      onKeySelected,
      onNewKeyCreated,
      defaultKeyName,
      onCreateFormToggle,
      inline = false,
    },
    ref,
  ) {
    const { data: apiKeys = [], isLoading: isLoadingKeys } = useApiKeys()
    const createApiKey = useCreateApiKey()
    const [showCreateForm, setShowCreateForm] = useState(false)

    // Inline creation form state
    const [keyName, setKeyName] = useState(defaultKeyName ?? "")
    const [publicKey, setPublicKey] = useState("")
    const [secretKey, setSecretKey] = useState("")
    const [passphrase, setPassphrase] = useState("")
    const [memo, setMemo] = useState("")

    // Update keyName when defaultKeyName changes (e.g. exchange changed)
    useEffect(() => {
      if (defaultKeyName !== undefined) {
        setKeyName(defaultKeyName)
      }
    }, [defaultKeyName])

    // Filter keys by exchange
    const filteredKeys = exchangeName
      ? apiKeys.filter((k) => k.exchange_name === exchangeName)
      : []

    const isHyperliquid = exchangeName === "hyperliquid"
    const showPassphrase = exchangeName === "bitget"
    const showMemo = exchangeName === "bitmart"

    const isFormValid =
      !!exchangeName &&
      !!keyName &&
      !!publicKey &&
      (isHyperliquid || !!secretKey) &&
      (!showPassphrase || !!passphrase) &&
      (!showMemo || !!memo)

    const handleSelectChange = (value: string) => {
      if (value === CREATE_NEW_KEY) {
        setShowCreateForm(true)
        onCreateFormToggle?.(true)
      } else {
        setShowCreateForm(false)
        onCreateFormToggle?.(false)
        onKeySelected(value)
      }
    }

    const resetForm = () => {
      setKeyName(defaultKeyName ?? "")
      setPublicKey("")
      setSecretKey("")
      setPassphrase("")
      setMemo("")
    }

    const doCreateKey = async (): Promise<string | null> => {
      if (!exchangeName || !isFormValid) return null

      try {
        const result = await createApiKey.mutateAsync({
          name: keyName,
          exchange_name: exchangeName as "bitget" | "bitmart" | "hyperliquid",
          public_key: publicKey,
          secret_key: isHyperliquid ? "not_required" : secretKey,
          passphrase: showPassphrase ? passphrase : undefined,
          memo: showMemo ? memo : undefined,
        })
        if (result) {
          const newKeyId = (result as { id: string }).id
          onNewKeyCreated(newKeyId)
          resetForm()
          setShowCreateForm(false)
          onCreateFormToggle?.(false)
          return newKeyId
        }
        return null
      } catch (err) {
        toast.error("Failed to create API key", {
          description: err instanceof Error ? err.message : "Unknown error",
        })
        return null
      }
    }

    // Expose imperative handle for parent to trigger key creation
    useImperativeHandle(ref, () => ({
      createKey: doCreateKey,
      isCreating: showCreateForm,
      isFormValid,
    }))

    const maskKey = (key: string): string => {
      if (key.length <= 8) return key
      return `${key.substring(0, 4)}...${key.substring(key.length - 4)}`
    }

    if (!exchangeName) {
      return (
        <div className="text-sm text-muted-foreground">
          Select an exchange first to choose an API key.
        </div>
      )
    }

    return (
      <div className="space-y-4">
        <Field>
          <FieldLabel>{isHyperliquid ? "Wallet" : "API Key"}</FieldLabel>
          <Select
            value={showCreateForm ? CREATE_NEW_KEY : (selectedKeyId ?? undefined)}
            onValueChange={handleSelectChange}
            disabled={isLoadingKeys}
          >
            <SelectTrigger>
              <SelectValue placeholder={isHyperliquid ? "Select a wallet" : "Select an API key"} />
            </SelectTrigger>
            <SelectContent>
              {filteredKeys.map((key) => (
                <SelectItem key={key.id} value={key.id}>
                  {key.name} ({maskKey(key.public_key)})
                </SelectItem>
              ))}
              {filteredKeys.length > 0 && <SelectSeparator />}
              <SelectItem value={CREATE_NEW_KEY}>
                {isHyperliquid ? "+ Add new wallet" : "+ Create new API key"}
              </SelectItem>
            </SelectContent>
          </Select>
          {!showCreateForm && (
            <FieldDescription>
              {isHyperliquid
                ? `Select an existing wallet for ${exchangeName} or add a new one.`
                : `Select an existing key for ${exchangeName} or create a new one.`
              }
            </FieldDescription>
          )}
        </Field>

        {showCreateForm && (
          <div className={inline ? "space-y-4" : "space-y-4 rounded-md border p-4"}>
            {!isHyperliquid && (
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
            {!(inline && defaultKeyName !== undefined) && (
              <Field>
                <FieldLabel>{isHyperliquid ? "Wallet Name" : "Key Name"}</FieldLabel>
                <Input
                  placeholder={isHyperliquid ? "e.g., My Hyperliquid Wallet" : "e.g., Main Bitget Key"}
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                />
              </Field>
            )}
            <Field>
              <FieldLabel>{isHyperliquid ? "Wallet Address" : "API Key / Public Key"}</FieldLabel>
              <Input
                placeholder={isHyperliquid ? "0x..." : "Enter your API key"}
                value={publicKey}
                onChange={(e) => setPublicKey(e.target.value)}
              />
              {isHyperliquid && (
                <FieldDescription>Your Ethereum wallet address (0x + 40 hex characters).</FieldDescription>
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
                <FieldDescription>Required for Bitget exchange.</FieldDescription>
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
                <FieldDescription>Required for Bitmart exchange.</FieldDescription>
              </Field>
            )}
            {!inline && (
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setShowCreateForm(false)
                    onCreateFormToggle?.(false)
                    resetForm()
                  }}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={createApiKey.isPending || !isFormValid}
                  onClick={doCreateKey}
                >
                  {createApiKey.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Create Key
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    )
  },
)

export default ApiKeySelector
