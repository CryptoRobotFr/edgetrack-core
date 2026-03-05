import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ArrowDownNarrowWide, ArrowUpNarrowWide, HelpCircle } from "lucide-react"
import { WinRateGauge } from "@/components/charts/WinRateGauge"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { formatUsd, formatPercent } from "@/lib/formatters"

interface TopPair {
  pair: string
  pnl: number
  base_image_url?: string | null
}

interface PositionCardProps {
  positionType: "long" | "short"
  total: number
  wins: number
  losses: number
  winRate: number
  pnl: number
  topPairs: TopPair[]
}

export function PositionCard({
  positionType,
  total,
  wins,
  losses,
  winRate,
  pnl,
  topPairs,
}: PositionCardProps) {
  return (
    <Card className="px-2 h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-0">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            {positionType === "long" ? "Long Positions" : "Short Positions"}
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Statistics for {positionType} positions only</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        {positionType === "long" ? (
          <ArrowUpNarrowWide className="w-3.5 h-3.5 text-muted-foreground" />
        ) : (
          <ArrowDownNarrowWide className="w-3.5 h-3.5 text-muted-foreground" />
        )}
      </CardHeader>
      <CardContent className="p-4">
        <div className="grid gap-4 grid-cols-2">
          {/* Total */}
          <div>
            <p className="text-muted-foreground text-sm">Total</p>
            <div className="flex items-center pt-2">
              <p className="mr-3 font-bold text-2xl">{total}</p>
              <p className="text-sm text-muted-foreground">
                {wins} Win / {losses} Loss
              </p>
            </div>
          </div>

          {/* Win Rate */}
          <div>
            <p className="text-muted-foreground text-sm">Win Rate</p>
            <div className="flex items-center">
              <div className="size-12 mr-3">
                <WinRateGauge winRate={winRate} />
              </div>
              <p className="font-bold text-2xl">{formatPercent(winRate, { decimals: 0 })}</p>
            </div>
          </div>

          {/* Closed P&L */}
          <div>
            <p className="text-muted-foreground text-sm">Closed P&L</p>
            <div className="flex items-center pt-2">
              <p
                className={`font-mono font-bold text-2xl ${
                  pnl >= 0
                    ? "text-emerald-700 dark:text-emerald-400"
                    : "text-red-700 dark:text-red-400"
                } mr-2`}
              >
                {formatUsd(pnl, { showSign: true, withSuffix: false })}
              </p>
              <p className="font-semibold text-md hidden @sm:hidden @md:block @lg:hidden @xl:block">
                USD
              </p>
            </div>
          </div>

          {/* Best Pairs */}
          <div>
            <p className="text-muted-foreground text-sm">Best Pairs</p>
            <div className="flex items-center pt-1">
              {topPairs.length > 0 ? (
                topPairs.map((pair, index) => (
                  <TooltipProvider key={pair.pair}>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger asChild>
                        <div
                          className={`relative ${index !== 0 ? "-ml-3" : ""}`}
                          style={{ zIndex: 50 - (topPairs.length - 1 - index) }}
                        >
                          <Avatar className="size-9 border border-border">
                            {pair.base_image_url && (
                              <AvatarImage src={pair.base_image_url} alt={pair.pair} />
                            )}
                            <AvatarFallback className="text-xs">
                              {pair.pair.split("/")[0].slice(0, 2).toUpperCase()}
                            </AvatarFallback>
                          </Avatar>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>
                          {pair.pair} {formatUsd(pair.pnl, { showSign: true, withSuffix: false })} USD
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                ))
              ) : (
                <p className="text-sm text-muted-foreground pt-2">No trades yet</p>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
