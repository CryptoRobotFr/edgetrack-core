import * as React from "react"
import { useMemo } from "react"
import {
  TrendingUp,
  LineChart,
  Key,
  Briefcase,
  BarChart3,
  Calendar,
  List,
} from "lucide-react"

import { NavMain, type NavItem } from "@/components/nav-main"
import { NavUser } from "@/components/nav-user"
import { useAccount } from "@/contexts/AccountContext"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"


export const navItems: NavItem[] = [
  {
    title: "Spot",
    url: "#",
    icon: TrendingUp,
    disabled: true,
    items: [
      { title: "Portfolio", url: "/spot/portfolio", icon: Briefcase },
      { title: "Analysis", url: "/spot/analysis", icon: BarChart3 },
      { title: "Calendar", url: "/spot/calendar", icon: Calendar },
      { title: "Trades", url: "/spot/trades", icon: List },
    ],
  },
  {
    title: "Futures",
    url: "#",
    icon: LineChart,
    items: [
      { title: "Positions", url: "/futures/positions", icon: Briefcase },
      { title: "Analysis", url: "/futures/analysis", icon: BarChart3 },
      { title: "Calendar", url: "/futures/calendar", icon: Calendar },
      { title: "Trades", url: "/futures/trades", icon: List },
    ],
  },
  {
    title: "Accounts",
    url: "/accounts",
    icon: Key,
  },
]

/** Lock all non-disabled sub-items in sections that match the given titles. */
function applyNoAccountLocks(items: NavItem[]): NavItem[] {
  return items.map((item) => {
    // Only lock Futures sub-items (Spot is already disabled)
    if (!item.items || item.disabled || item.title !== "Futures") return item

    return {
      ...item,
      items: item.items.map((sub) => {
        // Don't double-lock items already locked (e.g. premium lock)
        if (sub.locked) return sub
        return {
          ...sub,
          locked: true,
          lockedTooltip: `Add an account to access ${sub.title}`,
        }
      }),
    }
  })
}

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
  /** Override the default nav items */
  items?: NavItem[]
  /** Slot rendered between SidebarContent and SidebarFooter */
  ctaSlot?: React.ReactNode
}

export function AppSidebar({ items, ctaSlot, ...props }: AppSidebarProps) {
  const { accounts, isLoading } = useAccount()
  const hasNoAccounts = !isLoading && accounts.length === 0

  const finalItems = useMemo(() => {
    const base = items ?? navItems
    if (hasNoAccounts) return applyNoAccountLocks(base)
    return base
  }, [items, hasNoAccounts])

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" className="cursor-default hover:bg-transparent active:bg-transparent">
                <img
                  src="/logo.svg"
                  alt="EdgeTrack"
                  className="size-8 rounded-lg"
                />
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">EdgeTrack</span>
                  <span className="truncate text-xs text-muted-foreground">Trading Analysis</span>
                </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={finalItems} />
      </SidebarContent>
      {ctaSlot}
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
