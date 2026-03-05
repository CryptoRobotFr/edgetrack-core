import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"
import type {
  UnifiedFeedItem,
  LedgerFeedItem,
  OrderFeedItem,
  OhlcvFeedItem,
  FundingFeedItem,
  SystemFeedItem,
} from "@/hooks/useSyncStream"

interface LiveDataFeedProps {
  items: UnifiedFeedItem[]
}

/** Format timestamp to HH:mm:ss */
function formatTime(timestamp: number): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
}

/** Format decimal string to compact display */
function formatAmount(value: string, decimals: number = 4): string {
  const num = parseFloat(value)
  if (isNaN(num)) return value
  if (Math.abs(num) >= 1000) {
    return num.toLocaleString("en-US", { maximumFractionDigits: 2 })
  }
  return num.toFixed(decimals)
}

/** Format funding rate as percentage */
function formatRate(value: string): string {
  const num = parseFloat(value)
  if (isNaN(num)) return value
  return (num * 100).toFixed(4) + "%"
}

/** Render a single ledger item */
function LedgerLine({ item }: { item: LedgerFeedItem }) {
  const isPositive = parseFloat(item.amount) >= 0
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className="text-white/70">[{formatTime(item.date)}]</span>
      <span className="text-white">{item.type}</span>
      <span className={isPositive ? "text-emerald-400" : "text-red-400"}>
        {isPositive ? "+" : ""}
        {formatAmount(item.amount)}
      </span>
      <span className="text-white">{item.coin}</span>
    </div>
  )
}

/** Render a single order item */
function OrderLine({ item }: { item: OrderFeedItem }) {
  const isBuy = item.side === "BUY"
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className="text-white/70">[{formatTime(item.date)}]</span>
      <span className="text-white">{item.pair}</span>
      <span className={isBuy ? "text-emerald-400" : "text-red-400"}>{item.side}</span>
      <span className="text-amber-400">{formatAmount(item.size)}</span>
      <span className="text-white">@</span>
      <span className="text-amber-400">{formatAmount(item.price, 2)}</span>
    </div>
  )
}

/** Render a single OHLCV item */
function OhlcvLine({ item }: { item: OhlcvFeedItem }) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className="text-white/70">[{formatTime(item.timestamp)}]</span>
      <span className="text-white">{item.pair}</span>
      <span className="text-white">close:</span>
      <span className="text-amber-400">{formatAmount(item.close, 2)}</span>
    </div>
  )
}

/** Render a single funding item */
function FundingLine({ item }: { item: FundingFeedItem }) {
  const rate = parseFloat(item.rate)
  const isPositive = rate >= 0
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className="text-white/70">[{formatTime(item.timestamp)}]</span>
      <span className="text-white">{item.pair}</span>
      <span className="text-white">rate:</span>
      <span className={isPositive ? "text-emerald-400" : "text-red-400"}>
        {formatRate(item.rate)}
      </span>
    </div>
  )
}

/** Render a system message */
function SystemLine({ item }: { item: SystemFeedItem }) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className="text-white/70">[{formatTime(Date.now())}]</span>
      <span className="text-blue-400 italic">{item.message}</span>
    </div>
  )
}

/** Render item based on unified type */
function UnifiedFeedLine({ item }: { item: UnifiedFeedItem }) {
  switch (item.type) {
    case "ledger":
      return <LedgerLine item={item.data as LedgerFeedItem} />
    case "orders":
      return <OrderLine item={item.data as OrderFeedItem} />
    case "ohlcv":
      return <OhlcvLine item={item.data as OhlcvFeedItem} />
    case "funding":
      return <FundingLine item={item.data as FundingFeedItem} />
    case "system":
      return <SystemLine item={item.data as SystemFeedItem} />
  }
}

/**
 * LiveDataFeed component displays a unified scrolling log of data during sync.
 * Shows all feed types mixed chronologically in a single terminal-like console.
 */
export function LiveDataFeed({ items }: LiveDataFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new items arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [items])

  return (
    <div
      ref={containerRef}
      className={cn(
        "rounded-md bg-zinc-900/80 border border-zinc-800",
        "px-3 py-2 max-h-[180px] overflow-y-auto",
        "scroll-smooth"
      )}
    >
      {items.length === 0 ? (
        <div className="text-xs font-mono text-white/40 italic">
          Waiting for data...
        </div>
      ) : (
        <div className="space-y-0.5">
          {items.map((item) => (
            <div
              key={item.id}
              className="animate-in slide-in-from-bottom-1 duration-200"
            >
              <UnifiedFeedLine item={item} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default LiveDataFeed
