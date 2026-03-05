export function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="mt-1 text-muted-foreground">Welcome to EdgeTrack</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Placeholder cards for future metrics */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-sm font-medium text-muted-foreground">Total P&L</h3>
          <p className="mt-2 font-mono text-2xl font-semibold text-emerald-700 dark:text-emerald-400">
            +$1,234.56
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-sm font-medium text-muted-foreground">Open Positions</h3>
          <p className="mt-2 text-2xl font-semibold text-foreground">3</p>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-sm font-medium text-muted-foreground">Today's Trades</h3>
          <p className="mt-2 text-2xl font-semibold text-foreground">12</p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold text-foreground">Recent Activity</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Connect your exchange accounts to start tracking trades.
        </p>
      </div>
    </div>
  )
}

export default DashboardPage
