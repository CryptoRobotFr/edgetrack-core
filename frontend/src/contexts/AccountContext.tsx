import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from "react"
import { useLocation } from "react-router-dom"
import { authApi } from "@/api/client"
import type { components } from "@/api/schema"

type Account = components["schemas"]["AccountResponse"]
type AccountType = "spot" | "futures"

const STORAGE_KEY = "selectedAccountId"

/** Routes where the account selector should be visible */
const ROUTES_WITH_SELECTOR = ["/spot", "/futures"]

/** Routes that should hide the account selector */
const ROUTES_WITHOUT_SELECTOR = ["/accounts", "/settings"]

interface AccountContextType {
  /** All accounts from the API */
  accounts: Account[]
  /** Accounts filtered by current route (spot/futures) */
  filteredAccounts: Account[]
  /** Currently selected account ID */
  selectedAccountId: string | null
  /** Currently selected account object */
  selectedAccount: Account | null
  /** Set the selected account */
  setSelectedAccountId: (id: string | null) => void
  /** Whether accounts are currently loading */
  isLoading: boolean
  /** Error message if fetch failed */
  error: string | null
  /** Whether the selector should be visible on current route */
  showSelector: boolean
  /** Refresh accounts from API */
  refreshAccounts: () => Promise<void>
}

const AccountContext = createContext<AccountContextType | null>(null)

/**
 * Determine what account type filter to apply based on current route.
 * Returns null if no filtering should be applied.
 */
function getAccountTypeFilter(pathname: string): AccountType | null {
  if (pathname.startsWith("/futures")) return "futures"
  if (pathname.startsWith("/spot")) return "spot"
  return null
}

/**
 * Determine if the account selector should be visible on current route.
 */
function shouldShowSelector(pathname: string): boolean {
  // Explicitly hidden routes
  if (ROUTES_WITHOUT_SELECTOR.some((route) => pathname.startsWith(route))) {
    return false
  }
  // Show on routes that need account context
  return ROUTES_WITH_SELECTOR.some((route) => pathname.startsWith(route))
}

export function AccountProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedAccountId, setSelectedAccountIdState] = useState<string | null>(() => {
    // Initialize from localStorage
    return localStorage.getItem(STORAGE_KEY)
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Calculate derived state
  const accountTypeFilter = getAccountTypeFilter(location.pathname)
  const showSelector = shouldShowSelector(location.pathname)

  // Filter accounts based on current route
  const filteredAccounts = useMemo(() => {
    if (!accountTypeFilter) return accounts
    return accounts.filter((acc) => acc.account_type === accountTypeFilter)
  }, [accounts, accountTypeFilter])

  // Get the currently selected account object
  const selectedAccount = useMemo(() => {
    if (!selectedAccountId) return null
    return accounts.find((acc) => acc.id === selectedAccountId) ?? null
  }, [accounts, selectedAccountId])

  // Persist selection to localStorage
  const setSelectedAccountId = useCallback((id: string | null) => {
    setSelectedAccountIdState(id)
    if (id) {
      localStorage.setItem(STORAGE_KEY, id)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }, [])

  // Fetch accounts from API
  const fetchAccounts = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const { data, error: apiError } = await authApi.GET("/api/v1/accounts")
      if (apiError) {
        setError("Failed to load accounts")
        return
      }
      setAccounts(data ?? [])
    } catch {
      setError("Failed to load accounts")
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Fetch accounts on mount
  useEffect(() => {
    fetchAccounts()
  }, [fetchAccounts])

  // Auto-select account when:
  // 1. No account is selected
  // 2. Selected account is not in the filtered list
  // Also clear stale selection when no accounts exist
  useEffect(() => {
    if (isLoading) return

    // No accounts available — clear any stale selection
    if (filteredAccounts.length === 0) {
      if (selectedAccountId) {
        setSelectedAccountId(null)
      }
      return
    }

    const isSelectionValid =
      selectedAccountId && filteredAccounts.some((acc) => acc.id === selectedAccountId)

    if (!isSelectionValid) {
      // Auto-select the first account from filtered list
      setSelectedAccountId(filteredAccounts[0].id)
    }
  }, [filteredAccounts, selectedAccountId, isLoading, setSelectedAccountId])

  const value: AccountContextType = {
    accounts,
    filteredAccounts,
    selectedAccountId,
    selectedAccount,
    setSelectedAccountId,
    isLoading,
    error,
    showSelector,
    refreshAccounts: fetchAccounts,
  }

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>
}

export function useAccount() {
  const context = useContext(AccountContext)
  if (!context) {
    throw new Error("useAccount must be used within an AccountProvider")
  }
  return context
}
