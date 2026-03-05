export type Theme = "light" | "dark"

// Trading colors — good contrast on both backgrounds
export const PROFIT_COLOR = "#59C0A4"
export const LOSS_COLOR = "#EC787E"

export function getChartTheme(theme: Theme) {
  const isDark = theme === "dark"

  return {
    // Tooltip styling
    tooltip: {
      backgroundColor: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255, 255, 255, 0.95)",
      borderColor: isDark ? "rgba(255, 255, 255, 0.1)" : "#e2e8f0",
      textStyle: { color: isDark ? "#e2e8f0" : "#334155", fontSize: 12 },
    },

    // Axis styling
    axis: {
      axisLabel: { color: isDark ? "#94a3b8" : "#64748b" },
      axisLine: { lineStyle: { color: isDark ? "#334155" : "#e2e8f0" } },
      splitLine: { lineStyle: { color: isDark ? "rgba(100, 116, 139, 0.15)" : "rgba(100, 116, 139, 0.15)" } },
    },

    // Text colors for inline HTML tooltips
    textColor: isDark ? "#e2e8f0" : "#334155",
    secondaryTextColor: isDark ? "#94a3b8" : "#64748b",

    // Grid border
    gridBorderColor: isDark ? "#334155" : "#e2e8f0",

    // Area gradient color stops for PnL curves
    areaGradient: {
      profit: {
        start: isDark ? "rgba(89, 192, 164, 0.4)" : "#59C0A4",
        end: isDark ? "rgba(89, 192, 164, 0.05)" : "#E9F7F3",
      },
      loss: {
        start: isDark ? "rgba(236, 120, 126, 0.05)" : "#FDF1F1",
        end: isDark ? "rgba(236, 120, 126, 0.4)" : "#EC787E",
      },
    },

    // Color at the zero-crossing point in mixed PnL gradients
    zeroCrossingColor: isDark ? "transparent" : "black",

    // Legend
    legendTextColor: isDark ? "#e2e8f0" : "#334155",

    // Drawdown-specific gradient (always negative)
    drawdownGradient: {
      start: isDark ? "rgba(236, 120, 126, 0.05)" : "#FDF1F1",
      end: isDark ? "rgba(236, 120, 126, 0.3)" : "#EC787E",
    },

    // Lightweight-charts (OHLCV)
    chartTextColor: isDark ? "#9ca3af" : "#64748b",
    chartBorderColor: isDark ? "#334155" : "#dbdbdb",
  }
}
