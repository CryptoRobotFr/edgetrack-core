import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import {
  Check,
  Loader2,
  Circle,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  ArrowLeft,
  ChevronRight,
  MonitorSmartphone,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  useSyncStream,
  type SyncEventType,
  type SyncState,
} from "@/hooks/useSyncStream"
import { LiveDataFeed } from "./components/LiveDataFeed"
import { useAccount } from "@/contexts/AccountContext"

/** Phase configuration */
interface Phase {
  id: string
  label: string
  steps: SyncEventType[]
}

const PHASES: Phase[] = [
  {
    id: "init",
    label: "Initialization",
    steps: ["started", "validating"],
  },
  {
    id: "account",
    label: "Account Data",
    steps: ["equity_fetching", "equity_calculated", "positions_fetched"],
  },
  {
    id: "orders",
    label: "Order History",
    steps: ["orders_progress", "orders_fetched"],
  },
  {
    id: "trades",
    label: "Trade Building",
    steps: ["grouping", "trades_built"],
  },
  {
    id: "market",
    label: "Market Data",
    steps: ["ohlcv_fetching", "ohlcv_fetched", "funding_fetching", "funding_fetched"],
  },
  {
    id: "analytics",
    label: "Analytics",
    steps: ["daily_pnl_calculating", "daily_pnl_calculated"],
  },
  {
    id: "finalize",
    label: "Finalization",
    steps: ["saving", "completed"],
  },
]

/** All steps in order for progress calculation */
const ALL_STEPS: SyncEventType[] = PHASES.flatMap((p) => p.steps)

/**
 * Map granular progress events to their parent phase events.
 * Granular events are emitted during streaming but are not in ALL_STEPS,
 * so we map them to the corresponding phase event for progress calculation.
 */
const GRANULAR_EVENT_TO_PARENT: Partial<Record<SyncEventType, SyncEventType>> = {
  ledger_progress: "equity_fetching",
  orders_item_progress: "orders_progress",
  ohlcv_progress: "ohlcv_fetching",
  funding_progress: "funding_fetching",
}

/** Get the effective step for progress calculation (maps granular events to parents) */
function getEffectiveStep(step: SyncEventType | null): SyncEventType | null {
  if (!step) return null
  return GRANULAR_EVENT_TO_PARENT[step] ?? step
}

/** Step labels */
const STEP_LABELS: Record<SyncEventType, string> = {
  started: "Starting sync",
  validating: "Validating credentials",
  equity_fetching: "Fetching equity history",
  equity_calculated: "Equity calculated",
  positions_fetched: "Positions fetched",
  orders_progress: "Fetching orders",
  orders_fetched: "Orders fetched",
  grouping: "Grouping orders",
  trades_built: "Trades built",
  ohlcv_fetching: "Fetching OHLCV data",
  ohlcv_fetched: "OHLCV data fetched",
  funding_fetching: "Fetching funding rates",
  funding_fetched: "Funding rates fetched",
  daily_pnl_calculating: "Calculating daily PnL",
  daily_pnl_calculated: "Daily PnL calculated",
  saving: "Saving to database",
  completed: "Completed",
  error: "Error",
  heartbeat: "Heartbeat",
  // Live feed progress events (not shown as steps, just for labeling)
  ledger_progress: "Streaming ledger data",
  orders_item_progress: "Streaming orders",
  ohlcv_progress: "Streaming OHLCV data",
  funding_progress: "Streaming funding rates",
}

/** Get phase status */
function getPhaseStatus(
  phase: Phase,
  currentStep: SyncEventType | null,
  isCompleted: boolean,
  isError: boolean
): "pending" | "active" | "completed" {
  if (isCompleted) return "completed"
  if (!currentStep) return "pending"

  // Map granular events to their parent phase events
  const effectiveStep = getEffectiveStep(currentStep)
  const currentStepIndex = ALL_STEPS.indexOf(effectiveStep!)
  const phaseFirstStepIndex = ALL_STEPS.indexOf(phase.steps[0])
  const phaseLastStepIndex = ALL_STEPS.indexOf(phase.steps[phase.steps.length - 1])

  if (currentStepIndex > phaseLastStepIndex) return "completed"
  if (currentStepIndex >= phaseFirstStepIndex && currentStepIndex <= phaseLastStepIndex) {
    return isError ? "pending" : "active"
  }
  return "pending"
}

/** Get step status */
function getStepStatus(
  step: SyncEventType,
  currentStep: SyncEventType | null,
  isCompleted: boolean
): "pending" | "active" | "completed" {
  if (isCompleted) return "completed"
  if (!currentStep) return "pending"

  const stepIndex = ALL_STEPS.indexOf(step)

  // Map ALL granular events to their parent step (not just orders_progress)
  const effectiveCurrentStep = getEffectiveStep(currentStep) ?? currentStep
  const effectiveIndex = ALL_STEPS.indexOf(effectiveCurrentStep)

  if (stepIndex < effectiveIndex) return "completed"
  if (stepIndex === effectiveIndex) return "active"
  return "pending"
}

