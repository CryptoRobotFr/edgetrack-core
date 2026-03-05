import { useState } from "react"
import { Plus } from "lucide-react"
import { Card } from "@/components/ui/card"
import CreateAccountDialog from "./CreateAccountDialog"

export default function NewAccountCard() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <Card
        className="shadow-md flex flex-col h-full justify-center items-center p-6 border-2 hover:border-muted-foreground hover:bg-accent cursor-pointer hover:font-medium transition-colors duration-200 min-h-[220px] group"
        onClick={() => setIsOpen(true)}
      >
        <p className="text-center text-muted-foreground text-lg mb-4">
          Link a new account
        </p>
        <div
          className="rounded-full w-16 h-16 border-2 border-border flex items-center justify-center text-muted-foreground transition-colors duration-200 group-hover:border-muted-foreground group-hover:text-muted-foreground"
          aria-hidden="true"
        >
          <Plus className="h-8 w-8" />
        </div>
      </Card>

      <CreateAccountDialog open={isOpen} onOpenChange={setIsOpen} />
    </>
  )
}
