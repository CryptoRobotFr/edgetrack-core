import { useState, useMemo } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { useQueryClient } from "@tanstack/react-query"
import { useAccount } from "@/contexts/AccountContext"
import { useDeleteAccount, useDeleteApiKey } from "@/hooks/useAccountMutations"
import type { AccountOverviewItem } from "@/hooks/useAccountsOverview"
import { Checkbox } from "@/components/ui/checkbox"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

interface DeleteAccountDialogProps {
  account: AccountOverviewItem
  allAccounts: AccountOverviewItem[]
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function DeleteAccountDialog({
  account,
  allAccounts,
  open,
  onOpenChange,
}: DeleteAccountDialogProps) {
  const queryClient = useQueryClient()
  const { refreshAccounts } = useAccount()
  const deleteAccount = useDeleteAccount()
  const deleteApiKey = useDeleteApiKey()
  const [alsoDeleteKey, setAlsoDeleteKey] = useState(false)

  const isDeleting = deleteAccount.isPending || deleteApiKey.isPending

  /** Check if the API key will become orphaned after deleting this account */
  const willBeOrphaned = useMemo(() => {
    const accountsWithSameKey = allAccounts.filter(
      (a) => a.api_key_id === account.api_key_id
    )
    return accountsWithSameKey.length <= 1
  }, [allAccounts, account.api_key_id])

  const handleDelete = async (e: React.MouseEvent) => {
    // Prevent AlertDialogAction from auto-closing the dialog
    // so we can show the loading state and close only after success
    e.preventDefault()

    try {
      const result = await deleteAccount.mutateAsync(account.id)

      // Also delete the orphaned API key if the user opted in
      if (alsoDeleteKey && result.orphaned_api_key_id) {
        try {
          await deleteApiKey.mutateAsync(result.orphaned_api_key_id)
          toast.success("Account and API key deleted", {
            description: `"${account.name}" and API key "${account.api_key_name}" have been permanently deleted.`,
          })
        } catch (err) {
          toast.success("Account deleted", {
            description: `"${account.name}" has been deleted.`,
          })
          toast.error("Failed to delete API key", {
            description: err instanceof Error ? err.message : "Unknown error",
          })
        }
      } else {
        toast.success("Account deleted", {
          description: `"${account.name}" has been permanently deleted.`,
        })
      }

      await queryClient.invalidateQueries({ queryKey: ["accounts"] })
      await queryClient.invalidateQueries({ queryKey: ["api-keys"] })
      refreshAccounts()
      setAlsoDeleteKey(false)
      onOpenChange(false)
    } catch (err) {
      toast.error("Failed to delete account", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    }
  }

  const handleCancel = () => {
    setAlsoDeleteKey(false)
    onOpenChange(false)
  }

  return (
    <AlertDialog open={open} onOpenChange={(v) => { if (!v) handleCancel(); else onOpenChange(v) }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>
                This action cannot be undone. This will permanently delete the account{" "}
                <strong className="text-foreground">"{account.name}"</strong> (
                {account.exchange_name} - {account.product_type ?? account.account_type}) and all
                its synced trading data.
              </p>
              {willBeOrphaned && (
                <label className="flex items-center gap-2 cursor-pointer pt-1">
                  <Checkbox
                    checked={alsoDeleteKey}
                    onCheckedChange={(checked) => setAlsoDeleteKey(checked === true)}
                  />
                  <span className="text-sm text-muted-foreground">
                    Also delete API key{" "}
                    <strong className="text-foreground">"{account.api_key_name}"</strong>{" "}
                    (no longer used by any account)
                  </span>
                </label>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleCancel} disabled={isDeleting}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleDelete}
            disabled={isDeleting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isDeleting ? "Deleting..." : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
