import React, { ReactNode } from 'react'
import { LucideIcon, Inbox } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent } from '@/components/ui/card'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.01] p-8 text-center sm:p-12 ${className}`}
    >
      <div className="flex size-12 items-center justify-center rounded-full border border-white/10 bg-white/5 text-muted-foreground shadow-sm">
        <Icon className="size-6" />
      </div>
      <h4 className="mt-3 text-sm font-semibold text-foreground sm:text-base">{title}</h4>
      {description && (
        <p className="mt-1.5 max-w-sm text-xs text-muted-foreground sm:text-sm">
          {description}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function MetricCardSkeleton() {
  return (
    <Card className="border-white/8 bg-card/70 p-5">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="size-5 rounded-full" />
      </div>
      <Skeleton className="mt-3 h-8 w-36" />
      <Skeleton className="mt-2 h-3 w-44" />
    </Card>
  )
}

export function TableSkeleton({ rows = 5, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between gap-4 border-b border-white/8 pb-3">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center justify-between gap-4 py-2.5">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className="h-4 flex-1 opacity-70" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function ChartSkeleton({ height = 'h-64' }: { height?: string }) {
  return (
    <div className={`flex flex-col justify-end gap-2 p-6 ${height}`}>
      <div className="flex h-full items-end gap-2 sm:gap-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton
            key={i}
            className="w-full rounded-t-md"
            style={{ height: `${20 + ((i * 17) % 75)}%` }}
          />
        ))}
      </div>
      <div className="flex justify-between border-t border-white/8 pt-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  )
}
