'use client'

import { memo } from 'react'
import type { SectionTitleProps } from '@/types/dashboard'

export const SectionTitle = memo(function SectionTitle({
  eyebrow,
  title,
  description,
  action,
  status,
}: SectionTitleProps) {
  return (
    <div className="mb-4 sm:mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 flex-1">
        {eyebrow && (
          <div className="mb-1.5 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-cyan-400">
            <span className="size-1.5 rounded-full bg-cyan-400" />
            {eyebrow}
          </div>
        )}
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-balance break-words text-foreground">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {(status || action) && (
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 shrink-0">
          {status}
          {action}
        </div>
      )}
    </div>
  )
})
