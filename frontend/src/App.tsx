import { Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthProvider } from "@/contexts/AuthContext"
import { ThemeProvider } from "@/contexts/ThemeContext"
import { UserProvider } from "@/contexts/UserContext"
import { AccountProvider } from "@/contexts/AccountContext"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { AuthenticatedLayout } from "@/components/layouts/AuthenticatedLayout"
import SignupPage from "@/pages/auth/SignupPage"
import LoginPage from "@/pages/auth/LoginPage"
import LogoutPage from "@/pages/auth/LogoutPage"
import SyncPage from "@/pages/accounts/SyncPage"
import { RootRedirect } from "@/components/RootRedirect"
import AnalysisPage from "@/pages/futures/AnalysisPage"
import PnlTab from "@/pages/futures/analysis/PnlTab"
import EquityTab from "@/pages/futures/analysis/EquityTab"
import CalendarPage from "@/pages/futures/CalendarPage"
import TradesPage from "@/pages/futures/TradesPage"
import TradeDetailDialog from "@/pages/futures/trades/TradeDetailDialog"
import PositionsPage from "@/pages/futures/PositionsPage"
import FuturesLayout from "@/pages/futures/FuturesLayout"
import SettingsPage from "@/pages/settings/SettingsPage"
import AccountsPage from "@/pages/accounts/AccountsPage"
import ApiKeysPage from "@/pages/api-keys/ApiKeysPage"
import AdminPage from "@/pages/admin/AdminPage"
import NotFoundPage from "@/pages/NotFoundPage"
import { Toaster } from "sonner"

const queryClient = new QueryClient()

function App() {
  return (
    <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <UserProvider>
          <Routes>
        {/* Public routes */}
        <Route path="/" element={<RootRedirect />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/logout" element={<LogoutPage />} />

        {/* Protected fullscreen routes (no sidebar) */}
        <Route
          path="/accounts/:accountId/sync"
          element={
            <ProtectedRoute>
              <AccountProvider>
                <SyncPage />
              </AccountProvider>
            </ProtectedRoute>
          }
        />

        {/* Protected routes with sidebar layout */}
        <Route
          element={
            <ProtectedRoute>
              <AuthenticatedLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<Navigate to="/futures/positions" replace />} />
          {/* Spot routes */}
          <Route path="/spot/portfolio" element={<PlaceholderPage title="Spot Portfolio" />} />
          <Route path="/spot/analysis" element={<PlaceholderPage title="Spot Analysis" />} />
          <Route path="/spot/calendar" element={<PlaceholderPage title="Spot Calendar" />} />
          <Route path="/spot/trades" element={<PlaceholderPage title="Spot Trades" />} />
          {/* Futures routes - wrapped in FuturesLayout for auto-sync */}
          <Route path="/futures" element={<FuturesLayout />}>
            <Route path="positions" element={<PositionsPage />}>
              <Route path=":tradeId" element={<TradeDetailDialog />} />
            </Route>
            <Route path="analysis" element={<AnalysisPage />}>
              <Route index element={<Navigate to="/futures/analysis/pnl" replace />} />
              <Route path="pnl" element={<PnlTab />} />
              <Route path="equity" element={<EquityTab />} />
            </Route>
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="trades" element={<TradesPage />}>
              <Route path=":tradeId" element={<TradeDetailDialog />} />
            </Route>
          </Route>
          {/* Other routes */}
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/api-keys" element={<ApiKeysPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
          </Routes>
          <Toaster richColors position="bottom-right" />
        </UserProvider>
      </AuthProvider>
    </QueryClientProvider>
    </ThemeProvider>
  )
}

// Temporary placeholder for routes not yet implemented
function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <h1 className="text-2xl font-bold text-foreground">{title}</h1>
      <p className="mt-2 text-muted-foreground">Coming soon...</p>
    </div>
  )
}

export default App
