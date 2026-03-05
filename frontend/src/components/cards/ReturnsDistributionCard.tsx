import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { BarChart, HelpCircle } from "lucide-react"
import { ReturnsHistogram } from "@/components/charts/ReturnsHistogram"
import type { DailyReturn } from "@/hooks/useFuturesEquityAnalysis"

interface ReturnsDistributionCardProps {
  dailyReturns: DailyReturn[]
}

const MAX_BUCKETS = 50

function buildHistogramData(dailyReturns: DailyReturn[]) {
  if (dailyReturns.length === 0) {
    return { buckets: [], counts: [] }
  }

  // Filter out non-finite values and 0% returns (flat days are noise)
  const returns = dailyReturns
    .map((d) => d.return_pct)
    .filter((r) => Number.isFinite(r) && r !== 0)

  if (returns.length === 0) {
    return { buckets: [], counts: [] }
  }

  const minReturn = Math.min(...returns)
  const maxReturn = Math.max(...returns)

  // All values are the same — single bucket
  const range = maxReturn - minReturn
  if (range === 0) {
    const label = `${minReturn.toFixed(1)}%`
    return {
      buckets: [label],
      counts: [{ value: returns.length, itemStyle: { color: minReturn < 0 ? "#EC787E" : "#59C0A4" } }],
    }
  }

  // Determine bucket size (aim for ~10-20 buckets)
  let bucketSize: number
  if (range <= 2) bucketSize = 0.25
  else if (range <= 5) bucketSize = 0.5
  else if (range <= 20) bucketSize = 1
  else if (range <= 50) bucketSize = 2.5
  else bucketSize = 5

  // Create buckets with a safety cap
  const bucketStart = Math.floor(minReturn / bucketSize) * bucketSize
  const bucketEnd = Math.ceil(maxReturn / bucketSize) * bucketSize

  const buckets: string[] = []
  const countMap: number[] = []

  for (let b = bucketStart; b < bucketEnd && buckets.length < MAX_BUCKETS; b += bucketSize) {
    const lo = b
    const hi = b + bucketSize
    const label = `${lo.toFixed(1)}% to ${hi.toFixed(1)}%`
    buckets.push(label)
    const count = returns.filter(
      (r) => r >= lo && r < hi
    ).length
    countMap.push(count)
  }

  // Assign colors: red for fully negative, green for fully positive, gray for mixed
  const counts = buckets.map((_, i) => {
    const lo = bucketStart + i * bucketSize
    return {
      value: countMap[i],
      itemStyle: {
        color: lo + bucketSize <= 0 ? "#EC787E" : lo >= 0 ? "#59C0A4" : "#A3A3A3",
      },
    }
  })

  return { buckets, counts }
}

export function ReturnsDistributionCard({ dailyReturns }: ReturnsDistributionCardProps) {
  if (dailyReturns.length === 0) {
    return (
      <Card className="px-2 h-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
          <div className="flex flex-row gap-x-2 items-center">
            <CardTitle className="text-lg font-semibold text-muted-foreground">
              Returns Distribution
            </CardTitle>
          </div>
          <BarChart className="w-3.5 h-3.5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="pt-0 h-[300px] flex items-center justify-center">
          <p className="text-muted-foreground text-sm">No data available</p>
        </CardContent>
      </Card>
    )
  }

  const nonZeroReturns = dailyReturns.filter((d) => d.return_pct !== 0)
  const histogramData = buildHistogramData(nonZeroReturns)

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-1">
        <div className="flex flex-row gap-x-2 items-center">
          <CardTitle className="text-lg font-semibold text-muted-foreground">
            Returns Distribution
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-3.5 h-3.5 cursor-pointer text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Frequency distribution of daily returns (excluding 0% days)</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <BarChart className="w-3.5 h-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="h-[300px] p-4">
        <ReturnsHistogram data={histogramData} totalDays={nonZeroReturns.length} />
      </CardContent>
    </Card>
  )
}
