import { type ReactNode } from "react"

interface AuthLayoutProps {
  children: ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-screen md:grid-cols-2">
      {/* Hero panel — always dark, hidden on mobile */}
      <div className="relative hidden items-center justify-center overflow-hidden bg-slate-900 md:flex">
        {/* Radial gradient overlay */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at top, hsl(217 91% 60% / 0.15), transparent 70%)",
          }}
        />
        <div className="relative z-10 flex flex-col items-center gap-4 px-8">
          <img
            src="/logo.svg"
            alt="EdgeTrack"
            className="h-20 w-20 rounded-2xl"
          />
          <h1 className="text-3xl font-bold text-white">EdgeTrack</h1>
          <p className="text-lg text-white/60">Your Edge in Crypto Trading</p>
        </div>
      </div>

      {/* Form panel */}
      <div className="flex flex-col items-center justify-center bg-gradient-to-br from-background to-primary/5 p-6 md:p-10">
        {/* Mobile logo — visible only on small screens */}
        <div className="mb-8 flex flex-col items-center gap-2 md:hidden">
          <img
            src="/logo.svg"
            alt="EdgeTrack"
            className="h-12 w-12 rounded-xl"
          />
          <h2 className="text-xl font-bold">EdgeTrack</h2>
          <p className="text-sm text-muted-foreground">
            Your Edge in Crypto Trading
          </p>
        </div>

        {children}
      </div>
    </div>
  )
}
