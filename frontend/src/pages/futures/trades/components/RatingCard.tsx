import { useState } from "react"
import { Star } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface RatingCardProps {
  rating: number
  onRatingChange: (rating: number) => void
  isSaving?: boolean
}

export function RatingCard({
  rating,
  onRatingChange,
  isSaving,
}: RatingCardProps) {
  const [hoverRating, setHoverRating] = useState<number | null>(null)

  const displayRating = hoverRating ?? rating

  return (
    <Card>
      <CardHeader className="p-4">
        <CardTitle className="text-sm flex items-center justify-between">
          Rating
          {isSaving && (
            <span className="text-xs text-muted-foreground font-normal">
              Saving...
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <div className="flex items-center gap-1">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              className="p-1 transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 rounded"
              onMouseEnter={() => setHoverRating(star)}
              onMouseLeave={() => setHoverRating(null)}
              onClick={() => {
                // Toggle off if clicking the same rating
                const newRating = rating === star ? 0 : star
                onRatingChange(newRating)
              }}
              aria-label={`Rate ${star} star${star > 1 ? "s" : ""}`}
            >
              <Star
                className={`h-6 w-6 transition-colors ${
                  star <= displayRating
                    ? "fill-yellow-400 text-yellow-400"
                    : "text-muted-foreground/30 hover:text-yellow-400/50"
                }`}
              />
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
