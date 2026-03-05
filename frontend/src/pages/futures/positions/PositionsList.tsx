import { useState, useMemo } from "react"
import {
  HelpCircle,
  RefreshCw,
  Search,
  Inbox,
  TrendingUp,
  DollarSign,
  Clock,
  AlertTriangle,
  ArrowUp,
  ArrowDown,
} from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { PositionItem } from "@/hooks/usePositions"
import { PositionCard } from "./PositionCard"

type SortField = "unrealized_pnl" | "usd_size" | "duration" | "liquidation_price"
type SortDirection = "asc" | "desc"
type SortState = { field: SortField; direction: SortDirection } | null

const SORT_OPTIONS: { field: SortField; icon: typeof TrendingUp; label: string }[] = [
  { field: "unrealized_pnl", icon: TrendingUp, label: "Unrealized PnL" },
  { field: "usd_size", icon: DollarSign, label: "USD Size" },
  { field: "duration", icon: Clock, label: "Duration" },
  { field: "liquidation_price", icon: AlertTriangle, label: "Liquidation Price" },
]

/** % distance between liquidation price and mark price (lower = closer to liq) */
export function liqDistancePct(position: PositionItem): number | null {
  if (!position.liquidation_price || position.liquidation_price <= 0 || position.mark_price <= 0) return null
  return Math.abs(position.liquidation_price - position.mark_price) / position.mark_price * 100
}

function getSortValue(position: PositionItem, field: SortField): number {
  switch (field) {
    case "unrealized_pnl":
      return position.unrealized_pnl
    case "usd_size":
      return position.usd_size
    case "duration":
      return position.created_at ?? Infinity
    case "liquidation_price":
      return liqDistancePct(position) ?? Infinity
  }
}

interface PositionsListProps {
  positions: PositionItem[]
  isLoading: boolean
  onRefresh: () => void
}

export function PositionsList({
  positions,
  isLoading,
  onRefresh,
}: PositionsListProps) {
  const [search, setSearch] = useState("")
  const [sort, setSort] = useState<SortState>(null)

  const handleSort = (field: SortField) => {
    setSort((prev) => {
      if (!prev || prev.field !== field) return { field, direction: "desc" }
      if (prev.direction === "desc") return { field, direction: "asc" }
      return null
    })
  }

  const filteredPositions = useMemo(() => {
    let result = positions
    if (search.trim()) {
      const searchLower = search.toLowerCase()
      result = result.filter((p) => p.pair.toLowerCase().includes(searchLower))
    }
    if (sort) {
      const multiplier = sort.direction === "desc" ? -1 : 1
      // For duration, lower created_at = older = longer duration, so we invert
      const durationFlip = sort.field === "duration" ? -1 : 1
      result = [...result].sort((a, b) => {
        const va = getSortValue(a, sort.field)
        const vb = getSortValue(b, sort.field)
        return (va - vb) * multiplier * durationFlip
      })
    }
    return result
  }, [positions, search, sort])

  return (
    <Card className="bg-secondary">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-2">
        <div className="flex items-center gap-2">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Live Positions
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Current open positions on exchange</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        <div className="flex items-center gap-2">
          {/* Sort buttons */}
          <TooltipProvider>
            <div className="flex items-center gap-0.5">
              {SORT_OPTIONS.map(({ field, icon: Icon, label }) => {
                const isActive = sort?.field === field
                return (
                  <Tooltip key={field}>
                    <TooltipTrigger asChild>
                      <Button
                        variant={isActive ? "secondary" : "outline"}
                        size="sm"
                        className="h-7 w-7 p-0 relative"
                        onClick={() => handleSort(field)}
                      >
                        <Icon className="h-3.5 w-3.5" />
                        {isActive && (
                          sort.direction === "desc"
                            ? <ArrowDown className="h-2.5 w-2.5 absolute -bottom-0.5 -right-0.5" />
                            : <ArrowUp className="h-2.5 w-2.5 absolute -bottom-0.5 -right-0.5" />
                        )}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{label}{isActive ? ` (${sort.direction === "desc" ? "↓" : "↑"})` : ""}</p>
                    </TooltipContent>
                  </Tooltip>
                )
              })}
            </div>
          </TooltipProvider>

          {/* Search input - hidden on mobile */}
          <div className="relative hidden sm:block">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search pair..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-[140px] pl-7 text-sm"
            />
          </div>

          {/* Refresh button */}
          <Button
            variant="outline"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={onRefresh}
            disabled={isLoading}
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`}
            />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-0">
        {filteredPositions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Inbox className="h-8 w-8 mb-2" />
            <p>{search ? "No positions match your search" : "No open positions"}</p>
          </div>
        ) : (
          <ScrollArea className="w-full rounded-md pr-3">
            <div className="max-h-[36rem] flex flex-col gap-y-1 p-0">
              {filteredPositions.map((position) => (
                <PositionCard
                  key={position.pair + "-" + position.side}
                  position={position}
                />
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
