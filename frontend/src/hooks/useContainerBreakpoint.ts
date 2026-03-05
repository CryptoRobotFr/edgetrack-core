import { useState, useEffect, useRef, useCallback } from "react"

// Tailwind default breakpoints
const BREAKPOINTS = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  "2xl": 1536,
} as const

type Breakpoint = keyof typeof BREAKPOINTS

interface ContainerBreakpointResult {
  width: number
  /** Container width >= 640px */
  isSm: boolean
  /** Container width >= 768px */
  isMd: boolean
  /** Container width >= 1024px */
  isLg: boolean
  /** Container width >= 1280px */
  isXl: boolean
  /** Container width >= 1536px */
  is2Xl: boolean
  /** Check if container width >= given breakpoint */
  isAbove: (breakpoint: Breakpoint) => boolean
  /** Check if container width < given breakpoint */
  isBelow: (breakpoint: Breakpoint) => boolean
}

/**
 * Hook to get container-based breakpoints using ResizeObserver.
 *
 * Usage with ref:
 * ```tsx
 * const containerRef = useRef<HTMLDivElement>(null)
 * const { isMd, isLg } = useContainerBreakpoint({ ref: containerRef })
 * ```
 *
 * Usage with selector (for main layout container):
 * ```tsx
 * const { isMd, isLg } = useContainerBreakpoint({ selector: "#main-content" })
 * ```
 */
export function useContainerBreakpoint(options: {
  ref?: React.RefObject<HTMLElement | null>
  selector?: string
}): ContainerBreakpointResult {
  const { ref, selector } = options
  const [width, setWidth] = useState(0)
  const observerRef = useRef<ResizeObserver | null>(null)

  useEffect(() => {
    // Get the target element
    let element: HTMLElement | null = null

    if (ref?.current) {
      element = ref.current
    } else if (selector) {
      element = document.querySelector(selector)
    }

    if (!element) {
      return
    }

    // Set initial width
    setWidth(element.clientWidth)

    // Create ResizeObserver
    observerRef.current = new ResizeObserver((entries) => {
      for (const entry of entries) {
        // Use contentBoxSize for accurate width without padding
        if (entry.contentBoxSize) {
          const boxSize = Array.isArray(entry.contentBoxSize)
            ? entry.contentBoxSize[0]
            : entry.contentBoxSize
          setWidth(boxSize.inlineSize)
        } else {
          // Fallback for older browsers
          setWidth(entry.contentRect.width)
        }
      }
    })

    observerRef.current.observe(element)

    return () => {
      observerRef.current?.disconnect()
    }
  }, [ref, selector])

  const isAbove = useCallback(
    (breakpoint: Breakpoint) => width >= BREAKPOINTS[breakpoint],
    [width]
  )

  const isBelow = useCallback(
    (breakpoint: Breakpoint) => width < BREAKPOINTS[breakpoint],
    [width]
  )

  return {
    width,
    isSm: width >= BREAKPOINTS.sm,
    isMd: width >= BREAKPOINTS.md,
    isLg: width >= BREAKPOINTS.lg,
    isXl: width >= BREAKPOINTS.xl,
    is2Xl: width >= BREAKPOINTS["2xl"],
    isAbove,
    isBelow,
  }
}

/**
 * Convenience hook that uses the main layout container (#main-content).
 * Use this in components rendered inside AuthenticatedLayout.
 *
 * ```tsx
 * const { isMd, isLg } = useMainContainerBreakpoint()
 * ```
 */
export function useMainContainerBreakpoint(): ContainerBreakpointResult {
  return useContainerBreakpoint({ selector: "#main-content" })
}
