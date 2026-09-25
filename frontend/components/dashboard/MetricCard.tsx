'use client'

import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { ArrowUpRight } from 'lucide-react'
import type { MetricCardProps } from '@/types/dashboard'

const toneStyles: Record<string, { bg: string; text: string; glow: string; border: string }> = {
  cyan: {
    bg: 'bg-sky-500/10',
    text: 'text-sky-400',
    glow: 'group-hover:shadow-[0_0_24px_-4px_rgba(56,189,248,0.25)]',
    border: 'group-hover:border-sky-500/40',
  },
  sky: {
    bg: 'bg-sky-500/10',
    text: 'text-sky-400',
    glow: 'group-hover:shadow-[0_0_24px_-4px_rgba(56,189,248,0.25)]',
    border: 'group-hover:border-sky-500/40',
  },
  indigo: {
    bg: 'bg-indigo-500/10',
    text: 'text-indigo-400',
    glow: 'group-hover:shadow-[0_0_24px_-4px_rgba(99,102,241,0.25)]',
    border: 'group-hover:border-indigo-500/40',
  },
  emerald: {
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-400',
    glow: 'group-hover:shadow-[0_0_24px_-4px_rgba(16,185,129,0.25)]',
    border: 'group-hover:border-emerald-500/40',
  },
  purple: {
    bg: 'bg-purple-500/10',
    text: 'text-purple-400',
    glow: 'group-hover:shadow-[0_0_24px_-4px_rgba(168,85,247,0.25)]',
    border: 'group-hover:border-purple-500/40',
  },
  amber: {
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
    glow: 'group-hover:shadow-[0_0_24px_-4px_rgba(245,158,11,0.25)]',
    border: 'group-hover:border-amber-500/40',
  },
  rose: {
    bg: 'bg-rose-500/10',
    text: 'text-rose-400',
    glow: 'group-hover:shadow-[0_0_24px_-4px_rgba(244,63,94,0.25)]',
    border: 'group-hover:border-rose-500/40',
  },
  red: {
    bg: 'bg-rose-500/10',
    text: 'text-rose-400',
    glow: 'group-hover:shadow-[0_0_24px_-4px_rgba(244,63,94,0.25)]',
    border: 'group-hover:border-rose-500/40',
  },
  blue: {
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
    glow: 'group-hover:shadow-[0_0_24px_-4px_rgba(59,130,246,0.25)]',
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
    <Card className={`group relative overflow-hidden rounded-xl border border-white/[0.08] bg-card/85 shadow-lg shadow-black/25 backdrop-blur-md transition-all duration-200 ease-out hover:-translate-y-0.5 ${currentTone.border} ${currentTone.glow}`}>
      {/* Subtle top edge specular highlight */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent" />
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between">
          <div className={`flex size-9 sm:size-10 items-center justify-center rounded-xl ${currentTone.bg} ${currentTone.text} ring-1 ring-white/10 shrink-0 transition-transform duration-200 group-hover:scale-105`}>
            <Icon className="size-4 sm:size-5" />
          </div>
          {trend && (
            <span className="flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[11px] sm:text-xs font-medium text-emerald-400 shadow-xs">
              <ArrowUpRight className="size-3" />{trend}
            </span>
          )}
        </div>
        <div className="mt-4 sm:mt-5 text-xs font-medium tracking-wide uppercase text-muted-foreground/80">{label}</div>
        <div className="mt-1 text-xl sm:text-2xl font-bold tracking-tight text-foreground truncate font-mono">{value}</div>
        <div className="mt-1 text-xs text-muted-foreground truncate">{detail}</div>
      </CardContent>
    </Card>
  )
})
