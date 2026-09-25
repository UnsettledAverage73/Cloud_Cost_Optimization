'use client'

import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { ArrowUpRight } from 'lucide-react'
import type { MetricCardProps } from '@/types/dashboard'

const toneStyles: Record<string, { bg: string; text: string; glow: string; border: string }> = {
  cyan: {
    bg: 'bg-sky-500/10 dark:bg-sky-500/15',
    text: 'text-sky-600 dark:text-sky-400',
    glow: 'group-hover:shadow-[0_4px_20px_-2px_rgba(14,165,233,0.18)]',
    border: 'group-hover:border-sky-500/40',
  },
  sky: {
    bg: 'bg-sky-500/10 dark:bg-sky-500/15',
    text: 'text-sky-600 dark:text-sky-400',
    glow: 'group-hover:shadow-[0_4px_20px_-2px_rgba(14,165,233,0.18)]',
    border: 'group-hover:border-sky-500/40',
  },
  indigo: {
    bg: 'bg-indigo-500/10 dark:bg-indigo-500/15',
    text: 'text-indigo-600 dark:text-indigo-400',
    glow: 'group-hover:shadow-[0_4px_20px_-2px_rgba(99,102,241,0.18)]',
    border: 'group-hover:border-indigo-500/40',
  },
  emerald: {
    bg: 'bg-emerald-500/10 dark:bg-emerald-500/15',
    text: 'text-emerald-600 dark:text-emerald-400',
    glow: 'group-hover:shadow-[0_4px_20px_-2px_rgba(16,185,129,0.18)]',
    border: 'group-hover:border-emerald-500/40',
  },
  purple: {
    bg: 'bg-purple-500/10 dark:bg-purple-500/15',
    text: 'text-purple-600 dark:text-purple-400',
    glow: 'group-hover:shadow-[0_4px_20px_-2px_rgba(168,85,247,0.18)]',
    border: 'group-hover:border-purple-500/40',
  },
  amber: {
    bg: 'bg-amber-500/10 dark:bg-amber-500/15',
    text: 'text-amber-600 dark:text-amber-400',
    glow: 'group-hover:shadow-[0_4px_20px_-2px_rgba(245,158,11,0.18)]',
    border: 'group-hover:border-amber-500/40',
  },
  rose: {
    bg: 'bg-rose-500/10 dark:bg-rose-500/15',
    text: 'text-rose-600 dark:text-rose-400',
    glow: 'group-hover:shadow-[0_4px_20px_-2px_rgba(244,63,94,0.18)]',
    border: 'group-hover:border-rose-500/40',
  },
  red: {
    bg: 'bg-rose-500/10 dark:bg-rose-500/15',
    text: 'text-rose-600 dark:text-rose-400',
    glow: 'group-hover:shadow-[0_4px_20px_-2px_rgba(244,63,94,0.18)]',
    border: 'group-hover:border-rose-500/40',
  },
  blue: {
    bg: 'bg-blue-500/10 dark:bg-blue-500/15',
    text: 'text-blue-600 dark:text-blue-400',
    glow: 'group-hover:shadow-[0_4px_20px_-2px_rgba(59,130,246,0.18)]',
    border: 'group-hover:border-blue-500/40',
  },
}

export const MetricCard = memo(function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  tone = 'cyan',
  trend,
}: MetricCardProps) {
  const currentTone = toneStyles[tone] || toneStyles.cyan

  return (
    <Card className={`group relative overflow-hidden rounded-xl border border-border/80 dark:border-white/[0.08] bg-card shadow-sm dark:shadow-lg dark:shadow-black/25 backdrop-blur-md transition-all duration-200 ease-out hover:-translate-y-0.5 hover:shadow-md ${currentTone.border} ${currentTone.glow}`}>
      {/* Subtle top edge highlight */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-border to-transparent dark:via-white/15" />
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between">
          <div className={`flex size-9 sm:size-10 items-center justify-center rounded-xl ${currentTone.bg} ${currentTone.text} ring-1 ring-border/50 dark:ring-white/10 shrink-0 transition-transform duration-200 group-hover:scale-105`}>
            <Icon className="size-4 sm:size-5" />
          </div>
          {trend && (
            <span className="flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] sm:text-xs font-semibold text-emerald-700 dark:text-emerald-400 shadow-xs">
              <ArrowUpRight className="size-3" />{trend}
            </span>
          )}
        </div>
        <div className="mt-4 sm:mt-5 text-xs font-semibold tracking-wider uppercase text-muted-foreground">{label}</div>
        <div className="mt-1 text-xl sm:text-2xl font-bold tracking-tight text-foreground truncate font-mono">{value}</div>
        <div className="mt-1 text-xs text-muted-foreground truncate">{detail}</div>
      </CardContent>
    </Card>
  )
})
