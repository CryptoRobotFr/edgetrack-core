import { createContext, useContext, useRef, type ReactNode, type RefObject } from "react"

interface MainContainerContextType {
  containerRef: RefObject<HTMLElement | null>
}

const MainContainerContext = createContext<MainContainerContextType | null>(null)

export function MainContainerProvider({ children }: { children: ReactNode }) {
  const containerRef = useRef<HTMLElement | null>(null)

  return (
    <MainContainerContext.Provider value={{ containerRef }}>
      {children}
    </MainContainerContext.Provider>
  )
}

/**
 * Get the main container ref for positioning portaled elements (tooltips, popovers).
 * Returns null if used outside MainContainerProvider.
 */
export function useMainContainer(): HTMLElement | null {
  const context = useContext(MainContainerContext)
  return context?.containerRef.current ?? null
}

/**
 * Get the raw ref object for attaching to the main container element.
 * Only used by AuthenticatedLayout.
 */
export function useMainContainerRef(): RefObject<HTMLElement | null> | null {
  const context = useContext(MainContainerContext)
  return context?.containerRef ?? null
}
