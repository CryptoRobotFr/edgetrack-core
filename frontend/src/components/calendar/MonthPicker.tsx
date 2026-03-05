import { useState } from "react"
import {
  add,
  eachMonthOfInterval,
  endOfYear,
  format,
  isEqual,
  isFuture,
  parse,
  startOfMonth,
  startOfToday,
} from "date-fns"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"

function getStartOfCurrentMonth() {
  return startOfMonth(startOfToday())
}

interface MonthPickerProps {
  currentMonth: Date
  onMonthChange: (newMonth: Date) => void
}

export function MonthPicker({ currentMonth, onMonthChange }: MonthPickerProps) {
  const [currentYear, setCurrentYear] = useState(format(currentMonth, "yyyy"))
  const firstDayCurrentYear = parse(currentYear, "yyyy", new Date())

  const months = eachMonthOfInterval({
    start: firstDayCurrentYear,
    end: endOfYear(firstDayCurrentYear),
  })

  function previousYear() {
    const firstDayPrevYear = add(firstDayCurrentYear, { years: -1 })
    setCurrentYear(format(firstDayPrevYear, "yyyy"))
  }

  function nextYear() {
    const firstDayNextYear = add(firstDayCurrentYear, { years: 1 })
    setCurrentYear(format(firstDayNextYear, "yyyy"))
  }

  return (
    <div className="p-3">
      <div className="flex flex-col space-y-4">
        <div className="space-y-4">
          {/* Year navigation */}
          <div className="relative flex items-center justify-center pt-1">
            <div className="text-sm font-medium">
              {format(firstDayCurrentYear, "yyyy")}
            </div>
            <div className="flex items-center space-x-1">
              <Button
                variant="outline"
                size="icon"
                className="absolute left-1 h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100"
                type="button"
                onClick={previousYear}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="absolute right-1 h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100 disabled:bg-muted"
                type="button"
                disabled={isFuture(add(firstDayCurrentYear, { years: 1 }))}
                onClick={nextYear}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Month grid */}
          <div className="grid w-full grid-cols-3 gap-2">
            {months.map((month) => (
              <div
                key={month.toString()}
                className="relative p-0 text-center text-sm"
              >
                <Button
                  variant={isEqual(month, currentMonth) ? "default" : "ghost"}
                  className={`h-9 w-16 p-0 text-sm font-normal ${
                    !isEqual(month, currentMonth) &&
                    isEqual(month, getStartOfCurrentMonth())
                      ? "bg-muted"
                      : ""
                  }`}
                  disabled={isFuture(month)}
                  type="button"
                  onClick={() => onMonthChange(month)}
                >
                  <time dateTime={format(month, "yyyy-MM-dd")}>
                    {format(month, "MMM")}
                  </time>
                </Button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
