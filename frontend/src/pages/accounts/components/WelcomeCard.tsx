import { useState } from "react"
import { Rocket } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import CreateAccountDialog from "./CreateAccountDialog"

export default function WelcomeCard() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <Card className="shadow-md flex flex-col h-full justify-center items-center p-6 min-h-[220px] col-span-full @md:col-span-1 border-primary/30">
        <Rocket className="h-10 w-10 text-muted-foreground mb-4" />
        <h2 className="text-lg font-semibold text-foreground text-center">
          Welcome to EdgeTrack
        </h2>
        <p className="mt-2 text-sm text-muted-foreground text-center max-w-xs">
          Track and analyze your crypto trades across exchanges. Connect your
          first exchange account to get started.
        </p>
        <Button className="mt-4" onClick={() => setIsOpen(true)}>
          Link an account
        </Button>
      </Card>

      <CreateAccountDialog open={isOpen} onOpenChange={setIsOpen} />
    </>
  )
}
