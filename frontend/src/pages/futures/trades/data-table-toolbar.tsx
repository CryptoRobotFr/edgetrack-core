import * as React from "react"
import { format } from "date-fns"
import { Table } from "@tanstack/react-table"
import { X, TrendingUp, TrendingDown, Clock, CalendarIcon } from "lucide-react"
import { type DateRange as DayPickerDateRange } from "react-day-picker"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { DataTableViewOptions } from "./data-table-view-options"
import { DataTableFacetedFilter } from "./data-table-faceted-filter"

interface DataTableToolbarProps<TData> {
  table: Table<TData>
  dateRange?: DayPickerDateRange
  onDateRangeChange?: (range: DayPickerDateRange | undefined) => void
}

const sideOptions = [
  {
    label: "Long",
    value: "long",
    icon: TrendingUp,
  },
  {
    label: "Short",
    value: "short",
    icon: TrendingDown,
  },
]

const marginModeOptions = [
  {
    label: "Cross",
    value: "cross",
  },
  {
    label: "Isolated",
    value: "isolated",
  },
]

const durationOptions = [
  { label: "<1h", value: "<1h", icon: Clock },
  { label: "<1d", value: "<1d", icon: Clock },
  { label: "<1w", value: "<1w", icon: Clock },
  { label: ">1w", value: ">1w", icon: Clock },
]

export function DataTableToolbar<TData>({
  table,
  dateRange,
  onDateRangeChange,
}: DataTableToolbarProps<TData>) {
  const isFiltered = table.getState().columnFilters.length > 0
  const [calendarOpen, setCalendarOpen] = React.useState(false)
  // Local state for pending date selection (requires 2 clicks before applying)
  const [pendingDateRange, setPendingDateRange] = React.useState<DayPickerDateRange | undefined>(dateRange)

  // Sync pending state when external dateRange changes
  React.useEffect(() => {
    if (!calendarOpen) {
      setPendingDateRange(dateRange)
    }
  }, [dateRange, calendarOpen])

  // Get dynamic leverage options from data
  const leverageOptions = React.useMemo(() => {
    const leverageColumn = table.getColumn("leverage")
    if (!leverageColumn) return []

    const facets = leverageColumn.getFacetedUniqueValues()
    const leverageValues = Array.from(facets.keys())
      .filter((v) => v !== null)
      .map((v) => Number(v))
      .sort((a, b) => a - b)

    return leverageValues.map((lev) => ({
      label: `${lev}x`,
      value: lev, // Keep as number for facet lookup
    }))
  }, [table.getColumn("leverage")?.getFacetedUniqueValues()])

  // Get dynamic pair options from data (with image URLs)
  const pairOptions = React.useMemo(() => {
    const pairColumn = table.getColumn("pair")
    if (!pairColumn) return []

    const facets = pairColumn.getFacetedUniqueValues()
    const pairs = Array.from(facets.keys())
      .filter((v) => v !== null && v !== "")
      .sort()

    // Build pair -> imageUrl map from rows
    const pairImageMap = new Map<string, string | null>()
    for (const row of table.getCoreRowModel().rows) {
      const original = row.original as Record<string, unknown>
      const pair = original.pair as string | undefined
      const imageUrl = original.base_image_url as string | null | undefined
      if (pair && imageUrl && !pairImageMap.has(pair)) {
        pairImageMap.set(pair, imageUrl)
      }
    }

    return pairs.map((pair) => ({
      label: String(pair),
      value: String(pair),
      imageUrl: pairImageMap.get(String(pair)) ?? null,
    }))
  }, [table.getColumn("pair")?.getFacetedUniqueValues(), table.getCoreRowModel().rows])

  const formatDateRangeLabel = () => {
    if (!dateRange?.from) return "All time"
    if (!dateRange.to) return format(dateRange.from, "MMM d, yyyy")
    return `${format(dateRange.from, "MMM d")} - ${format(dateRange.to, "MMM d, yyyy")}`
  }

  const handleClearDateFilter = () => {
    setPendingDateRange(undefined)
    onDateRangeChange?.(undefined)
    setCalendarOpen(false)
  }

  const handleApplyDateFilter = () => {
    onDateRangeChange?.(pendingDateRange)
    setCalendarOpen(false)
  }

  // Check if a complete range is selected (both from and to dates)
  const hasCompleteRange = pendingDateRange?.from && pendingDateRange?.to

  return (
    <div className="flex flex-col @md:flex-row @md:items-center @md:justify-between gap-2">
      <div className="flex flex-1 items-center space-x-2 flex-wrap gap-y-2">
        {table.getColumn("pair") && pairOptions.length > 0 && (
          <DataTableFacetedFilter
            column={table.getColumn("pair")}
            title="Pair"
            options={pairOptions}
            searchable
          />
        )}
        {table.getColumn("side") && (
          <DataTableFacetedFilter
            column={table.getColumn("side")}
            title="Side"
            options={sideOptions}
          />
        )}
        {table.getColumn("duration_bucket") && (
          <DataTableFacetedFilter
            column={table.getColumn("duration_bucket")}
            title="Duration"
            options={durationOptions}
          />
        )}
        {table.getColumn("margin_mode") && (
          <DataTableFacetedFilter
            column={table.getColumn("margin_mode")}
            title="Margin"
            options={marginModeOptions}
          />
        )}
        {table.getColumn("leverage") && leverageOptions.length > 0 && (
          <DataTableFacetedFilter
            column={table.getColumn("leverage")}
            title="Leverage"
            options={leverageOptions}
          />
        )}
        {isFiltered && (
          <Button
            variant="ghost"
            onClick={() => table.resetColumnFilters()}
            className="h-8 px-2 lg:px-3"
          >
            Reset
            <X className="ml-2 h-4 w-4" />
          </Button>
        )}
      </div>
      <div className="flex items-center space-x-2">
        <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="default"
              size="sm"
              className="h-8 justify-start text-left font-normal"
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {formatDateRangeLabel()}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="end">
            <Calendar
              mode="range"
              defaultMonth={pendingDateRange?.from ?? dateRange?.from}
              selected={pendingDateRange}
              onSelect={setPendingDateRange}
              numberOfMonths={2}
            />
            <div className="flex items-center justify-end gap-2 border-t p-3">
              {(pendingDateRange?.from || dateRange?.from) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearDateFilter}
                >
                  <X className="mr-1 h-4 w-4" />
                  Clear
                </Button>
              )}
              <Button
                size="sm"
                onClick={handleApplyDateFilter}
                disabled={pendingDateRange?.from && !hasCompleteRange}
              >
                Apply
              </Button>
            </div>
          </PopoverContent>
        </Popover>
        <DataTableViewOptions table={table} />
      </div>
    </div>
  )
}
