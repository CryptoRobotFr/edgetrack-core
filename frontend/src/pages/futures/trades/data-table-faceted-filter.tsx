import * as React from "react"
import { Column } from "@tanstack/react-table"
import { Check, PlusCircle, Search } from "lucide-react"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Separator } from "@/components/ui/separator"

interface DataTableFacetedFilterProps<TData, TValue> {
  column?: Column<TData, TValue>
  title?: string
  options: {
    label: string
    value: string | number
    icon?: React.ComponentType<{ className?: string }>
    imageUrl?: string | null
  }[]
  searchable?: boolean
}

export function DataTableFacetedFilter<TData, TValue>({
  column,
  title,
  options,
  searchable = false,
}: DataTableFacetedFilterProps<TData, TValue>) {
  const facets = column?.getFacetedUniqueValues()
  const filterValue = column?.getFilterValue() as (string | number)[] | undefined
  const selectedValues = new Set(filterValue?.map(v => String(v)) ?? [])
  const [search, setSearch] = React.useState("")

  const filteredOptions = React.useMemo(() => {
    if (!searchable || !search) return options
    const term = search.toLowerCase()
    return options.filter((option) => option.label.toLowerCase().includes(term))
  }, [options, search, searchable])

  return (
    <Popover onOpenChange={() => setSearch("")}>
      <PopoverTrigger asChild>
        <Button variant="secondary" size="sm" className="h-8">
          <PlusCircle className="mr-2 h-4 w-4" />
          {title}
          {selectedValues?.size > 0 && (
            <>
              <Separator orientation="vertical" className="mx-2 h-4" />
              <Badge
                variant="secondary"
                className="rounded-sm px-1 font-normal lg:hidden"
              >
                {selectedValues.size}
              </Badge>
              <div className="hidden space-x-1 lg:flex items-center">
                {options
                  .filter((option) => selectedValues.has(String(option.value)))
                  .map((option) =>
                    option.imageUrl ? (
                      <img
                        key={String(option.value)}
                        src={option.imageUrl}
                        alt={option.label}
                        title={option.label}
                        className="h-4 w-4 rounded-full"
                      />
                    ) : (
                      <Badge
                        variant="secondary"
                        key={String(option.value)}
                        className="rounded-sm px-1 font-normal"
                      >
                        {option.label}
                      </Badge>
                    )
                  )}
              </div>
            </>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[200px] p-0" align="start">
        {searchable && (
          <div className="p-2 pb-0">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 pl-7 text-sm"
              />
            </div>
          </div>
        )}
        <div className="p-2">
          <div className={cn("space-y-1", searchable && "max-h-[240px] overflow-y-auto")}>
            {filteredOptions.map((option) => {
              const optionKey = String(option.value)
              const isSelected = selectedValues.has(optionKey)
              // Get count - facets use original type (number or string)
              const count = facets?.get(option.value)
              return (
                <div
                  key={optionKey}
                  className={cn(
                    "flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm cursor-pointer hover:bg-accent",
                    isSelected && "bg-accent"
                  )}
                  onClick={() => {
                    if (isSelected) {
                      selectedValues.delete(optionKey)
                    } else {
                      selectedValues.add(optionKey)
                    }
                    const filterValues = Array.from(selectedValues)
                    column?.setFilterValue(
                      filterValues.length ? filterValues : undefined
                    )
                  }}
                >
                  <div
                    className={cn(
                      "flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
                      isSelected
                        ? "bg-primary text-primary-foreground"
                        : "opacity-50 [&_svg]:invisible"
                    )}
                  >
                    <Check className="h-3 w-3" />
                  </div>
                  {option.imageUrl && (
                    <img src={option.imageUrl} alt="" className="h-4 w-4 rounded-full" />
                  )}
                  {option.icon && (
                    <option.icon className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span>{option.label}</span>
                  {count !== undefined && (
                    <span className="ml-auto flex h-4 w-4 items-center justify-center font-mono text-xs">
                      {count}
                    </span>
                  )}
                </div>
              )
            })}
            {searchable && filteredOptions.length === 0 && (
              <p className="text-center text-sm text-muted-foreground py-2">No results</p>
            )}
          </div>
        </div>
        {selectedValues.size > 0 && (
          <>
            <Separator />
            <div className="p-2">
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-center text-xs"
                onClick={() => column?.setFilterValue(undefined)}
              >
                Clear filters
              </Button>
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  )
}