/** Calculate progress percentage */
function calculateProgress(currentStep: SyncEventType | null, isCompleted: boolean): number {
  if (isCompleted) return 100
  if (!currentStep) return 0

  // Map granular events to their parent phase events first
  const mappedStep = getEffectiveStep(currentStep)
  const effectiveStep = mappedStep === "orders_progress" ? "orders_fetched" : mappedStep
  const index = ALL_STEPS.indexOf(effectiveStep!)
  if (index === -1) return 0

  return Math.round(((index + 1) / ALL_STEPS.length) * 100)
}

/** Get counter value for a step */
function getStepCounter(step: SyncEventType, state: SyncState): string | undefined {
  switch (step) {
    case "positions_fetched":
      return state.positionsCount > 0 ? `${state.positionsCount}` : undefined
    case "orders_fetched":
      return state.ordersFetched > 0 ? `${state.ordersFetched}` : undefined
    case "trades_built":
      return state.tradesCount > 0 ? `${state.tradesCount}` : undefined
    case "ohlcv_fetched":
      return state.candlesFetched > 0 ? `${state.candlesFetched}` : undefined
    case "funding_fetched":
      return state.fundingRatesFetched > 0 ? `${state.fundingRatesFetched}` : undefined
    case "daily_pnl_calculated":
      return state.dailyPnlRecords > 0 ? `${state.dailyPnlRecords}` : undefined
    case "equity_calculated":
      return state.equityRecords > 0 ? `${state.equityRecords}` : undefined
    default:
      return undefined
  }
}

/** Single step indicator */
function StepIndicator({
  step,
  status,
  counter,
  isLast,
}: {
  step: SyncEventType
  status: "pending" | "active" | "completed"
  counter?: string
  isLast: boolean
}) {
  return (
    <div className="flex items-start gap-3 ml-6">
      {/* Connector line + circle */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex h-5 w-5 items-center justify-center rounded-full border transition-colors",
            status === "completed" && "border-emerald-600 bg-emerald-600",
            status === "active" && "border-primary bg-primary",
            status === "pending" && "border-muted-foreground/30 bg-transparent"
          )}
        >
          {status === "completed" && <Check className="h-3 w-3 text-white" />}
          {status === "active" && <Loader2 className="h-3 w-3 text-white animate-spin" />}
          {status === "pending" && <Circle className="h-2 w-2 text-muted-foreground/30" />}
        </div>
        {!isLast && (
          <div
            className={cn(
              "w-px h-5 mt-1",
              status === "completed" ? "bg-emerald-600/50" : "bg-border"
            )}
          />
        )}
      </div>

      {/* Step label */}
      <div className="flex items-center gap-2 pb-3">
        <span
          className={cn(
            "text-sm",
            status === "completed" && "text-emerald-600",
            status === "active" && "text-foreground font-medium",
            status === "pending" && "text-muted-foreground/50"
          )}
        >
          {STEP_LABELS[step]}
        </span>
        {counter && status !== "pending" && (
          <span
            className={cn(
              "text-xs font-mono px-1.5 py-0.5 rounded",
              status === "completed"
                ? "bg-emerald-600/10 text-emerald-600"
                : "bg-primary/10 text-primary"
            )}
          >
            {counter}
          </span>
        )}
      </div>
    </div>
  )
}

