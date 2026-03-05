import { useState } from "react"
import { AlertTriangle, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { useUpdateAccount } from "@/hooks/useAccountMutations"
import type { AccountOverviewItem } from "@/hooks/useAccountsOverview"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldLabel } from "@/components/ui/field"
import ApiKeySelector from "./ApiKeySelector"

interface EditAccountDialogProps {
  account: AccountOverviewItem
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function EditAccountDialog({
  account,
  open,
  onOpenChange,
}: EditAccountDialogProps) {
  const updateAccount = useUpdateAccount()
  const [name, setName] = useState(account.name)
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null)
  const [isChangingKey, setIsChangingKey] = useState(false)

  const isUpdating = updateAccount.isPending

  const handleOpenChange = (nextOpen: boolean) => {
    if (isUpdating) return
    if (!nextOpen) {
      // Reset state on close
      setName(account.name)
      setSelectedKeyId(null)
      setIsChangingKey(false)
    }
    onOpenChange(nextOpen)
  }

  const handleSave = async () => {
    const data: { name?: string; api_key_id?: string } = {}

    if (name.trim() !== account.name) {
      data.name = name.trim()
    }
    if (isChangingKey && selectedKeyId) {
      data.api_key_id = selectedKeyId
    }

    // Nothing to update
    if (Object.keys(data).length === 0) {
      onOpenChange(false)
      return
    }

    try {
      await updateAccount.mutateAsync({
        accountId: account.id,
        data,
      })
      toast.success("Account updated", {
        description: `"${name.trim()}" has been updated.`,
      })
      onOpenChange(false)
    } catch (err) {
      toast.error("Failed to update account", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    }
  }

  const maskKey = (key: string): string => {
    if (key.length <= 8) return key
    return `${key.substring(0, 4)}...${key.substring(key.length - 4)}`
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="sm:max-w-[425px]"
        onInteractOutside={(e) => {
          if (isUpdating) e.preventDefault()
        }}
        onEscapeKeyDown={(e) => {
          if (isUpdating) e.preventDefault()
        }}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {account.exchange_avatar_url && (
              <img
                src={account.exchange_avatar_url}
                alt={`${account.exchange_name} logo`}
                className="h-5 w-5 rounded-full"
              />
            )}
            <span>{account.name}</span>
          </DialogTitle>
          <DialogDescription>
            Update your account details below.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4 space-y-6 relative">
          <Field>
            <FieldLabel>Account Name</FieldLabel>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isUpdating}
            />
          </Field>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <FieldLabel>API Key</FieldLabel>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsChangingKey(!isChangingKey)
                  if (isChangingKey) setSelectedKeyId(null)
                }}
                disabled={isUpdating}
              >
                {isChangingKey ? "Cancel" : "Change Key"}
              </Button>
            </div>

            {!isChangingKey ? (
              <div className="text-sm text-muted-foreground font-mono">
                Current: {account.api_key_name} ({maskKey(account.api_key_id)})
              </div>
            ) : (
              <>
                <div className="rounded-md border border-amber-500/50 bg-amber-500/10 p-3 text-sm">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                    <div>
                      <p className="font-medium text-amber-700 dark:text-amber-400">
                        Warning: Changing API Key
                      </p>
                      <p className="mt-1 text-muted-foreground">
                        Only change the API key if you regenerated your credentials on the{" "}
                        <strong className="text-foreground">same exchange account</strong>. If you want to
                        track a different exchange account, create a new account instead. Using
                        credentials from a different exchange account will cause data inconsistencies.
                      </p>
                    </div>
                  </div>
                </div>

                <ApiKeySelector
                  exchangeName={account.exchange_name}
                  selectedKeyId={selectedKeyId}
                  onKeySelected={setSelectedKeyId}
                  onNewKeyCreated={setSelectedKeyId}
                />
              </>
            )}
          </div>

          {isUpdating && (
            <div className="absolute inset-0 bg-background/90 backdrop-blur-sm flex flex-col items-center justify-center rounded-lg z-20 p-4">
              <Loader2 className="h-10 w-10 animate-spin text-primary mb-4" />
              <p className="text-center text-lg font-semibold text-foreground">
                Updating Account...
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isUpdating}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isUpdating || !name.trim()}
          >
            {isUpdating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
