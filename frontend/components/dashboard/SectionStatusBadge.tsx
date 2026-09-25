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
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300 shadow-[0_0_10px_-2px_rgba(16,185,129,0.25)]'
      : status === 'partial'
        ? 'border-amber-500/30 bg-amber-500/10 text-amber-300 shadow-[0_0_10px_-2px_rgba(245,158,11,0.25)]'
        : status === 'error'
          ? 'border-red-500/30 bg-red-500/10 text-red-300 shadow-[0_0_10px_-2px_rgba(239,68,68,0.25)]'
          : 'border-slate-500/30 bg-slate-500/10 text-slate-300'

  const dot =
    status === 'loading'
      ? 'bg-amber-400'
      : status === 'ready'
        ? 'bg-emerald-400'
        : status === 'partial'
          ? 'bg-amber-400'
          : status === 'error'
            ? 'bg-red-400'
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