/** Phase component */
function PhaseItem({
  phase,
  status,
  currentStep,
  state,
  isLast,
}: {
  phase: Phase
  status: "pending" | "active" | "completed"
  currentStep: SyncEventType | null
  state: SyncState
  isLast: boolean
}) {
  const isExpanded = status === "active"

  return (
    <div className="relative">
      {/* Phase header */}
      <div className="flex items-center gap-3">
        {/* Status indicator */}
        <div
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded-full border-2 transition-colors",
            status === "completed" && "border-emerald-600 bg-emerald-600",
            status === "active" && "border-primary bg-primary",
            status === "pending" && "border-muted-foreground/30 bg-transparent"
          )}
        >
          {status === "completed" && <Check className="h-3.5 w-3.5 text-white" />}
          {status === "active" && <Loader2 className="h-3.5 w-3.5 text-white animate-spin" />}
          {status === "pending" && (
            <span className="text-xs text-muted-foreground/50 font-medium">
              {PHASES.indexOf(phase) + 1}
            </span>
          )}
        </div>

        {/* Phase label */}
        <span
          className={cn(
            "text-sm font-medium transition-colors",
            status === "completed" && "text-emerald-600",
            status === "active" && "text-foreground",
            status === "pending" && "text-muted-foreground/50"
          )}
        >
          {phase.label}
        </span>

        {/* Chevron for expandable */}
        <ChevronRight
          className={cn(
            "h-4 w-4 transition-transform",
            isExpanded && "rotate-90",
            status === "pending" ? "text-muted-foreground/30" : "text-muted-foreground"
          )}
        />
      </div>

      {/* Expanded steps */}
      {isExpanded && (
        <div className="mt-3 mb-2">
          {phase.steps.map((step, idx) => (
            <StepIndicator
              key={step}
              step={step}
              status={getStepStatus(step, currentStep, state.status === "completed")}
              counter={getStepCounter(step, state)}
              isLast={idx === phase.steps.length - 1}
            />
          ))}
        </div>
      )}

      {/* Connector line to next phase */}
      {!isLast && (
        <div
          className={cn(
            "absolute left-[11px] top-8 w-px h-6",
            status === "completed" ? "bg-emerald-600/50" : "bg-border"
          )}
        />
      )}
    </div>
  )
}

