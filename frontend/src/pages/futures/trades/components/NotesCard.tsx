import { useState, useEffect, useRef } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface NotesCardProps {
  notes: string
  onNotesChange: (notes: string) => void
  isSaving?: boolean
}

const DEBOUNCE_MS = 1000

export function NotesCard({ notes, onNotesChange, isSaving }: NotesCardProps) {
  const [localNotes, setLocalNotes] = useState(notes)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync local state when notes prop changes (e.g., from API response)
  useEffect(() => {
    setLocalNotes(notes)
  }, [notes])

  const handleChange = (value: string) => {
    setLocalNotes(value)

    // Clear existing timeout
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    // Set new timeout for debounced save
    debounceRef.current = setTimeout(() => {
      onNotesChange(value)
    }, DEBOUNCE_MS)
  }

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [])

  return (
    <Card>
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-sm flex items-center justify-between">
          Notes
          {isSaving && (
            <span className="text-xs text-muted-foreground font-normal">
              Saving...
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-2">
        <textarea
          value={localNotes}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Add notes about this trade..."
          className="w-full h-64 p-2 text-xs bg-transparent border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        />
      </CardContent>
    </Card>
  )
}
