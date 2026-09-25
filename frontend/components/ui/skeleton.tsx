import * as React from "react"
import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "relative overflow-hidden rounded-md bg-white/[0.04] dark:bg-white/[0.03] border border-white/[0.03] shimmer-sweep",
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
