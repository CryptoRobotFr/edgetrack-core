import * as React from "react"
import {
  ColumnDef,
  ColumnFiltersState,
  SortingState,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { type DateRange as DayPickerDateRange } from "react-day-picker"

import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { DataTablePagination } from "./data-table-pagination"
import { DataTableToolbar } from "./data-table-toolbar"
import { defaultColumnVisibility } from "./columns"
import { formatUsd, formatPercent, formatDuration } from "@/lib/formatters"

const STORAGE_KEY = "edgetrack:futures-trades-columns"

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  onViewDetails?: (row: TData) => void
  onAddNote?: (row: TData) => void
  dateRange?: DayPickerDateRange
  onDateRangeChange?: (range: DayPickerDateRange | undefined) => void
  columnFilters?: ColumnFiltersState
  onColumnFiltersChange?: (filters: ColumnFiltersState) => void
}

export function DataTable<TData, TValue>({
  columns,
  data,
  onViewDetails,
  onAddNote,
  dateRange,
  onDateRangeChange,
  columnFilters: controlledColumnFilters,
  onColumnFiltersChange,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [internalColumnFilters, setInternalColumnFilters] = React.useState<ColumnFiltersState>([])

  const columnFilters = controlledColumnFilters ?? internalColumnFilters
  const handleColumnFiltersChange: typeof setInternalColumnFilters = React.useCallback(
    (updater) => {
      if (onColumnFiltersChange) {
        const newValue = typeof updater === "function" ? updater(columnFilters) : updater
        onColumnFiltersChange(newValue)
      } else {
        setInternalColumnFilters(updater)
      }
    },
    [columnFilters, onColumnFiltersChange]
  )
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>(() => {
    // Load from localStorage on initial render
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      try {
        return JSON.parse(saved)
      } catch {
        return defaultColumnVisibility
      }
    }
    return defaultColumnVisibility
  })

  // Persist column visibility to localStorage
  React.useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(columnVisibility))
  }, [columnVisibility])

  // Inject callbacks into column meta
  const columnsWithMeta = React.useMemo(() => {
    return columns.map((col) => ({
      ...col,
      meta: {
        ...(col.meta || {}),
        onViewDetails,
        onAddNote,
      },
    }))
  }, [columns, onViewDetails, onAddNote])

  const table = useReactTable({
    data,
    columns: columnsWithMeta,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: handleColumnFiltersChange,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
    initialState: {
      pagination: {
        pageSize: 20,
      },
    },
  })

  // Calculate aggregations
  const filteredRows = table.getFilteredRowModel().rows
  const aggregations = React.useMemo(() => {
    if (filteredRows.length === 0) {
      return {
        totalPnl: 0,
        avgPnlPct: 0,
        totalFees: 0,
        totalFundingFees: 0,
        avgDuration: 0,
        avgLeverage: 0,
        avgOrders: 0,
      }
    }

    let totalPnl = 0
    let totalPnlPct = 0
    let totalFees = 0
    let totalFundingFees = 0
    let totalDuration = 0
    let totalLeverage = 0
    let leverageCount = 0
    let totalOrders = 0

    filteredRows.forEach((row) => {
      const rowData = row.original as {
        pnl: number
        pnl_pct: number
        fees: number
        funding_fees: number
        duration_ms: number
        leverage: number | null
        order_count: number
      }
      totalPnl += rowData.pnl
      totalPnlPct += rowData.pnl_pct
      totalFees += rowData.fees
      totalFundingFees += rowData.funding_fees
      totalDuration += rowData.duration_ms
      if (rowData.leverage !== null) {
        totalLeverage += rowData.leverage
        leverageCount++
      }
      totalOrders += rowData.order_count
    })

    return {
      totalPnl,
      avgPnlPct: totalPnlPct / filteredRows.length,
      totalFees,
      totalFundingFees,
      avgDuration: totalDuration / filteredRows.length,
      avgLeverage: leverageCount > 0 ? totalLeverage / leverageCount : 0,
      avgOrders: totalOrders / filteredRows.length,
    }
  }, [filteredRows])

  return (
    <div className="space-y-4">
      <DataTableToolbar
        table={table}
        dateRange={dateRange}
        onDateRangeChange={onDateRangeChange}
      />
      <div className="rounded-md border overflow-x-auto">
        <Table className="min-w-[1200px]">
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id} colSpan={header.colSpan}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => onViewDetails?.(row.original as TData)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No closed trades found for the selected period.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
          {filteredRows.length > 0 && (
            <TableFooter>
              <TableRow className="bg-muted/50">
                {table.getVisibleLeafColumns().map((column) => {
                  const colId = column.id
                  let content: React.ReactNode = null

                  if (colId === "pair") {
                    content = (
                      <span className="font-medium text-muted-foreground">
                        {filteredRows.length} trades
                      </span>
                    )
                  } else if (colId === "pnl") {
                    content = (
                      <span className={`font-medium ${aggregations.totalPnl >= 0 ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
                        {formatUsd(aggregations.totalPnl, { showSign: true })}
                      </span>
                    )
                  } else if (colId === "pnl_pct") {
                    content = (
                      <span className={`font-medium ${aggregations.avgPnlPct >= 0 ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
                        ø {formatPercent(aggregations.avgPnlPct, { showSign: true })}
                      </span>
                    )
                  } else if (colId === "fees") {
                    const displayFees = -aggregations.totalFees
                    content = (
                      <span className={`font-medium ${displayFees >= 0 ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
                        {formatUsd(displayFees, { showSign: true })}
                      </span>
                    )
                  } else if (colId === "funding_fees") {
                    const displayFunding = -aggregations.totalFundingFees
                    content = (
                      <span className={`font-medium ${displayFunding >= 0 ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
                        {formatUsd(displayFunding, { showSign: true })}
                      </span>
                    )
                  } else if (colId === "total_fees") {
                    const displayTotal = -(aggregations.totalFees + aggregations.totalFundingFees)
                    content = (
                      <span className={`font-medium ${displayTotal >= 0 ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
                        {formatUsd(displayTotal, { showSign: true })}
                      </span>
                    )
                  } else if (colId === "duration_ms") {
                    content = (
                      <span className="font-medium text-muted-foreground">
                        ø {formatDuration(aggregations.avgDuration)}
                      </span>
                    )
                  } else if (colId === "leverage") {
                    content = (
                      <span className="font-medium text-muted-foreground">
                        ø {aggregations.avgLeverage.toFixed(1)}x
                      </span>
                    )
                  } else if (colId === "order_count") {
                    content = (
                      <span className="font-medium text-muted-foreground">
                        ø {aggregations.avgOrders.toFixed(1)}
                      </span>
                    )
                  }

                  return (
                    <TableCell key={column.id} className="text-right">
                      {content}
                    </TableCell>
                  )
                })}
              </TableRow>
            </TableFooter>
          )}
        </Table>
      </div>
      <DataTablePagination table={table} />
    </div>
  )
}
