import { Card } from "@/components/ui/card"
import {
  formatUsd,
  formatDuration,
  formatDate,
  formatPriceRaw,
  formatNumber,
  formatPercent,
} from "@/lib/formatters"
import type { TradeDetail } from "@/hooks/useTradeDetail"
import type { PositionItem } from "@/hooks/usePositions"

interface TradeInfoCardProps {
  trade: TradeDetail
  position?: PositionItem | null
}

function InfoItem({
  label,
  value,
  valueClassName,
}: {
  label: string
  value: React.ReactNode
  valueClassName?: string
}) {
  return (
    <div>
      <p className="text-xs @lg:text-sm @2xl:text-base text-muted-foreground font-medium">
        {label}
      </p>
      <p
        className={`text-xs @lg:text-sm @2xl:text-base ${valueClassName || "font-bold"}`}
      >
        {value}
      </p>
    </div>
  )
}

export function TradeInfoCard({ trade, position }: TradeInfoCardProps) {
  const isPositionView = !!position

  if (isPositionView) {
    const isLong = trade.side === "long"
    const tradePerf = isLong
      ? ((position.mark_price - trade.mean_entry_price) / trade.mean_entry_price) * 100
      : ((trade.mean_entry_price - position.mark_price) / trade.mean_entry_price) * 100

    return (
      <Card className="p-4">
        <div className="grid gap-x-8 gap-y-2 @lg:gap-y-1 grid-cols-2 @md:grid-cols-3 @lg:grid-cols-4 @xl:grid-cols-5 @2xl:grid-cols-6">
          <InfoItem
            label="Position Size"
            value={`${formatNumber(position.size, position.size_decimals)} ${position.base}`}
          />
          <InfoItem label="Position USD" value={formatUsd(position.usd_size)} />
          <InfoItem
            label="Entry Price"
            value={`${formatPriceRaw(trade.mean_entry_price)}$`}
          />
          <InfoItem
            label="Market Price"
            value={`${formatPriceRaw(position.mark_price)}$`}
          />
          <InfoItem
            label="Trade Performance"
            value={formatPercent(tradePerf, { showSign: true })}
            valueClassName={`font-bold ${
              tradePerf >= 0
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-red-700 dark:text-red-400"
            }`}
          />
          <InfoItem
            label="Unrealized PnL"
            value={formatUsd(position.unrealized_pnl, { showSign: true })}
            valueClassName={`font-bold ${
              position.unrealized_pnl >= 0
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-red-700 dark:text-red-400"
            }`}
          />
          <InfoItem
            label="Realized PnL"
            value={formatUsd(position.realized_pnl, { showSign: true })}
            valueClassName={`font-bold ${
              position.realized_pnl >= 0
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-red-700 dark:text-red-400"
            }`}
          />
          <InfoItem
            label="Entry Date"
            value={formatDate(trade.entry_date, { withTime: true })}
          />
          <InfoItem label="Duration" value={formatDuration(Date.now() - trade.entry_date)} />
          <InfoItem label="Trading Fees" value={formatUsd(trade.fees)} />
          <InfoItem label="Funding Fees" value={formatUsd(trade.funding_fees)} />
          <InfoItem
            label="Total Fees"
            value={formatUsd(trade.total_fees)}
            valueClassName="font-bold"
          />
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-4">
      <div className="grid gap-x-8 gap-y-2 @lg:gap-y-1 grid-cols-2 @md:grid-cols-3 @lg:grid-cols-4 @xl:grid-cols-5 @2xl:grid-cols-6">
        <InfoItem
          label="Entry Size"
          value={`${formatNumber(trade.entry_size, trade.size_decimals)} ${trade.base}`}
        />
        <InfoItem label="Entry USD" value={formatUsd(trade.entry_usd_size)} />
        <InfoItem
          label="Entry Price"
          value={`${formatPriceRaw(trade.mean_entry_price)}$`}
        />
        <InfoItem
          label="Exit Price"
          value={
            trade.mean_exit_price
              ? `${formatPriceRaw(trade.mean_exit_price)}$`
              : "-"
          }
        />
        <InfoItem
          label="Entry Date"
          value={formatDate(trade.entry_date, { withTime: true })}
        />
        <InfoItem
          label="Exit Date"
          value={
            trade.exit_date
              ? formatDate(trade.exit_date, { withTime: true })
              : "-"
          }
        />
        <InfoItem label="Duration" value={formatDuration(trade.duration_ms)} />
        <InfoItem label="Trading Fees" value={formatUsd(trade.fees)} />
        <InfoItem label="Funding Fees" value={formatUsd(trade.funding_fees)} />
        <InfoItem
          label="Total Fees"
          value={formatUsd(trade.total_fees)}
          valueClassName="font-bold"
        />
      </div>
    </Card>
  )
}
