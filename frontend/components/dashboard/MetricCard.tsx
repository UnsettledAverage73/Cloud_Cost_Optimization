'use client'

import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { ArrowUpRight } from 'lucide-react'
import type { MetricCardProps } from '@/types/dashboard'

export const MetricCard = memo(function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  trend,
}: MetricCardProps) {
  return (
    <Card className="group relative overflow-hidden rounded-lg border border-border bg-card transition-all duration-150 ease-out hover:border-foreground/40 hover:-translate-y-0.5">
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between">
          <div className="flex size-9 sm:size-10 items-center justify-center rounded-lg bg-secondary text-foreground border border-border shrink-0 transition-transform duration-150 group-hover:scale-105">
            <Icon className="size-4 sm:size-5" />
          </div>
          {trend && (
            <span className="flex items-center gap-1 rounded-full border border-border bg-secondary px-2 py-0.5 text-[11px] sm:text-xs font-semibold text-foreground">
              <ArrowUpRight className="size-3" />{trend}
            </span>
          )}
        </div>
        <div className="mt-4 sm:mt-5 text-xs font-medium tracking-wider uppercase text-muted-foreground">{label}</div>
        <div className="mt-1 text-xl sm:text-2xl font-bold tracking-tight text-foreground truncate font-mono">{value}</div>
        <div className="mt-1 text-xs text-muted-foreground truncate">{detail}</div>
      </CardContent>
    </Card>
  )
})
