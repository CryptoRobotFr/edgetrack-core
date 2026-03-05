import { ColumnDef } from "@tanstack/react-table"
import { TrendingUp, TrendingDown, Star } from "lucide-react"

import { DataTableColumnHeader } from "./data-table-column-header"
import {
  formatUsd,
  formatPercent,
  formatDuration,
  formatDate,
  formatPriceRaw,
  formatNumber,
} from "@/lib/formatters"
import type { TradeListItem } from "@/hooks/useFuturesTrades"

export const columns: ColumnDef<TradeListItem>[] = [
  {
    accessorKey: "pair",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Pair" />
    ),
    cell: ({ row }) => {
      const pair = row.getValue("pair") as string
      const imageUrl = row.original.base_image_url

      return (
        <div className="flex items-center gap-2 min-w-[120px]">
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
    filterFn: (row, id, value) => {
      const pair = row.getValue(id) as string
      // Support both text search (string) and faceted filter (array)
      if (Array.isArray(value)) {
        return value.includes(pair)
      }
      return pair.toLowerCase().includes(value.toLowerCase())
    },
    enableHiding: false,
  },
  {
    accessorKey: "side",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Side" />
    ),
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
    filterFn: (row, id, value) => {
      return value.includes(row.getValue(id))
    },
  },
  {
    accessorKey: "entry_date",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Entry Date" />
    ),
    cell: ({ row }) => {
      const timestamp = row.getValue("entry_date") as number
      return (
        <span className="text-muted-foreground whitespace-nowrap">
          {formatDate(timestamp, { withTime: true })}
        </span>
      )
    },
  },
  {
    accessorKey: "exit_date",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Exit Date" />
    ),
    cell: ({ row }) => {
      const timestamp = row.getValue("exit_date") as number | null
      if (!timestamp) return <span className="text-muted-foreground">-</span>
      return (
        <span className="text-muted-foreground whitespace-nowrap">
          {formatDate(timestamp, { withTime: true })}
        </span>
      )
    },
  },
  {
    accessorKey: "mean_entry_price",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Entry Price" className="justify-end" />
    ),
    cell: ({ row }) => {
      const price = row.getValue("mean_entry_price") as number
      return <div className="text-right whitespace-nowrap">{formatPriceRaw(price)}$</div>
    },
  },
  {
    accessorKey: "mean_exit_price",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Exit Price" className="justify-end" />
    ),
    cell: ({ row }) => {
      const price = row.getValue("mean_exit_price") as number | null
      if (!price) return <div className="text-right text-muted-foreground">-</div>
      return <div className="text-right whitespace-nowrap">{formatPriceRaw(price)}$</div>
    },
  },
  {
    id: "size",
    accessorKey: "entry_size",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Size" className="justify-end" />
    ),
    cell: ({ row }) => {
      const size = row.original.entry_size
      const decimals = row.original.size_decimals
      return <div className="text-right">{formatNumber(size, decimals)}</div>
    },
    enableHiding: true,
  },
  {
    accessorKey: "entry_usd_size",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Entry $ Size" className="justify-end" />
    ),
    cell: ({ row }) => {
      const size = row.getValue("entry_usd_size") as number
      return <div className="text-right">{formatUsd(size)}</div>
    },
    enableHiding: true,
  },
  {
    accessorKey: "exit_usd_size",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Exit $ Size" className="justify-end" />
    ),
    cell: ({ row }) => {
      const size = row.getValue("exit_usd_size") as number
      return <div className="text-right">{formatUsd(size)}</div>
    },
    enableHiding: true,
  },
  {
    accessorKey: "pnl",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="PnL" className="justify-end" />
    ),
    cell: ({ row }) => {
      const pnl = row.getValue("pnl") as number
      const isPositive = pnl >= 0

      return (
        <div
          className={`text-right font-medium whitespace-nowrap ${
            isPositive ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"
          }`}
        >
          {formatUsd(pnl, { showSign: true })}
        </div>
      )
    },
  },
  {
    accessorKey: "pnl_pct",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="PnL %" className="justify-end" />
    ),
    cell: ({ row }) => {
      const pnlPct = row.getValue("pnl_pct") as number
      const isPositive = pnlPct >= 0

      return (
        <div
          className={`text-right whitespace-nowrap ${
            isPositive ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"
          }`}
        >
          {formatPercent(pnlPct, { showSign: true })}
        </div>
      )
    },
  },
  {
    accessorKey: "equity_pct_pnl",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Equity PnL %" className="justify-end" />
    ),
    cell: ({ row }) => {
      const pnlPct = row.getValue("equity_pct_pnl") as number
      const isPositive = pnlPct >= 0

      return (
        <div
          className={`text-right whitespace-nowrap ${
            isPositive ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"
          }`}
        >
          {formatPercent(pnlPct, { showSign: true })}
        </div>
      )
    },
    enableHiding: true,
  },
  {
    accessorKey: "total_fees",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Total Fees" className="justify-end" />
    ),
    cell: ({ row }) => {
      const fees = row.original.fees as number
      const fundingFees = row.original.funding_fees as number
      const displayValue = -(fees + fundingFees)
      return (
        <div className={`text-right font-medium whitespace-nowrap ${displayValue >= 0 ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
          {formatUsd(displayValue, { showSign: true })}
        </div>
      )
    },
  },
  {
    accessorKey: "duration_ms",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Duration" />
    ),
    cell: ({ row }) => {
      const durationMs = row.getValue("duration_ms") as number
      return (
        <span className="text-muted-foreground whitespace-nowrap">
          {formatDuration(durationMs)}
        </span>
      )
    },
  },
  {
    accessorKey: "duration_bucket",
    header: () => null,
    cell: () => null,
    filterFn: (row, id, value) => {
      return value.includes(row.getValue(id))
    },
    enableHiding: true,
    enableSorting: false,
  },
  {
    accessorKey: "leverage",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Lev." className="justify-end" />
    ),
    cell: ({ row }) => {
      const leverage = row.getValue("leverage") as number | null
      return (
        <div className="text-right">
          {leverage ? `${leverage}x` : "-"}
        </div>
      )
    },
    filterFn: (row, id, value) => {
      const leverage = row.getValue(id) as number | null
      return value.includes(String(leverage))
    },
  },
  {
    accessorKey: "margin_mode",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Margin" />
    ),
    cell: ({ row }) => {
      const marginMode = row.getValue("margin_mode") as string
      return (
        <span className="capitalize text-muted-foreground">
          {marginMode}
        </span>
      )
    },
    filterFn: (row, id, value) => {
      return value.includes(row.getValue(id))
    },
    enableHiding: true,
  },
  {
    accessorKey: "position_mode",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Pos. Mode" />
    ),
    cell: ({ row }) => {
      const posMode = row.getValue("position_mode") as string
      return (
        <span className="text-muted-foreground whitespace-nowrap">
          {posMode === "one_way" ? "One-way" : "Hedge"}
        </span>
      )
    },
    enableHiding: true,
  },
  {
    accessorKey: "order_count",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Orders" className="justify-end" />
    ),
    cell: ({ row }) => {
      const count = row.getValue("order_count") as number
      return <div className="text-right">{count}</div>
    },
    enableHiding: true,
  },
  {
    accessorKey: "fees",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Trade Fees" className="justify-end" />
    ),
    cell: ({ row }) => {
      const fees = row.getValue("fees") as number
      const displayValue = -fees
      return (
        <div className={`text-right font-medium whitespace-nowrap ${displayValue >= 0 ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
          {formatUsd(displayValue, { showSign: true })}
        </div>
      )
    },
    enableHiding: true,
  },
  {
    accessorKey: "funding_fees",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Fund. Fees" className="justify-end" />
    ),
    cell: ({ row }) => {
      const fees = row.getValue("funding_fees") as number
      const displayValue = -fees
      return (
        <div className={`text-right font-medium whitespace-nowrap ${displayValue >= 0 ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
          {formatUsd(displayValue, { showSign: true })}
        </div>
      )
    },
    enableHiding: true,
  },
  {
    accessorKey: "rating",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Rating" />
    ),
    cell: ({ row }) => {
      const rating = row.getValue("rating") as number
      return (
        <div className="flex">
          {[1, 2, 3, 4, 5].map((star) => (
            <Star
              key={star}
              className={`h-3.5 w-3.5 ${
                star <= rating
                  ? "fill-yellow-400 text-yellow-400"
                  : "text-muted-foreground/30"
              }`}
            />
          ))}
        </div>
      )
    },
    enableHiding: true,
  },
]

// Default visible columns
export const defaultColumnVisibility: Record<string, boolean> = {
  pair: true,
  side: true,
  entry_date: true,
  exit_date: true,
  mean_entry_price: true,
  mean_exit_price: true,
  size: true,
  entry_usd_size: false,
  exit_usd_size: false,
  pnl: true,
  pnl_pct: true,
  equity_pct_pnl: false,
  total_fees: true,
  duration_ms: true,
  duration_bucket: false,  // Hidden column for filtering only
  leverage: false,
  margin_mode: false,
  position_mode: false,
  order_count: false,
  fees: false,
  funding_fees: false,
  rating: false,
}
