import { useParams, useNavigate, useLocation } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { ResponsiveDialog } from "@/components/responsive-dialog"
import { useAccount } from "@/contexts/AccountContext"
import { useTradeDetail } from "@/hooks/useTradeDetail"
import { useTradeOrders } from "@/hooks/useTradeOrders"
import { useUpdateTrade } from "@/hooks/useUpdateTrade"
import { formatPercent } from "@/lib/formatters"
import type { PositionItem } from "@/hooks/usePositions"
import { TradeInfoCard } from "./components/TradeInfoCard"
import { OhlcvChart } from "./components/OhlcvChart"
import { TradePnlChart } from "./components/TradePnlChart"
import { OrdersCard } from "./components/OrdersCard"
import { RatingCard } from "./components/RatingCard"
import { NotesCard } from "./components/NotesCard"

export default function TradeDetailDialog() {
  const { tradeId } = useParams<{ tradeId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { selectedAccountId } = useAccount()

  const isPositionView = location.pathname.startsWith("/futures/positions/")
  const position = (location.state as { position?: PositionItem })?.position ?? null

  const { data: trade, isLoading: isLoadingTrade } = useTradeDetail(tradeId ?? null)
  const { data: ordersData, isLoading: isLoadingOrders } = useTradeOrders(tradeId ?? null)
  const updateTrade = useUpdateTrade()

  const handleClose = () => {
    // Navigate to parent route (remove /:tradeId segment)
    const parentPath = location.pathname.replace(/\/[^/]+$/, "")
    navigate(parentPath)
  }

  const handleRatingChange = (rating: number) => {
    if (!tradeId) return
    updateTrade.mutate({ tradeId, rating })
  }

  const handleNotesChange = (notes: string) => {
    if (!tradeId) return
    updateTrade.mutate({ tradeId, notes })
  }

  // Loading state
  if (isLoadingTrade) {
    return (
      <ResponsiveDialog
        open={true}
        onOpenChange={(open) => !open && handleClose()}
        ariaTitle="Loading trade details"
      >
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </ResponsiveDialog>
    )
  }

  // Error or not found state
  if (!trade) {
    return (
      <ResponsiveDialog
        open={true}
        onOpenChange={(open) => !open && handleClose()}
        ariaTitle="Trade not found"
      >
        <div className="flex items-center justify-center py-12">
          <p className="text-muted-foreground">Trade not found</p>
        </div>
      </ResponsiveDialog>
    )
  }

  const orders = ordersData?.orders ?? []
  const isLong = trade.side === "long"
  const displayPnlPct = isPositionView && position ? position.pnl_pct : trade.pnl_pct
  const isProfitable = isPositionView && position ? position.unrealized_pnl >= 0 : trade.pnl >= 0

  return (
    <ResponsiveDialog
      open={true}
      onOpenChange={(open) => !open && handleClose()}
      ariaTitle={`Trade details for ${trade.pair}`}
    >
      {/* Header */}
      <div className="flex items-center pb-4 border-b mb-4">
        <div className="flex items-center gap-3">
          {trade.base_image_url && (
            <img src={trade.base_image_url} alt="" className="h-8 w-8 rounded-full" />
          )}
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold">{trade.pair}</span>
            <span className="text-sm text-muted-foreground">
              {trade.margin_mode.toUpperCase()}
            </span>
            <span className={`text-sm font-medium ${isLong ? "text-green-500 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
              {trade.side.toUpperCase()}
            </span>
            <span className="text-sm text-muted-foreground">{trade.leverage}x</span>
          </div>
          <div
            className={`px-2 py-1 rounded text-sm font-semibold ${
              isProfitable
                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300"
            }`}
          >
            {formatPercent(displayPnlPct, { showSign: true })}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {/* Row 1: TradeInfoCard - full width */}
        <TradeInfoCard trade={trade} position={isPositionView ? position : null} />

        {/* OHLCV (14/20) | Rating+Notes (6/20) | PnL+Orders below OHLCV */}
        {/* On mobile: OHLCV → PnL+Orders → Rating+Notes */}
        <div className="grid grid-cols-1 @xl:grid-cols-[14fr_6fr] gap-4">
          <div className="min-w-0">
            {selectedAccountId && (
              <OhlcvChart
                accountId={selectedAccountId}
                base={trade.base}
                quote={trade.quote}
                entryDate={trade.entry_date}
                exitDate={trade.exit_date}
                meanEntryPrice={trade.mean_entry_price}
                orders={orders}
                side={trade.side as "long" | "short"}
              />
            )}
          </div>
          <div className="space-y-4 order-last @xl:order-none @xl:row-span-2">
            <RatingCard
              rating={trade.rating}
              onRatingChange={handleRatingChange}
              isSaving={updateTrade.isPending}
            />
            <NotesCard
              notes={trade.notes}
              onNotesChange={handleNotesChange}
              isSaving={updateTrade.isPending}
            />
          </div>
          <div className="grid grid-cols-1 @lg:grid-cols-2 gap-4">
            {tradeId && <TradePnlChart tradeId={tradeId} />}
            <OrdersCard
              orders={orders}
              isLoading={isLoadingOrders}
              sizeDecimals={trade.size_decimals}
              base={trade.base}
            />
          </div>
        </div>
      </div>
    </ResponsiveDialog>
  )
}
