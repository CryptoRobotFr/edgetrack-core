import { useEffect, useRef } from "react"
import * as echarts from "echarts"

type EChartEventHandler = (...args: unknown[]) => void

interface EChartProps {
  option: Record<string, unknown>
  style?: React.CSSProperties
  onEvents?: Record<string, EChartEventHandler>
  notMerge?: boolean
  renderer?: "canvas" | "svg"
}

/**
 * Lightweight echarts wrapper using hooks.
 * Avoids the size-sensor "disconnect" bug in echarts-for-react
 * that triggers errors during React StrictMode double-mount.
 */
export function EChart({ option, style, onEvents, notMerge, renderer }: EChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = echarts.init(containerRef.current, undefined, renderer ? { renderer } : undefined)
    chartRef.current = chart
    chart.setOption(option)

    const observer = new ResizeObserver(() => {
      chart.resize()
    })
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, notMerge ?? true)
  }, [option, notMerge])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !onEvents) return

    const entries = Object.entries(onEvents)
    for (const [event, handler] of entries) {
      chart.on(event, handler)
    }
    return () => {
      if (chart.isDisposed()) return
      for (const [event, handler] of entries) {
        chart.off(event, handler)
      }
    }
  }, [onEvents])

  return <div ref={containerRef} style={style} />
}
