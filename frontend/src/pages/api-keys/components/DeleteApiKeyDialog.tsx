import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { useDeleteApiKey } from "@/hooks/useAccountMutations"
import type { components } from "@/api/schema"
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

type ApiKeyResponse = components["schemas"]["ApiKeyResponse"]

interface DeleteApiKeyDialogProps {
  apiKey: ApiKeyResponse
  open: boolean
  onOpenChange: (open: boolean) => void
}

function capitalizeFirst(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export default function DeleteApiKeyDialog({
  apiKey,
  open,
  onOpenChange,
}: DeleteApiKeyDialogProps) {
  const deleteApiKey = useDeleteApiKey()
  const isDeleting = deleteApiKey.isPending

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault()

    try {
      await deleteApiKey.mutateAsync(apiKey.id)
      toast.success("API key deleted", {
        description: `"${apiKey.name}" has been permanently deleted.`,
      })
      onOpenChange(false)
    } catch (err) {
      toast.error("Failed to delete API key", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={(v) => { if (!isDeleting) onOpenChange(v) }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete API Key?</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently delete the API key{" "}
            <strong className="text-foreground">"{apiKey.name}"</strong>{" "}
            ({capitalizeFirst(apiKey.exchange_name)}). This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
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
