import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { List } from "lucide-react"
import { DataTable } from "@/components/trades/data-table"
import { columns } from "@/components/trades/columns"
import type { components } from "@/api/schema"

type TradeAnalysis = components["schemas"]["TradeAnalysis"]

interface TradesTableCardProps {
  trades: TradeAnalysis[]
}

export function TradesTableCard({ trades }: TradesTableCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-2">
        <CardTitle className="text-lg font-semibold text-muted-foreground">
          Recent Trades
        </CardTitle>
        <List className="w-4 h-4 text-muted-foreground" />
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <DataTable columns={columns} data={trades} />
      </CardContent>
    </Card>
  )
}
