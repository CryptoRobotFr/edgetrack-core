import * as React from "react"
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


const navItems: NavItem[] = [
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

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
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
        <NavMain items={navItems} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