/** Success state */
function SyncSuccess({
  state,
  onViewTrades,
}: {
  state: SyncState
  onViewTrades: () => void
}) {
  const stats = [
    { label: "Trades", value: state.tradesCount },
    { label: "Orders", value: state.ordersFetched },
    { label: "Pairs", value: state.pairsProcessed.length },
    { label: "Daily PnL", value: state.dailyPnlRecords },
  ].filter((s) => s.value > 0)

  return (
    <div className="mt-6 border border-emerald-600/30 rounded-md bg-emerald-600/5 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Check className="h-4 w-4 text-emerald-600" />
        <span className="text-sm font-medium text-emerald-600">Sync completed</span>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        {stats.map((stat) => (
          <div key={stat.label} className="text-center">
            <p className="text-lg font-mono font-semibold text-foreground">{stat.value}</p>
            <p className="text-xs text-muted-foreground">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Pairs */}
      {state.pairsProcessed.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {state.pairsProcessed.map((pair) => (
            <span
              key={pair}
              className="text-xs font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground"
            >
              {pair}
            </span>
          ))}
        </div>
      )}

      <Button onClick={onViewTrades} size="sm" className="w-full">
        View positions
        <ArrowRight className="ml-2 h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

/** Error state */
function SyncError({
  message,
  onRetry,
  onBackToAccounts,
}: {
  message: string
  onRetry: () => void
  onBackToAccounts: () => void
}) {
  return (
    <div className="mt-6 border border-red-600/30 rounded-md bg-red-600/5 p-4">
      <div className="flex items-center gap-2 mb-2">
        <AlertCircle className="h-4 w-4 text-red-600" />
        <span className="text-sm font-medium text-red-600">Sync failed</span>
      </div>
      <p className="text-sm text-muted-foreground mb-4">{message || "An error occurred"}</p>
      <div className="flex gap-2">
        <Button onClick={onRetry} variant="outline" size="sm" className="flex-1">
          <RefreshCw className="mr-2 h-3.5 w-3.5" />
          Retry
        </Button>
        <Button onClick={onBackToAccounts} variant="ghost" size="sm" className="flex-1">
          <ArrowLeft className="mr-2 h-3.5 w-3.5" />
          Back to accounts
        </Button>
      </div>
    </div>
  )
}

/** Main sync page */
export function SyncPage() {
  const { accountId } = useParams<{ accountId: string }>()
  const navigate = useNavigate()
  const { setSelectedAccountId } = useAccount()

  const { state, start, reset, detach, pushSystemMessage } = useSyncStream({
    accountId: accountId || "",
    autoStart: true,
  })

  const handleContinueInBackground = useCallback(() => {
    detach()
    navigate("/accounts")
  }, [detach, navigate])

  // Equity fetching waiting messages timer
  const equityTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const equityMsgIndexRef = useRef(0)
  const equityStartTimeRef = useRef(0)

  useEffect(() => {
    const WAITING_MESSAGES = [
      "Connecting to exchange API...",
      "Fetching account balance...",
      "Downloading ledger entries...",
      "Processing transaction history...",
      "This may take a moment for large accounts...",
    ]

    if (state.currentStep === "equity_fetching") {
      // Start generating waiting messages
      equityMsgIndexRef.current = 0
      equityStartTimeRef.current = Date.now()

      equityTimerRef.current = setInterval(() => {
        const idx = equityMsgIndexRef.current
        if (idx < WAITING_MESSAGES.length) {
          pushSystemMessage(WAITING_MESSAGES[idx])
          equityMsgIndexRef.current++
        } else {
          const elapsed = Math.round((Date.now() - equityStartTimeRef.current) / 1000)
          pushSystemMessage(`Still fetching... (${elapsed}s)`)
        }
      }, 2000)

      return () => {
        if (equityTimerRef.current) {
          clearInterval(equityTimerRef.current)
          equityTimerRef.current = null
        }
      }
    } else {
      // Stop timer when step changes away from equity_fetching
      if (equityTimerRef.current) {
        clearInterval(equityTimerRef.current)
        equityTimerRef.current = null
      }
    }
  }, [state.currentStep, pushSystemMessage])

  // Block navigation while sync is in progress
  const isSyncing = state.status === "syncing" || state.status === "connecting"

  // Browser beforeunload warning (tab close / refresh)
  useEffect(() => {
    if (!isSyncing) return

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [isSyncing])

  // In-app navigation blocking (works with BrowserRouter)
  const [showLeavePrompt, setShowLeavePrompt] = useState(false)

  useEffect(() => {
    if (!isSyncing) return

    const handlePopState = () => {
      // User pressed back/forward — push current URL back and show dialog
      window.history.pushState(null, "", window.location.href)
      setShowLeavePrompt(true)
    }

    // Push a state so we can intercept the back button
    window.history.pushState(null, "", window.location.href)
    window.addEventListener("popstate", handlePopState)

    return () => {
      window.removeEventListener("popstate", handlePopState)
    }
  }, [isSyncing])

  const handleConfirmLeave = useCallback(() => {
    setShowLeavePrompt(false)
    detach()
    navigate(-1)
  }, [detach, navigate])

  const handleCancelLeave = useCallback(() => {
    setShowLeavePrompt(false)
  }, [])

  const progress = useMemo(
    () => calculateProgress(state.currentStep, state.status === "completed"),
    [state.currentStep, state.status]
  )

  const handleRetry = () => {
    reset()
    setTimeout(() => start(), 100)
  }

  const handleViewTrades = () => {
    if (accountId) {
      setSelectedAccountId(accountId)
    }
    navigate("/futures/positions")
  }

  useEffect(() => {
    if (!accountId) {
      navigate("/accounts")
    }
  }, [accountId, navigate])

  if (!accountId) return null

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-md px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-lg font-semibold text-foreground">Syncing account</h1>
          <p className="text-sm text-muted-foreground">Importing your trading history</p>
        </div>

        {/* Progress bar */}
        <div className="mb-6">
          <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
            <span>Progress</span>
            <span className="font-mono">{progress}%</span>
          </div>
          <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full transition-all duration-300 ease-out rounded-full",
                state.status === "completed" ? "bg-emerald-600" : "bg-primary",
                state.status === "error" && "bg-red-600"
              )}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Phases */}
        <div className="border rounded-md bg-card p-4 space-y-6">
          {PHASES.map((phase, idx) => (
            <PhaseItem
              key={phase.id}
              phase={phase}
              status={getPhaseStatus(
                phase,
                state.currentStep,
                state.status === "completed",
                state.status === "error"
              )}
              currentStep={state.currentStep}
              state={state}
              isLast={idx === PHASES.length - 1}
            />
          ))}
        </div>

        {/* Unified Console */}
        {(state.status === "syncing" || state.status === "completed" || state.status === "error") && (
          <div className="mt-4">
            <LiveDataFeed items={state.unifiedFeed} />
          </div>
        )}

        {/* Continue in background */}
        {state.status === "syncing" && (
          <div className="mt-4">
            <Button
              onClick={handleContinueInBackground}
              variant="outline"
              size="sm"
              className="w-full"
            >
              <MonitorSmartphone className="mr-2 h-3.5 w-3.5" />
              Continue in background
            </Button>
          </div>
        )}

        {/* Success */}
        {state.status === "completed" && (
          <SyncSuccess state={state} onViewTrades={handleViewTrades} />
        )}

        {/* Error */}
        {state.status === "error" && (
          <SyncError
            message={state.errorMessage || ""}
            onRetry={handleRetry}
            onBackToAccounts={() => navigate("/accounts")}
          />
        )}

        {/* Connecting */}
        {state.status === "connecting" && (
          <div className="mt-6 text-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mx-auto mb-2" />
            <p className="text-sm">Connecting...</p>
          </div>
        )}
      </div>

      {/* Navigation confirmation dialog */}
      <AlertDialog open={showLeavePrompt}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sync in progress</AlertDialogTitle>
            <AlertDialogDescription>
              A sync is currently running. If you leave, it will continue in the background.
              You can check its progress on the accounts page.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleCancelLeave}>Stay</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmLeave} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Leave
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default SyncPage
