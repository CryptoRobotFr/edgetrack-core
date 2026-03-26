import React, { createContext, useContext, useMemo, type ReactNode } from "react"
import { Outlet, useLocation } from "react-router-dom"
import { AppSidebar } from "@/components/app-sidebar"
import type { NavItem } from "@/components/nav-main"
import { AccountSelector } from "@/components/account-selector"
import { AccountProvider, useAccount } from "@/contexts/AccountContext"
import { MainContainerProvider, useMainContainerRef } from "@/contexts/MainContainerContext"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

import type { components } from "@/api/schema"

type Account = components["schemas"]["AccountResponse"]

// Breadcrumb segments for each route
const routeBreadcrumbs: Record<string, string[]> = {
  "/futures": ["Futures Trading"],
  "/futures/positions": ["Futures", "Positions"],
  "/futures/trades": ["Futures", "Trades"],
  "/futures/calendar": ["Futures", "Calendar"],
  "/futures/analysis": ["Futures", "Analysis"],
  "/futures/analysis/pnl": ["Futures", "Analysis", "P&L"],
  "/futures/analysis/equity": ["Futures", "Analysis", "Equity"],
  "/accounts": ["Accounts"],
  "/api-keys": ["API Keys"],
  "/billing": ["Billing"],
  "/admin": ["Administration"],
  "/admin/users": ["Administration", "Users"],
  "/admin/billing": ["Administration", "Billing"],
  "/admin/kols": ["Administration", "KOLs"],
  "/kol": ["Affiliate Dashboard"],
  "/settings": ["Settings"],
}

/** Context passed to factory functions so SaaS can compute values inside AccountProvider. */
export interface AccountInfo {
  isDemoSelected: boolean
  filteredAccounts: Account[]
}

type AccountSelectorProps = { disabledAccountIds?: string[]; disabledTooltip?: string }

interface LayoutOverrides {
  items?: NavItem[]
  ctaSlot?: ReactNode
  /** Static selector props (used when no factory is provided). */
  accountSelectorProps?: AccountSelectorProps
  /** Factory functions called inside AccountProvider to compute dynamic values. */
  sidebarItemsFactory?: (base: NavItem[], info: AccountInfo) => NavItem[]
  accountSelectorPropsFactory?: (info: AccountInfo) => AccountSelectorProps | undefined
}

const LayoutOverridesContext = createContext<LayoutOverrides>({})

function LayoutContent() {
  const location = useLocation()
  const breadcrumbs = routeBreadcrumbs[location.pathname] || ["Futures"]
  const mainContainerRef = useMainContainerRef()
  const overrides = useContext(LayoutOverridesContext)
  const { isDemoSelected, filteredAccounts } = useAccount()

  const accountInfo: AccountInfo = useMemo(
    () => ({ isDemoSelected, filteredAccounts }),
    [isDemoSelected, filteredAccounts],
  )

  // Compute sidebar items: use factory if provided, otherwise static items
  const sidebarItems = useMemo(() => {
    if (overrides.sidebarItemsFactory && overrides.items) {
      return overrides.sidebarItemsFactory(overrides.items, accountInfo)
    }
    return overrides.items
  }, [overrides.sidebarItemsFactory, overrides.items, accountInfo])

  // Compute selector props: use factory if provided, otherwise static props
  const selectorProps = useMemo(() => {
    if (overrides.accountSelectorPropsFactory) {
      return overrides.accountSelectorPropsFactory(accountInfo)
    }
    return overrides.accountSelectorProps
  }, [overrides.accountSelectorPropsFactory, overrides.accountSelectorProps, accountInfo])

  return (
    <>
      <AppSidebar items={sidebarItems} ctaSlot={overrides.ctaSlot} />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4 bg-sidebar text-sidebar-foreground">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              {breadcrumbs.map((segment, index) => (
                <React.Fragment key={segment}>
                  {index > 0 && <BreadcrumbSeparator />}
                  <BreadcrumbItem>
                    <BreadcrumbPage>{segment}</BreadcrumbPage>
                  </BreadcrumbItem>
                </React.Fragment>
              ))}
            </BreadcrumbList>
          </Breadcrumb>
          {/* Spacer to push account selector to the right */}
          <div className="ml-auto" />
          <AccountSelector {...(selectorProps ?? {})} />
        </header>
        <main
          id="main-content"
          ref={mainContainerRef as React.RefObject<HTMLElement>}
          className="flex-1 min-w-0 overflow-auto"
        >
          <div className="@container p-4 min-h-full">
            <Outlet />
          </div>
        </main>
      </SidebarInset>
    </>
  )
}

interface AuthenticatedLayoutProps {
  sidebarItems?: NavItem[]
  sidebarCtaSlot?: ReactNode
  accountSelectorProps?: AccountSelectorProps
  /** Called inside AccountProvider to adjust sidebar items based on account state. */
  sidebarItemsFactory?: (base: NavItem[], info: AccountInfo) => NavItem[]
  /** Called inside AccountProvider to compute account selector restrictions. */
  accountSelectorPropsFactory?: (info: AccountInfo) => AccountSelectorProps | undefined
}

export function AuthenticatedLayout({
  sidebarItems,
  sidebarCtaSlot,
  accountSelectorProps,
  sidebarItemsFactory,
  accountSelectorPropsFactory,
}: AuthenticatedLayoutProps = {}) {
  return (
    <SidebarProvider>
      <MainContainerProvider>
        <AccountProvider>
          <LayoutOverridesContext.Provider
            value={{
              items: sidebarItems,
              ctaSlot: sidebarCtaSlot,
              accountSelectorProps,
              sidebarItemsFactory,
              accountSelectorPropsFactory,
            }}
          >
            <LayoutContent />
          </LayoutOverridesContext.Provider>
        </AccountProvider>
      </MainContainerProvider>
    </SidebarProvider>
  )
}
