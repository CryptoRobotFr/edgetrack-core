/**
 * Utility functions for chart calculations.
 */

/**
 * Clamp a value between min and max bounds.
 *
 * @param value - The value to clamp
 * @param min - Minimum bound
 * @param max - Maximum bound
 * @returns The clamped value
 *
 * @example
 * clamp(1.5, 0, 1)  // 1
 * clamp(-0.5, 0, 1) // 0
 * clamp(0.5, 0, 1)  // 0.5
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}
