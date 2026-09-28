'use client'

import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { ArrowUpRight, HelpCircle } from 'lucide-react'
import { FeatureExplainer } from '@/components/ui/feature-explainer'
import type { MetricCardProps } from '@/types/dashboard'

export const MetricCard = memo(function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  trend,
  featureKey,
  explainer,
}: MetricCardProps) {
  const cardContent = (
    <Card className="group relative overflow-hidden rounded-xl border border-border bg-card transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] hover:border-foreground/40 hover:-translate-y-0.5 hover:shadow-lg">
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between">
          <div className="flex size-9 sm:size-10 items-center justify-center rounded-lg bg-secondary text-foreground border border-border shrink-0 transition-transform duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-105">
            <Icon className="size-4 sm:size-5" />
          </div>
          <div className="flex items-center gap-1.5">
            {(featureKey || explainer) && (
              <span className="opacity-0 group-hover:opacity-100 transition-opacity duration-150 text-muted-foreground hover:text-foreground">
                <HelpCircle className="size-3.5" />
              </span>
            )}
            {trend && (
              <span className="flex items-center gap-1 rounded-full border border-border bg-secondary px-2 py-0.5 text-[11px] sm:text-xs font-semibold text-foreground">
                <ArrowUpRight className="size-3" />{trend}
              </span>
            )}
          </div>
        </div>
        <div className="mt-4 sm:mt-5 text-xs font-medium tracking-wider uppercase text-muted-foreground flex items-center justify-between">
          <span>{label}</span>
        </div>
        <div className="mt-1 text-xl sm:text-2xl font-bold tracking-tight text-foreground truncate font-mono">{value}</div>
        <div className="mt-1 text-xs text-muted-foreground truncate">{detail}</div>
      </CardContent>
    </Card>
  )

  if (featureKey || explainer) {
    return (
      <FeatureExplainer
        featureKey={featureKey}
        title={explainer?.title}
        description={explainer?.description}
        impact={explainer?.impact}
        tip={explainer?.tip}
        placement="top"
        className="w-full text-left block"
      >
        {cardContent}
      </FeatureExplainer>
    )
  }

  return cardContent
})

