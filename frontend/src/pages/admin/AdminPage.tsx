import { useState } from "react"
import {
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UserCheck,
  UserX,
} from "lucide-react"
import { toast } from "sonner"
import {
  useAdminUsers,
  useAdminInvitations,
  useDeactivateUser,
  useActivateUser,
  useDeleteUser,
  useCreateInvitation,
  useDeleteInvitation,
} from "@/hooks/useAdmin"
import { formatDate } from "@/lib/formatters"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldLabel, FieldDescription } from "@/components/ui/field"

// --- Users Section ---

function UsersSection() {
  const { data: users, isLoading, error, refetch, isFetching } = useAdminUsers()
  const deactivateUser = useDeactivateUser()
  const activateUser = useActivateUser()
  const deleteUser = useDeleteUser()

  const [deleteTarget, setDeleteTarget] = useState<{ id: string; email: string } | null>(null)
  const [deleteConfirmInput, setDeleteConfirmInput] = useState("")

  const handleToggleActive = async (userId: string, currentlyActive: boolean) => {
    try {
      if (currentlyActive) {
        await deactivateUser.mutateAsync(userId)
        toast.success("User deactivated")
      } else {
        await activateUser.mutateAsync(userId)
        toast.success("User activated")
      }
    } catch (err) {
      toast.error("Failed to update user status", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteUser.mutateAsync(deleteTarget.id)
      toast.success("User deleted", {
        description: "User and all associated data have been permanently deleted.",
      })
      setDeleteTarget(null)
      setDeleteConfirmInput("")
    } catch (err) {
      toast.error("Failed to delete user", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Users</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Users</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive">{(error as Error).message}</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Users</CardTitle>
              <CardDescription>{users?.length || 0} registered user(s)</CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Accounts</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users?.map((user) => (
                <TableRow key={user.id}>
                  <TableCell
                    className="font-mono text-xs text-muted-foreground cursor-pointer hover:text-foreground"
                    title={`Click to copy: ${user.id}`}
                    onClick={() => {
                      navigator.clipboard.writeText(user.id)
                      toast.success("User ID copied to clipboard")
                    }}
                  >
                    {user.id.slice(0, 8)}
                  </TableCell>
                  <TableCell className="font-mono text-sm">{user.masked_email}</TableCell>
                  <TableCell>
                    {user.is_active ? (
                      <Badge variant="default" className="bg-emerald-600 hover:bg-emerald-600">Active</Badge>
                    ) : (
                      <Badge variant="destructive">Inactive</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {user.is_superuser && (
                      <Badge variant="secondary">
                        <ShieldCheck className="h-3 w-3 mr-1" />
                        Admin
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{user.accounts_count}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      {!user.is_superuser && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleToggleActive(user.id, user.is_active)}
                            disabled={deactivateUser.isPending || activateUser.isPending}
                            title={user.is_active ? "Deactivate user" : "Activate user"}
                          >
                            {user.is_active ? (
                              <UserX className="h-4 w-4" />
                            ) : (
                              <UserCheck className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteTarget({ id: user.id, email: user.masked_email })}
                            title="Delete user"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Delete User Confirmation Dialog */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(v) => {
          if (!v) {
            setDeleteTarget(null)
            setDeleteConfirmInput("")
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete User?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the user{" "}
              <strong className="text-foreground">{deleteTarget?.email}</strong>{" "}
              and ALL associated data (API keys, accounts, trades, orders, equity history).
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-2">
            <Field>
              <FieldLabel>Type the user ID to confirm</FieldLabel>
              <Input
                value={deleteConfirmInput}
                onChange={(e) => setDeleteConfirmInput(e.target.value)}
                placeholder={deleteTarget?.id.slice(0, 8) + "..."}
                className="font-mono text-sm"
              />
              <FieldDescription>
                Enter <span className="font-mono text-foreground">{deleteTarget?.id.slice(0, 8)}</span> to confirm deletion
              </FieldDescription>
            </Field>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteUser.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={
                deleteUser.isPending ||
                deleteConfirmInput !== deleteTarget?.id.slice(0, 8)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteUser.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {deleteUser.isPending ? "Deleting..." : "Delete User"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// --- Invitations Section ---

function InvitationsSection() {
  const { data: invitations, isLoading, error, refetch, isFetching } = useAdminInvitations()
  const createInvitation = useCreateInvitation()
  const deleteInvitation = useDeleteInvitation()

  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [expiresInDays, setExpiresInDays] = useState(7)

  const handleCreate = async () => {
    try {
      const inv = await createInvitation.mutateAsync(expiresInDays)
      const inviteUrl = `${window.location.origin}/signup?invite=${inv.token}`
      await navigator.clipboard.writeText(inviteUrl)
      toast.success("Invitation created", {
        description: "Invitation link copied to clipboard.",
      })
      setShowCreateDialog(false)
      setExpiresInDays(7)
    } catch (err) {
      toast.error("Failed to create invitation", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    }
  }

  const handleCopyLink = async (token: string) => {
    const inviteUrl = `${window.location.origin}/signup?invite=${token}`
    await navigator.clipboard.writeText(inviteUrl)
    toast.success("Invitation link copied to clipboard")
  }

  const handleDelete = async (invitationId: string) => {
    try {
      await deleteInvitation.mutateAsync(invitationId)
      toast.success("Invitation revoked")
    } catch (err) {
      toast.error("Failed to revoke invitation", {
        description: err instanceof Error ? err.message : "Unknown error",
      })
    }
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return <Badge variant="outline">Pending</Badge>
      case "used":
        return <Badge variant="default" className="bg-emerald-600 hover:bg-emerald-600">Used</Badge>
      case "expired":
        return <Badge variant="secondary">Expired</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Invitations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Invitations</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive">{(error as Error).message}</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Invitations</CardTitle>
              <CardDescription>
                Generate single-use invitation links for new users
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isFetching}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <Button
                size="sm"
                onClick={() => setShowCreateDialog(true)}
              >
                <Plus className="h-4 w-4 mr-2" />
                Create Invitation
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {invitations && invitations.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Token</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invitations.map((inv) => (
                  <TableRow key={inv.id}>
                    <TableCell className="font-mono text-sm">
                      {inv.token.slice(0, 12)}...
                    </TableCell>
                    <TableCell>{statusBadge(inv.status)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(inv.created_at)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(inv.expires_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {inv.status === "pending" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleCopyLink(inv.token)}
                            title="Copy invitation link"
                          >
                            <Link2 className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(inv.id)}
                          disabled={deleteInvitation.isPending}
                          title="Delete invitation"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <Link2 className="h-8 w-8 mb-2" />
              <p>No invitations yet</p>
              <p className="text-sm">Create an invitation to invite new users</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Invitation Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Invitation</DialogTitle>
            <DialogDescription>
              Generate a single-use invitation link. The link will be copied to your clipboard.
            </DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel>Expires in (days)</FieldLabel>
            <Input
              type="number"
              min={1}
              max={90}
              value={expiresInDays}
              onChange={(e) => setExpiresInDays(Number(e.target.value))}
            />
            <FieldDescription>
              Between 1 and 90 days (default: 7)
            </FieldDescription>
          </Field>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCreateDialog(false)}
              disabled={createInvitation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={createInvitation.isPending || expiresInDays < 1 || expiresInDays > 90}
            >
              {createInvitation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {createInvitation.isPending ? "Creating..." : "Create & Copy Link"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// --- Main Page ---

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <UsersSection />
      <InvitationsSection />
    </div>
  )
}
