import { useState } from "react"
import { format, getWeek } from "date-fns"
import { ChevronsLeft, ChevronsRight, Calendar } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { MonthPicker } from "./MonthPicker"
import { CalendarViewMode } from "@/types/calendar"
import { formatUsd } from "@/lib/formatters"

interface CalendarHeaderProps {
  currentMonth: Date
  onNavigate: (direction: "next" | "previous") => void
  onMonthSelect: (date: Date) => void
  monthlyPnL: number
  viewMode: CalendarViewMode
  isLoading: boolean
  isFullscreen?: boolean
}

export function CalendarHeader({
  currentMonth,
  onNavigate,
  onMonthSelect,
  monthlyPnL,
  viewMode,
  isLoading,
  isFullscreen = false,
}: CalendarHeaderProps) {
  const [popoverOpen, setPopoverOpen] = useState(false)

  return (
    <div
      className={`flex items-center justify-center gap-x-4 ${isFullscreen ? "h-[100px]" : "h-[80px]"}`}
    >
      {/* Previous button */}
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0"
        onClick={() => onNavigate("previous")}
        disabled={isLoading}
      >
        <ChevronsLeft className="h-5 w-5 text-muted-foreground" />
      </Button>

      {/* Center content */}
      <div className="flex flex-col items-center justify-center h-full min-h-[80px]">
        {/* Month/Year title with calendar button as a single block */}
        <div className="flex items-center gap-1 h-8">
          {/* Full format for @sm and above, short format below */}
          <h2 className="text-xl font-bold text-center text-muted-foreground whitespace-nowrap hidden @sm:block">
            {format(currentMonth, "MMMM yyyy")}
          </h2>
          <h2 className="text-xl font-bold text-center text-muted-foreground whitespace-nowrap @sm:hidden">
            {format(currentMonth, "MMM. yy")}
          </h2>
          {!isFullscreen && (
            <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  disabled={isLoading}
                >
                  <Calendar className="h-4 w-4" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="center">
                <MonthPicker
                  currentMonth={currentMonth}
                  onMonthChange={(date) => {
                    onMonthSelect(date)
                    setPopoverOpen(false)
                  }}
                />
              </PopoverContent>
            </Popover>
          )}
        </div>

        {/* Week number (for week view) */}
        {viewMode === "week" && (
          <div className="flex items-center gap-1 h-6">
            <span className="text-sm text-muted-foreground whitespace-nowrap">
              Week {getWeek(currentMonth, { weekStartsOn: 1 })}
            </span>
          </div>
        )}

        {/* Monthly PnL */}
        <div className="h-8 flex items-center">
          {isLoading ? (
            <span className="inline-block w-20 h-6 bg-muted animate-pulse rounded" />
          ) : (
            <p
              className={`font-mono font-bold text-xl whitespace-nowrap ${
                monthlyPnL === 0
                  ? "text-muted-foreground"
                  : monthlyPnL > 0
                    ? "text-emerald-700 dark:text-emerald-400"
                    : "text-red-700 dark:text-red-400"
              }`}
            >
              {formatUsd(monthlyPnL, { showSign: true })}
            </p>
          )}
        </div>
      </div>

      {/* Next button */}
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0"
        onClick={() => onNavigate("next")}
        disabled={isLoading}
      >
        <ChevronsRight className="h-5 w-5 text-muted-foreground" />
      </Button>
    </div>
  )
}
