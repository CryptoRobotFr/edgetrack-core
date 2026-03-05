import { useNavigate } from "react-router-dom"
import { Eye } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { formatUsd, formatPercent, formatDate, formatPrice, formatDuration, formatNumber } from "@/lib/formatters"
import type { PositionItem } from "@/hooks/usePositions"
import { liqDistancePct } from "./PositionsList"

const gridClass = "grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-x-4 gap-y-1"
const fieldClass = "grid"
const labelClass = "text-xs text-muted-foreground"
const valueClass = "text-sm font-medium"

interface PositionCardProps {
  position: PositionItem
}

export function PositionCard({ position }: PositionCardProps) {
  const navigate = useNavigate()
  const isLong = position.side === "long"
  const isProfitable = position.unrealized_pnl >= 0
  const liqDist = liqDistancePct(position)

  const handleView = () => {
    if (position.matched_trade_id) {
      navigate(`/futures/positions/${position.matched_trade_id}`, {
        state: { position },
      })
    }
  }

  return (
    <Card className="w-full border py-1 bg-card">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 py-1 px-4">
        <div className="flex gap-x-2 items-center">
          {/* Coin image */}
          <div className="border rounded-full overflow-hidden">
            {position.base_image_url ? (
              <img
                src={position.base_image_url}
                alt={position.base}
                className="h-6 w-6"
              />
            ) : (
              <div className="h-6 w-6 bg-muted flex items-center justify-center">
                <span className="text-[10px] font-medium">{position.base.slice(0, 2)}</span>
              </div>
            )}
          </div>

          {/* Pair + metadata */}
          <CardTitle className={`text-sm lg:text-sm xl:text-base font-semibold ${isLong ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}`}>
            {position.pair}
            <span className="hidden md:inline">
              {" "}- {position.margin_mode.charAt(0).toUpperCase() + position.margin_mode.slice(1)} - {position.side.charAt(0).toUpperCase() + position.side.slice(1)}
            </span>
            {" "}- {position.leverage}X
          </CardTitle>

          {/* PnL% badge */}
          <div
            className={`${
              isProfitable
                ? "bg-emerald-600"
                : "bg-red-600"
            } text-white text-xs lg:text-sm font-semibold px-2 py-0.5 rounded-md flex items-center justify-center`}
          >
            {formatPercent(position.pnl_pct, { showSign: true })}
          </div>
        </div>

        {/* View button */}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button
                  variant="default"
                  className="p-2 m-0 h-7"
                  disabled={!position.matched_trade_id}
                  onClick={handleView}
                >
                  <Eye className="h-3.5 w-3.5 mr-1" />
                  View
                </Button>
              </span>
            </TooltipTrigger>
            {!position.matched_trade_id && (
              <TooltipContent>
                <p>No matched trade</p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </CardHeader>

      <CardContent className="p-2 px-4 pt-0">
        <Accordion type="single" collapsible>
          <AccordionItem value="details" className="border-b-0">
            <AccordionTrigger className="py-0 hover:no-underline">
              <div className={`${gridClass} cursor-pointer w-full text-left`}>
                {/* Position Size - always visible */}
                <div className={fieldClass}>
                  <p className={labelClass}>Size</p>
                  <p className={valueClass}>
                    {formatNumber(position.size, position.size_decimals)} {position.base.toUpperCase()} ~ {formatUsd(position.usd_size)}
                  </p>
                </div>

                {/* Unrealized PnL - always visible */}
                <div className={fieldClass}>
                  <p className={labelClass}>Unrealized PnL</p>
                  <p
                    className={`${valueClass} ${
                      isProfitable
                        ? "text-emerald-700 dark:text-emerald-400"
                        : "text-red-700 dark:text-red-400"
                    }`}
                  >
                    {formatUsd(position.unrealized_pnl, { showSign: true })}
                  </p>
                </div>

                {/* Mark Price - hidden on mobile */}
                <div className={`${fieldClass} hidden md:grid`}>
                  <p className={labelClass}>Mark Price</p>
                  <p className={valueClass}>{formatPrice(position.mark_price, { decimals: position.price_decimals })}$</p>
                </div>

                {/* Entry Price - hidden below lg */}
                <div className={`${fieldClass} hidden lg:grid`}>
                  <p className={labelClass}>Entry Price</p>
                  <p className={valueClass}>{formatPrice(position.entry_price, { decimals: position.price_decimals })}$</p>
                </div>

                {/* Liquidation Price - hidden below xl */}
                <div className={`${fieldClass} hidden xl:grid`}>
                  <p className={labelClass}>Liq. Price</p>
                  <p className={valueClass}>
                    {liqDist !== null && liqDist < 1000
                      ? <>{formatPrice(position.liquidation_price!, { decimals: position.price_decimals })}$ <span className="text-xs text-muted-foreground">({formatPercent(liqDist)})</span></>
                      : "—"}
                  </p>
                </div>

                {/* Position Margin - hidden below 2xl */}
                <div className={`${fieldClass} hidden 2xl:grid`}>
                  <p className={labelClass}>Margin</p>
                  <p className={valueClass}>
                    {position.margin ? formatUsd(position.margin) : "—"}
                  </p>
                </div>
              </div>
            </AccordionTrigger>

            <AccordionContent className="pb-0">
              <div className="flex items-start">
              <div className={`${gridClass} flex-1 pt-2 pb-0`}>
                {/* Mark Price - shown on mobile when hidden above */}
                <div className={`${fieldClass} grid md:hidden`}>
                  <p className={labelClass}>Mark Price</p>
                  <p className={valueClass}>{formatPrice(position.mark_price, { decimals: position.price_decimals })}$</p>
                </div>

                {/* Entry Price - shown below lg when hidden above */}
                <div className={`${fieldClass} grid lg:hidden`}>
                  <p className={labelClass}>Entry Price</p>
                  <p className={valueClass}>{formatPrice(position.entry_price, { decimals: position.price_decimals })}$</p>
                </div>

                {/* Liquidation Price - shown below xl when hidden above */}
                <div className={`${fieldClass} grid xl:hidden`}>
                  <p className={labelClass}>Liq. Price</p>
                  <p className={valueClass}>
                    {liqDist !== null && liqDist < 1000
                      ? <>{formatPrice(position.liquidation_price!, { decimals: position.price_decimals })}$ <span className="text-xs text-muted-foreground">({formatPercent(liqDist)})</span></>
                      : "—"}
                  </p>
                </div>

                {/* Entry Date */}
                {position.created_at && (
                  <div className={fieldClass}>
                    <p className={labelClass}>Entry Date</p>
                    <p className={valueClass}>
                      {formatDate(position.created_at, { withTime: true })}
                    </p>
                  </div>
                )}

                {/* Margin - shown below 2xl when hidden above */}
                <div className={`${fieldClass} grid 2xl:hidden`}>
                  <p className={labelClass}>Margin</p>
                  <p className={valueClass}>
                    {position.margin ? formatUsd(position.margin) : "—"}
                  </p>
                </div>

                {/* Realized PnL */}
                <div className={fieldClass}>
                  <p className={labelClass}>Realized PnL</p>
                  <p
                    className={`${valueClass} ${
                      position.realized_pnl >= 0
                        ? "text-emerald-700 dark:text-emerald-400"
                        : "text-red-700 dark:text-red-400"
                    }`}
                  >
                    {formatUsd(position.realized_pnl, { showSign: true })}
                  </p>
                </div>

                {/* Duration */}
                {position.created_at && (
                  <div className={fieldClass}>
                    <p className={labelClass}>Duration</p>
                    <p className={valueClass}>
                      {formatDuration(Date.now() - position.created_at)}
                    </p>
                  </div>
                )}

                {/* Orders */}
                <div className={fieldClass}>
                  <p className={labelClass}>Orders</p>
                  <p className={valueClass}>{position.order_count}</p>
                </div>
              </div>
              {/* Invisible spacer matching AccordionTrigger's chevron (w-4 shrink-0) */}
              <div className="w-4 shrink-0" />
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </CardContent>
    </Card>
  )
}
