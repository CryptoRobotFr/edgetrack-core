import { useState } from "react"
import { useNavigate, useLocation, Outlet } from "react-router-dom"
import { format } from "date-fns"
import { CalendarIcon, X } from "lucide-react"
import { type DateRange as DayPickerDateRange } from "react-day-picker"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"

const tabs = [
  { value: "pnl", label: "P&L", path: "/futures/analysis/pnl" },
  { value: "equity", label: "Equity", path: "/futures/analysis/equity" },
]

export interface AnalysisDateRange {
  startDate: number | null
  endDate: number | null
}

export default function AnalysisPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [dateRange, setDateRange] = useState<DayPickerDateRange | undefined>(undefined)
  const [open, setOpen] = useState(false)

  // Determine active tab from URL
  const activeTab = tabs.find((tab) => location.pathname === tab.path)?.value ?? "pnl"

  const handleTabChange = (value: string) => {
    const tab = tabs.find((t) => t.value === value)
    if (tab) {
      navigate(tab.path)
    }
  }

  // Convert Date to UTC timestamp in milliseconds (start of day for from, end of day for to)
  // Note: Create new Date objects to avoid mutating the original state
  const analysisDateRange: AnalysisDateRange = {
    startDate: dateRange?.from
      ? new Date(new Date(dateRange.from).setHours(0, 0, 0, 0)).getTime()
      : null,
    endDate: dateRange?.to
      ? new Date(new Date(dateRange.to).setHours(23, 59, 59, 999)).getTime()
      : null,
  }

  const handleClearFilter = () => {
    setDateRange(undefined)
    setOpen(false)
  }

  const formatDateRange = () => {
    if (!dateRange?.from) return "Select dates"
    if (!dateRange.to) return format(dateRange.from, "MMM d, yyyy")
    return `${format(dateRange.from, "MMM d")} - ${format(dateRange.to, "MMM d, yyyy")}`
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList>
            {tabs.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}>
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                "justify-start text-left font-normal",
                !dateRange?.from && "text-muted-foreground"
              )}
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {formatDateRange()}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="end">
            <Calendar
              mode="range"
              defaultMonth={dateRange?.from}
              selected={dateRange}
              onSelect={setDateRange}
              numberOfMonths={2}
            />
            <div className="flex items-center justify-end gap-2 border-t p-3">
              {dateRange?.from && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearFilter}
                >
                  <X className="mr-1 h-4 w-4" />
                  Clear
                </Button>
              )}
              <Button size="sm" onClick={() => setOpen(false)}>
                Apply
              </Button>
            </div>
          </PopoverContent>
        </Popover>
      </div>

      {/* Tab content rendered via nested route, with date range context */}
      <Outlet context={analysisDateRange} />
    </div>
  )
}
