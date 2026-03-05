/**
 * Centralized formatting utilities for the EdgeTrack application.
 *
 * All formatting functions follow these conventions:
 * - Dates/times: UTC milliseconds as input (per API convention)
 * - Currency: USD with 2 decimal places by default
 * - Percentages: 0-100 scale (not 0-1)
 *
 * @see docs/frontend/formatters.md for usage guidelines
 */

// -----------------------------------------------------------------------------
// Locale Configuration
// -----------------------------------------------------------------------------

export type SupportedLocale = "en-US" | "fr-FR" | "de-DE"

/**
 * Module-level locale storage.
 * Set by UserContext when user data is loaded.
 * Falls back to "en-US" if not set.
 */
let currentLocale: SupportedLocale = "en-US"

/**
 * Set the current user locale. Called by UserContext when user data changes.
 * This allows formatters to work both inside and outside React components.
 */
export function setLocale(locale: SupportedLocale): void {
  currentLocale = locale
}

/**
 * Get the current user locale.
 * Returns the locale set by UserContext, or "en-US" as fallback.
 */
export function getLocale(): SupportedLocale {
  return currentLocale
}

/**
 * Get the current user locale for dates.
 */
export function getDateLocale(): string {
  return currentLocale
}

/**
 * Get the current user locale for numbers.
 */
export function getNumberLocale(): string {
  return currentLocale
}

/**
 * Locale display information for settings UI.
 */
export const LOCALE_OPTIONS: { value: SupportedLocale; label: string; example: string }[] = [
  { value: "en-US", label: "English (US)", example: "1,234.56" },
  { value: "fr-FR", label: "Francais (FR)", example: "1 234,56" },
  { value: "de-DE", label: "Deutsch (DE)", example: "1.234,56" },
]

// -----------------------------------------------------------------------------
// Currency Formatting
// -----------------------------------------------------------------------------

/**
 * Format a number as USD currency.
 * Automatically uses compact notation (K, M) for values >= 1000 to keep max 3 digits.
 *
 * @param value - Amount in USD
 * @param options - Formatting options
 * @returns Formatted string (e.g., "+1.46K$", "-567.89$")
 *
 * @example
 * formatUsd(999.99)                        // "999.99$"
 * formatUsd(1456.23)                       // "1.46K$"
 * formatUsd(-567.89)                       // "-567.89$"
 * formatUsd(1456.23, { showSign: true })   // "+1.46K$"
 * formatUsd(1234567)                       // "1.23M$"
 * formatUsd(1234.5, { withSuffix: false }) // "1.23K"
 */
export function formatUsd(
  value: number,
  options: {
    /** Show + sign for positive values */
    showSign?: boolean
    /** Number of decimal places (default: 2) */
    decimals?: number
    /** Add $ suffix (default: true) */
    withSuffix?: boolean
  } = {}
): string {
  const { showSign = false, decimals = 2, withSuffix = true } = options
  const suffix = withSuffix ? "$" : ""
  const locale = getNumberLocale()
  const absValue = Math.abs(value)

  let formatted: string

  if (absValue >= 1_000_000) {
    // Millions: 1.23M
    const millions = absValue / 1_000_000
    formatted = new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(millions) + "M"
  } else if (absValue >= 1_000) {
    // Thousands: 1.23K
    const thousands = absValue / 1_000
    formatted = new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(thousands) + "K"
  } else {
    // Under 1000: show full value
    formatted = new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(absValue)
  }

  if (value < 0) return `-${formatted}${suffix}`
  if (showSign && value > 0) return `+${formatted}${suffix}`
  return `${formatted}${suffix}`
}

// -----------------------------------------------------------------------------
// Percentage Formatting
// -----------------------------------------------------------------------------

/**
 * Format a percentage value.
 * Automatically uses compact notation (K, M) for values >= 1000% to keep max 3 digits.
 *
 * @param value - Percentage value (0-100 scale)
 * @param options - Formatting options
 * @returns Formatted string (e.g., "75.50%", "+12.50%", "1.23K%")
 *
 * @example
 * formatPercent(75.5)                     // "75.50%"
 * formatPercent(75.567, { decimals: 0 })  // "76%"
 * formatPercent(12.5, { showSign: true }) // "+12.50%"
 * formatPercent(1456.23)                  // "1.46K%"
 */
