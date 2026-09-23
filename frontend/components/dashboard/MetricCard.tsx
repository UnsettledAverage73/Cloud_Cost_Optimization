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
  tone = 'cyan',
  trend,
}: MetricCardProps) {
  return (
    <Card className="border-white/8 bg-card/70 shadow-lg shadow-black/10 backdrop-blur">
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between">
          <div className={`flex size-9 sm:size-10 items-center justify-center rounded-xl bg-${tone}-500/10 text-${tone}-400 shrink-0`}>
            <Icon className="size-4 sm:size-5" />
          </div>
          {trend && (
            <span className="flex items-center gap-1 text-[11px] sm:text-xs font-medium text-emerald-400">
              <ArrowUpRight className="size-3" />{trend}
            </span>
          )}
        </div>
        <div className="mt-4 sm:mt-5 text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-xl sm:text-2xl font-semibold tracking-tight truncate">{value}</div>
        <div className="mt-1 text-xs text-muted-foreground truncate">{detail}</div>
      </CardContent>
    </Card>
  )
})
