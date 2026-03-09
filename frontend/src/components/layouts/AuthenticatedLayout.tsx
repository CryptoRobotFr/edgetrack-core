import React from "react"
import { Outlet, useLocation } from "react-router-dom"
import { AppSidebar } from "@/components/app-sidebar"
import { AccountSelector } from "@/components/account-selector"
import { AccountProvider } from "@/contexts/AccountContext"
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
  "/admin/billing": ["Administration", "Billing"],
  "/settings": ["Settings"],
}

function LayoutContent() {
  const location = useLocation()
  const breadcrumbs = routeBreadcrumbs[location.pathname] || ["Futures"]
  const mainContainerRef = useMainContainerRef()

  return (
    <>
      <AppSidebar />
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
          <AccountSelector />
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

export function AuthenticatedLayout() {
  return (
    <SidebarProvider>
      <MainContainerProvider>
        <AccountProvider>
          <LayoutContent />
        </AccountProvider>
      </MainContainerProvider>
    </SidebarProvider>
  )
}