export function formatPercent(
  value: number,
  options: {
    /** Show + sign for positive values */
    showSign?: boolean
    /** Number of decimal places (default: 2) */
    decimals?: number
  } = {}
): string {
  const { showSign = false, decimals = 2 } = options
  const locale = getNumberLocale()
  const absValue = Math.abs(value)

  let formatted: string

  if (absValue >= 1_000_000) {
    // Millions: 1.23M%
    const millions = absValue / 1_000_000
    formatted = new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(millions) + "M"
  } else if (absValue >= 1_000) {
    // Thousands: 1.23K%
    const thousands = absValue / 1_000
    formatted = new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(thousands) + "K"
  } else {
    // Under 1000: show full value
    formatted = new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(absValue)
  }

  if (value < 0) return `-${formatted}%`
  if (showSign && value > 0) return `+${formatted}%`
  return `${formatted}%`
}

// -----------------------------------------------------------------------------
// Duration Formatting
// -----------------------------------------------------------------------------

/**
 * Format milliseconds to a human-readable duration string.
 *
 * @param ms - Duration in milliseconds
 * @returns Formatted string (e.g., "2h 30m", "1d 5h", "45m")
 *
 * @example
 * formatDuration(3600000)      // "1h"
 * formatDuration(5400000)      // "1h 30m"
 * formatDuration(90000000)     // "1d 1h"
 * formatDuration(0)            // "0m"
 */
export function formatDuration(ms: number): string {
  if (ms <= 0) return "0m"

  const minutes = Math.floor(ms / (1000 * 60))
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days > 0) {
    const remainingHours = hours % 24
    return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`
  }

  if (hours > 0) {
    const remainingMinutes = minutes % 60
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`
  }

  return `${minutes}m`
}

// -----------------------------------------------------------------------------
// Date/Time Formatting
// -----------------------------------------------------------------------------

/**
 * Format a UTC timestamp to a localized date string.
 *
 * @param timestampMs - UTC timestamp in milliseconds
 * @param options - Formatting options
 * @returns Formatted date string
 *
 * @example
 * formatDate(1705766400000)                    // "Jan 20, 2024"
 * formatDate(1705766400000, { full: true })    // "January 20, 2024"
 * formatDate(1705766400000, { withTime: true }) // "Jan 20, 2024, 12:00 PM"
 */
export function formatDate(
  timestampMs: number,
  options: {
    /** Use full month name */
    full?: boolean
    /** Include time */
    withTime?: boolean
  } = {}
): string {
  const { full = false, withTime = false } = options
  const date = new Date(timestampMs)

  const dateOptions: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: full ? "long" : "short",
    day: "numeric",
  }

  if (withTime) {
    dateOptions.hour = "numeric"
    dateOptions.minute = "2-digit"
  }

  return date.toLocaleDateString(getDateLocale(), dateOptions)
}

/**
 * Format a UTC timestamp to a compact date-time string.
 * Designed for space-constrained UIs like tooltips and tables.
 *
 * @param timestampMs - UTC timestamp in milliseconds
 * @returns Formatted date-time string (e.g., "Jan 20, 2024 14:30")
 *
 * @example
 * formatDateTime(1705766400000) // "Jan 20, 2024 14:30"
 */
export function formatDateTime(timestampMs: number): string {
  const date = new Date(timestampMs)
  const locale = getDateLocale()

  // Format date part
  const datePart = date.toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
    year: "numeric",
  })

  // Format time part (24h format for compactness)
  const timePart = date.toLocaleTimeString(locale, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })

  return `${datePart} ${timePart}`
}

/**
 * Format a UTC timestamp to a relative time string.
 *
 * @param timestampMs - UTC timestamp in milliseconds
 * @returns Relative time string (e.g., "2 hours ago", "in 3 days")
 *
 * @example
 * formatRelativeTime(Date.now() - 3600000)  // "1 hour ago"
 * formatRelativeTime(Date.now() - 86400000) // "1 day ago"
 */
export function formatRelativeTime(timestampMs: number): string {
  const now = Date.now()
  const diffMs = now - timestampMs
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) {
    return diffDays === 1 ? "1 day ago" : `${diffDays} days ago`
  }
  if (diffHours > 0) {
    return diffHours === 1 ? "1 hour ago" : `${diffHours} hours ago`
  }
  if (diffMinutes > 0) {
    return diffMinutes === 1 ? "1 minute ago" : `${diffMinutes} minutes ago`
  }
  return "just now"
}

// -----------------------------------------------------------------------------
// Number Formatting
// -----------------------------------------------------------------------------

