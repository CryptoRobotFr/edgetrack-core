import { Row } from "@tanstack/react-table"
import { Copy, Eye, MoreHorizontal, StickyNote } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface DataTableRowActionsProps<TData> {
  row: Row<TData>
  onViewDetails?: (row: TData) => void
  onAddNote?: (row: TData) => void
}

export function DataTableRowActions<TData extends { id: string }>({
  row,
  onViewDetails,
  onAddNote,
}: DataTableRowActionsProps<TData>) {
  const trade = row.original

  const handleCopyId = () => {
    navigator.clipboard.writeText(trade.id)
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="flex h-8 w-8 p-0 data-[state=open]:bg-muted"
        >
          <MoreHorizontal className="h-4 w-4" />
          <span className="sr-only">Open menu</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[160px]">
        <DropdownMenuItem onClick={() => onViewDetails?.(trade)}>
          <Eye className="mr-2 h-4 w-4" />
          View details
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleCopyId}>
          <Copy className="mr-2 h-4 w-4" />
          Copy trade ID
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => onAddNote?.(trade)}>
          <StickyNote className="mr-2 h-4 w-4" />
          Add note
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
