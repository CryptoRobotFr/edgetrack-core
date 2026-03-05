import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDate, formatUsd, formatPriceRaw, formatNumber } from "@/lib/formatters"
import type { TradeOrderItem } from "@/hooks/useTradeOrders"
import { Skeleton } from "@/components/ui/skeleton"

interface OrdersCardProps {
  orders: TradeOrderItem[]
  isLoading: boolean
  sizeDecimals: number
  base: string
}

// Format number without trailing zeros
function formatSize(value: number, decimals: number): string {
  const formatted = formatNumber(value, decimals)
  // Remove trailing zeros after decimal point
  if (formatted.includes(",") || formatted.includes(".")) {
    const sep = formatted.includes(",") ? "," : "."
    const [intPart, decPart] = formatted.split(sep)
    const trimmedDec = decPart.replace(/0+$/, "")
    return trimmedDec ? `${intPart}${sep}${trimmedDec}` : intPart
  }
  return formatted
}

function OrderItem({
  order,
  sizeDecimals,
  base,
}: {
  order: TradeOrderItem
  sizeDecimals: number
  base: string
}) {
  const isOpen = order.open_or_close === "open"
  return (
    <div className="border rounded-lg p-2 text-xs @2xl:text-sm">
      {/* Row 1 */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span>{formatDate(order.execution_date, { withTime: true })}</span>
          <span
            className={`px-1.5 py-0.5 rounded font-semibold ${
              isOpen
                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300"
            }`}
          >
            {order.open_or_close.toUpperCase()}
          </span>
        </div>
        <span className="font-semibold">
          {formatSize(order.size, sizeDecimals)} {base} ~ {formatUsd(order.size * order.price)}
        </span>
      </div>
      {/* Row 2 */}
      <div className="grid grid-cols-4 gap-2">
        <div>
          <span className="text-muted-foreground">Price</span>
          <br />
          {formatPriceRaw(order.price)}$
        </div>
        <div>
          <span className="text-muted-foreground">Type</span>
          <br />
          {order.order_type || "Market"}
        </div>
        <div>
          <span className="text-muted-foreground">Action</span>
          <br />
          <span className="capitalize">{order.action}</span>
        </div>
        <div>
          <span className="text-muted-foreground">Fee</span>
          <br />
          {formatUsd(order.fees)}
        </div>
      </div>
    </div>
  )
}

export function OrdersCard({ orders, isLoading, sizeDecimals, base }: OrdersCardProps) {
  if (isLoading) {
    return (
      <Card className="h-[300px]">
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm">Orders</CardTitle>
        </CardHeader>
        <CardContent className="h-[240px] p-2">
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-[300px]">
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm">Orders ({orders.length})</CardTitle>
      </CardHeader>
      <CardContent className="h-[240px] overflow-y-auto p-2 pt-0">
        <div className="space-y-2">
          {orders.map((order) => (
            <OrderItem key={order.id} order={order} sizeDecimals={sizeDecimals} base={base} />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