/**
 * Format a number with thousand separators.
 *
 * @param value - Number to format
 * @param decimals - Number of decimal places (default: 0)
 * @returns Formatted string (e.g., "1,234", "1,234.56")
 *
 * @example
 * formatNumber(1234567)     // "1,234,567"
 * formatNumber(1234.567, 2) // "1,234.57"
 */
export function formatNumber(value: number, decimals = 0): string {
  return new Intl.NumberFormat(getNumberLocale(), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/**
 * Format a number in compact notation with 2 decimal places.
 *
 * @param value - Number to format
 * @returns Compact string (e.g., "1.23K", "3.46M", "5.67B")
 *
 * @example
 * formatCompact(1456)       // "1.46K"
 * formatCompact(1234567)    // "1.23M"
 * formatCompact(1234567890) // "1.23B"
 */
export function formatCompact(value: number): string {
  const locale = getNumberLocale()
  const absValue = Math.abs(value)

  if (absValue >= 1_000_000_000) {
    const billions = absValue / 1_000_000_000
    const formatted = new Intl.NumberFormat(locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(billions)
    return value < 0 ? `-${formatted}B` : `${formatted}B`
  } else if (absValue >= 1_000_000) {
    const millions = absValue / 1_000_000
    const formatted = new Intl.NumberFormat(locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(millions)
    return value < 0 ? `-${formatted}M` : `${formatted}M`
  } else if (absValue >= 1_000) {
    const thousands = absValue / 1_000
    const formatted = new Intl.NumberFormat(locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(thousands)
    return value < 0 ? `-${formatted}K` : `${formatted}K`
  }

  // Under 1000: show full value with 2 decimals
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

// -----------------------------------------------------------------------------
// Chart Formatting
// -----------------------------------------------------------------------------

/**
 * Format a UTC timestamp to a short date string for chart axes.
 * Uses MM/DD format for compact display on chart X-axes.
 *
 * @param timestampMs - UTC timestamp in milliseconds
 * @returns Formatted date string (e.g., "01/20" for en-US, "20/01" for fr-FR)
 *
 * @example
 * formatChartDate(1705766400000) // "01/20" (en-US) or "20/01" (fr-FR)
 */
export function formatChartDate(timestampMs: number): string {
  const date = new Date(timestampMs)
  const locale = getDateLocale()

  return date.toLocaleDateString(locale, {
    month: "2-digit",
    day: "2-digit",
  })
}

/**
 * Format a crypto price with appropriate decimal places.
 * Uses more decimals for small prices (< $1) and fewer for larger prices.
 *
 * @param value - Price value
 * @param options - Formatting options
 * @returns Formatted price string without currency symbol
 *
 * @example
 * formatPrice(0.00001234)  // "0.00001234"
 * formatPrice(1.2345)      // "1.2345"
 * formatPrice(1234.56)     // "1,234.56"
 * formatPrice(1234.56, { decimals: 4 }) // "1,234.5600"
 */
export function formatPrice(
  value: number,
  options: {
    /** Fixed number of decimal places (auto-detected if not provided) */
    decimals?: number
  } = {}
): string {
  const locale = getNumberLocale()

  // Auto-detect decimals based on value magnitude if not specified
  let decimals = options.decimals
  if (decimals === undefined) {
    if (value === 0) {
      decimals = 2
    } else if (Math.abs(value) < 0.0001) {
      decimals = 8
    } else if (Math.abs(value) < 0.01) {
      decimals = 6
    } else if (Math.abs(value) < 1) {
      decimals = 4
    } else {
      decimals = 2
    }
  }

  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/**
 * Format a price preserving its original decimal places from the API.
 * Use this when the backend has already formatted the price with the correct precision.
 *
 * @param value - Price value (already rounded by backend)
 * @returns Formatted price string with locale thousand separators, preserving original decimals
 *
 * @example
 * formatPriceRaw(1234.5)     // "1,234.5" (not "1,234.50")
 * formatPriceRaw(0.001)      // "0.001"
 * formatPriceRaw(42000)      // "42,000"
 * formatPriceRaw(42000.10)   // "42,000.1" (trailing zeros removed by JS)
 */
export function formatPriceRaw(value: number): string {
  const locale = getNumberLocale()

  // Count actual decimal places in the number
  const str = String(value)
  const decimalIndex = str.indexOf(".")
  const decimals = decimalIndex === -1 ? 0 : str.length - decimalIndex - 1

  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}
