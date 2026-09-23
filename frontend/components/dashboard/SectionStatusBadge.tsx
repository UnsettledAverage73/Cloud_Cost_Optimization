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
      ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
      : status === 'partial'
        ? 'border-amber-400/30 bg-amber-400/10 text-amber-300'
        : status === 'error'
          ? 'border-red-400/30 bg-red-400/10 text-red-300'
          : 'border-slate-400/30 bg-slate-400/10 text-slate-300'

  const dot =
    status === 'loading'
      ? 'bg-amber-400 animate-pulse'
      : status === 'ready'
        ? 'bg-emerald-400'
        : status === 'partial'
          ? 'bg-amber-400'
          : status === 'error'
            ? 'bg-red-400'
            : 'bg-slate-400'

  return (
    <Badge variant="outline" className={classes}>
      <span className={`mr-2 size-2 rounded-full ${dot}`} />
      {getSectionStatusLabel(status)}
    </Badge>
  )
})
