import * as React from "react"
import * as VisuallyHidden from "@radix-ui/react-visually-hidden"

import { useMainContainerBreakpoint } from "@/hooks/useContainerBreakpoint"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer"

interface ResponsiveDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
  title?: React.ReactNode
  description?: React.ReactNode
  /** Screen reader only title when no visible title is provided */
  ariaTitle?: string
}

/**
 * A responsive dialog component that renders as a Dialog on desktop (>=1024px)
 * and as a Drawer on mobile (<1024px).
 *
 * Uses container queries via useMainContainerBreakpoint() to determine the
 * breakpoint based on the main content area width, not the viewport.
 */
export function ResponsiveDialog({
  open,
  onOpenChange,
  children,
  title,
  description,
  ariaTitle = "Dialog",
}: ResponsiveDialogProps) {
  const { isLg } = useMainContainerBreakpoint()

  if (isLg) {
    // Desktop: Render as Dialog
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className="max-w-[95vw] max-h-[98vh] overflow-hidden flex flex-col"
          aria-describedby={description ? undefined : undefined}
        >
          {title ? (
            <DialogHeader>
              <DialogTitle>{title}</DialogTitle>
              {description && <DialogDescription>{description}</DialogDescription>}
            </DialogHeader>
          ) : (
            <VisuallyHidden.Root asChild>
              <DialogTitle>{ariaTitle}</DialogTitle>
            </VisuallyHidden.Root>
          )}
          <div className="@container flex-1 overflow-auto">{children}</div>
        </DialogContent>
      </Dialog>
    )
  }

  // Mobile: Render as Drawer
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="max-h-[90vh]">
        {title ? (
          <DrawerHeader>
            <DrawerTitle>{title}</DrawerTitle>
            {description && <DrawerDescription>{description}</DrawerDescription>}
          </DrawerHeader>
        ) : (
          <VisuallyHidden.Root asChild>
            <DrawerTitle>{ariaTitle}</DrawerTitle>
          </VisuallyHidden.Root>
        )}
        <div className="@container flex-1 overflow-auto px-4 pb-4">{children}</div>
      </DrawerContent>
    </Drawer>
  )
}
