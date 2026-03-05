import { ColumnDef } from "@tanstack/react-table"
import { ArrowUpDown, TrendingUp, TrendingDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { formatUsd, formatPercent, formatDuration, formatDate, formatPriceRaw } from "@/lib/formatters"
import type { components } from "@/api/schema"

type TradeAnalysis = components["schemas"]["TradeAnalysis"]

export const columns: ColumnDef<TradeAnalysis>[] = [
  {
    accessorKey: "pair",
    header: "Pair",
    cell: ({ row }) => {
      const pair = row.getValue("pair") as string
      const imageUrl = row.original.base_image_url

      return (
        <div className="flex items-center gap-2">
          {imageUrl && (
            <img
              src={imageUrl}
              alt=""
              className="h-5 w-5 rounded-full"
            />
          )}
          <span className="font-medium">{pair}</span>
        </div>
      )
    },
  },
  {
    accessorKey: "side",
    header: "Side",
    cell: ({ row }) => {
      const side = row.getValue("side") as string
      const isLong = side === "long"

      return (
        <div className="flex items-center gap-1">
          {isLong ? (
            <TrendingUp className="h-3.5 w-3.5 text-green-500 dark:text-green-400" />
          ) : (
            <TrendingDown className="h-3.5 w-3.5 text-red-500 dark:text-red-400" />
          )}
          <span className={isLong ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}>
            {side.toUpperCase()}
          </span>
        </div>
      )
    },
  },
  {
    accessorKey: "entry_date",
    header: ({ column }) => {
      return (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          className="-ml-4"
        >
          Entry Date
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      )
    },
    cell: ({ row }) => {
      const timestamp = row.getValue("entry_date") as number
      return <span className="text-muted-foreground">{formatDate(timestamp, { withTime: true })}</span>
    },
  },
  {
    accessorKey: "exit_date",
    header: "Exit Date",
    cell: ({ row }) => {
      const timestamp = row.getValue("exit_date") as number
      if (!timestamp) return <span className="text-muted-foreground">-</span>
      return <span className="text-muted-foreground">{formatDate(timestamp, { withTime: true })}</span>
    },
  },
  {
    accessorKey: "entry_price",
    header: () => <div className="text-right">Entry Price</div>,
    cell: ({ row }) => {
      const price = row.getValue("entry_price") as number
      return <div className="text-right">{formatPriceRaw(price)}$</div>
    },
  },
  {
    accessorKey: "exit_price",
    header: () => <div className="text-right">Exit Price</div>,
    cell: ({ row }) => {
      const price = row.getValue("exit_price") as number
      if (!price) return <div className="text-right text-muted-foreground">-</div>
      return <div className="text-right">{formatPriceRaw(price)}$</div>
    },
  },
  {
    accessorKey: "pnl",
    header: ({ column }) => {
      return (
        <div className="text-right">
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
            className="-mr-4"
          >
            PnL
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        </div>
      )
    },
    cell: ({ row }) => {
      const pnl = row.getValue("pnl") as number
      const isPositive = pnl >= 0

      return (
        <div className={`text-right font-medium ${isPositive ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
          {formatUsd(pnl, { showSign: true })}
        </div>
      )
    },
  },
  {
    accessorKey: "pnl_pct",
    header: () => <div className="text-right">PnL %</div>,
    cell: ({ row }) => {
      const pnlPct = row.getValue("pnl_pct") as number
      const isPositive = pnlPct >= 0

      return (
        <div className={`text-right ${isPositive ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
          {formatPercent(pnlPct, { showSign: true })}
        </div>
      )
    },
  },
  {
    accessorKey: "duration_ms",
    header: "Duration",
    cell: ({ row }) => {
      const durationMs = row.getValue("duration_ms") as number
      return <span className="text-muted-foreground">{formatDuration(durationMs)}</span>
    },
  },
  {
    accessorKey: "fees",
    header: () => <div className="text-right">Fees</div>,
    cell: ({ row }) => {
      const fees = row.getValue("fees") as number
      const fundingFees = row.original.funding_fees
      const totalFees = fees + fundingFees

      return (
        <div className="text-right text-muted-foreground">
          {formatUsd(totalFees)}
        </div>
      )
    },
  },
]
