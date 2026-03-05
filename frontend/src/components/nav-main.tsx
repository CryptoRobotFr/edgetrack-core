import { ChevronDown, ChevronUp, Construction, type LucideIcon } from "lucide-react"
import { Link, useLocation } from "react-router-dom"
import * as React from "react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export type NavItem = {
  title: string
  url: string
  icon?: LucideIcon
  isActive?: boolean
  /** When true, the section is shown but non-clickable with a construction icon */
  disabled?: boolean
  items?: {
    title: string
    url: string
    icon?: LucideIcon
  }[]
}

// Check if the current path matches or starts with the given URL
function isRouteActive(pathname: string, url: string): boolean {
  if (url === "#") return false
  // Exact match or nested route match (e.g., /futures/analysis/pnl matches /futures/analysis)
  return pathname === url || pathname.startsWith(url + "/")
}

export function NavMain({ items }: { items: NavItem[] }) {
  const location = useLocation()
  const { state: sidebarState } = useSidebar()
  const isIconOnly = sidebarState === "collapsed"

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Navigation</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) =>
          item.disabled ? (
            <DisabledSection key={item.title} item={item} isIconOnly={isIconOnly} />
          ) : item.items ? (
            <NavSection
              key={item.title}
              item={item}
              location={location}
              isIconOnly={isIconOnly}
            />
          ) : (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                asChild
                tooltip={item.title}
                isActive={isRouteActive(location.pathname, item.url)}
              >
                <Link to={item.url}>
                  {item.icon && <item.icon />}
                  <span>{item.title}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )
        )}
      </SidebarMenu>
    </SidebarGroup>
  )
}

function DisabledSection({
  item,
  isIconOnly,
}: {
  item: NavItem
  isIconOnly: boolean
}) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        tooltip={`${item.title} — Coming soon`}
        className="cursor-default opacity-50 hover:bg-transparent hover:text-sidebar-foreground"
      >
        {item.icon && <item.icon />}
        {!isIconOnly && (
          <>
            <span>{item.title}</span>
            <Construction className="ml-auto h-4 w-4" />
          </>
        )}
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

function NavSection({
  item,
  location,
  isIconOnly,
}: {
  item: NavItem
  location: ReturnType<typeof useLocation>
  isIconOnly: boolean
}) {
  const [isOpen, setIsOpen] = React.useState(true)

  // In icon-only mode, show a chevron toggle + sub-items as icons
  if (isIconOnly) {
    return (
      <>
        {/* Section toggle (icon-only mode) */}
        <SidebarMenuItem>
          <SidebarMenuButton
            tooltip={item.title}
            onClick={() => setIsOpen(!isOpen)}
          >
            {isOpen ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </SidebarMenuButton>
        </SidebarMenuItem>

        {/* Sub-items (only visible when open) */}
        {isOpen &&
          item.items?.map((subItem) => (
            <SidebarMenuItem key={subItem.title}>
              <SidebarMenuButton
                asChild
                tooltip={subItem.title}
                isActive={isRouteActive(location.pathname, subItem.url)}
              >
                <Link to={subItem.url}>
                  {subItem.icon && <subItem.icon />}
                  <span>{subItem.title}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
      </>
    )
  }

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className="group/collapsible"
    >
      {/* Section toggle header */}
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton tooltip={item.title}>
            {item.icon && <item.icon />}
            <span>{item.title}</span>
            {isOpen ? (
              <ChevronUp className="ml-auto h-4 w-4 transition-transform duration-200" />
            ) : (
              <ChevronDown className="ml-auto h-4 w-4 transition-transform duration-200" />
            )}
          </SidebarMenuButton>
        </CollapsibleTrigger>
      </SidebarMenuItem>

      {/* Sub-items rendered flat (same level as other menu items) */}
      <CollapsibleContent>
        {item.items?.map((subItem) => (
          <SidebarMenuItem key={subItem.title}>
            <SidebarMenuButton
              asChild
              tooltip={subItem.title}
              isActive={isRouteActive(location.pathname, subItem.url)}
              className="pl-8"
            >
              <Link to={subItem.url}>
                {subItem.icon && <subItem.icon />}
                <span>{subItem.title}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
      </CollapsibleContent>
    </Collapsible>
  )
}
