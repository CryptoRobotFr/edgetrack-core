import { useState, useCallback } from "react"
import { Outlet, useNavigate } from "react-router-dom"
import { AlertCircle } from "lucide-react"
import { type DateRange as DayPickerDateRange } from "react-day-picker"
import { type ColumnFiltersState } from "@tanstack/react-table"

import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

import { useAccount } from "@/contexts/AccountContext"
import { PnlByPairChartCard } from "@/components/cards/PnlByPairChartCard"
import type { PnlByPairBarClickEvent } from "@/components/charts/PnlByPairBar"
import { useFuturesTrades, type TradeListItem } from "@/hooks/useFuturesTrades"
import { DataTable } from "./trades/data-table"
import { columns } from "./trades/columns"

interface DateRange {
  startDate: number | null
  endDate: number | null
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-[250px]" />
        <Skeleton className="h-8 w-[180px]" />
      </div>
      <div className="rounded-md border">
        <div className="p-4 space-y-4">
          {[...Array(10)].map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-[150px]" />
        <Skeleton className="h-8 w-[300px]" />
      </div>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-center py-12">
        <div className="text-center">
          <AlertCircle className="h-8 w-8 mx-auto mb-2 text-red-500" />
          <p className="text-muted-foreground">{message}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function NoAccountState() {
  return (
    <Card>
      <CardContent className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">
          Select an account to view trades
        </p>
      </CardContent>
    </Card>
  )
}

export default function TradesPage() {
  const navigate = useNavigate()
  const { selectedAccountId } = useAccount()
  const [dateRange, setDateRange] = useState<DayPickerDateRange | undefined>(undefined)
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])

  const handleBarClick = useCallback((event: PnlByPairBarClickEvent) => {
    setColumnFilters([
      { id: "pair", value: [event.pair] },
      { id: "side", value: [event.side] },
    ])
  }, [])

  // Convert Date to UTC timestamp in milliseconds
  const analysisDateRange: DateRange = {
    startDate: dateRange?.from
      ? new Date(new Date(dateRange.from).setHours(0, 0, 0, 0)).getTime()
      : null,
    endDate: dateRange?.to
      ? new Date(new Date(dateRange.to).setHours(23, 59, 59, 999)).getTime()
      : null,
  }

  const { data, isLoading, error } = useFuturesTrades(
    selectedAccountId,
    analysisDateRange
  )

  const handleViewDetails = (trade: TradeListItem) => {
    navigate(`/futures/trades/${trade.id}`)
  }

  const handleAddNote = (trade: TradeListItem) => {
    // Navigate to the trade detail dialog
    navigate(`/futures/trades/${trade.id}`)
  }

  if (!selectedAccountId) {
    return <NoAccountState />
  }

  return (
    <div className="space-y-4">
      {isLoading ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorState message="Failed to load trades data" />
      ) : (
        <>
          <DataTable
            columns={columns}
            data={data?.trades ?? []}
            onViewDetails={handleViewDetails}
            onAddNote={handleAddNote}
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            columnFilters={columnFilters}
            onColumnFiltersChange={setColumnFilters}
          />
          {data?.trades?.length ? (
            <PnlByPairChartCard trades={data.trades} onBarClick={handleBarClick} />
          ) : null}
        </>
      )}

      {/* Outlet for nested trade detail dialog route */}
      <Outlet />
    </div>
  )
}
