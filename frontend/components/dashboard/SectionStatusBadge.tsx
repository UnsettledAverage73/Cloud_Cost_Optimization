'use client'

import { memo } from 'react'
import { Badge } from '@/components/ui/badge'
import type { SectionStatusBadgeProps, SyncState } from '@/types/dashboard'

export function getSectionStatusLabel(status: SyncState): string {
  switch (status) {
    case 'loading':
      return 'Syncing'
    case 'ready':
      return 'Synced'
    case 'partial':
      return 'Partial'
    case 'error':
      return 'Unavailable'
    default:
      return 'Idle'
  }
}

export const SectionStatusBadge = memo(function SectionStatusBadge({ status }: SectionStatusBadgeProps) {
  const classes =
    status === 'ready'
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 shadow-xs'
      : status === 'partial'
        ? 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300 shadow-xs'
        : status === 'error'
          ? 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300 shadow-xs'
          : 'border-border bg-muted text-muted-foreground'

  const dot =
    status === 'loading'
      ? 'bg-amber-500'
      : status === 'ready'
        ? 'bg-emerald-500'
        : status === 'partial'
          ? 'bg-amber-500'
          : status === 'error'
            ? 'bg-red-500'
            : 'bg-slate-400'

  return (
    <Badge variant="outline" className={`${classes} font-medium px-2.5 py-0.5 text-xs`}>
      <span className="relative flex size-2 mr-2">
        {(status === 'ready' || status === 'loading') && (
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${status === 'ready' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
        )}
        <span className={`relative inline-flex rounded-full size-2 ${dot}`} />
      </span>
      {getSectionStatusLabel(status)}
    </Badge>
  )
})
