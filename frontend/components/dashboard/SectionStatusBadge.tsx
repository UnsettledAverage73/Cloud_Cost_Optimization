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
      ? 'border-border bg-secondary text-foreground'
      : status === 'partial'
        ? 'border-border bg-transparent text-muted-foreground'
        : status === 'error'
          ? 'border-foreground bg-foreground text-background font-semibold'
          : 'border-border bg-muted text-muted-foreground'

  const dot =
    status === 'loading'
      ? 'bg-foreground animate-pulse'
      : status === 'ready'
        ? 'bg-foreground'
        : status === 'partial'
          ? 'bg-muted-foreground'
          : status === 'error'
            ? 'bg-background'
            : 'bg-muted-foreground'

  return (
    <Badge variant="outline" className={`${classes} font-medium px-2.5 py-0.5 text-xs`}>
      <span className="relative flex size-2 mr-2">
        {status === 'loading' && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-foreground" />
        )}
        <span className={`relative inline-flex rounded-full size-2 ${dot}`} />
      </span>
      {getSectionStatusLabel(status)}
    </Badge>
  )
})
