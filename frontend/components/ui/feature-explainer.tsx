'use client'

import React, { useState, useRef, useEffect, useCallback, useId } from 'react'
import { FEATURE_EXPLAINERS, type FeatureExplainerData } from '@/lib/explainers'
import { Info, Sparkles, Shield, Cpu, Activity, Zap, HelpCircle } from 'lucide-react'

export type ExplainerPlacement = 'top' | 'bottom' | 'left' | 'right'

export interface FeatureExplainerProps {
  children: React.ReactNode
  featureKey?: string
  title?: string
  category?: 'FinOps' | 'Security' | 'Architecture' | 'Performance' | 'Reliability' | 'DevOps'
  description?: string
  impact?: string
  tip?: string
  simpleText?: string
  placement?: ExplainerPlacement
  disabled?: boolean
  className?: string
  delayMs?: number
  showInfoIcon?: boolean
}

export function FeatureExplainer({
  children,
  featureKey,
  title: directTitle,
  category: directCategory,
  description: directDescription,
  impact: directImpact,
  tip: directTip,
  simpleText,
  placement = 'top',
  disabled = false,
  className = '',
  delayMs = 120,
  showInfoIcon = false,
}: FeatureExplainerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [coords, setCoords] = useState<{ top: number; left: number }>({ top: 0, left: 0 })
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)
  const triggerRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const tooltipId = useId()

  const data: FeatureExplainerData | null = featureKey ? FEATURE_EXPLAINERS[featureKey] || null : null
  const title = directTitle || data?.title || ''
  const category = directCategory || data?.category || 'FinOps'
  const description = directDescription || data?.description || simpleText || ''
  const impact = directImpact || data?.impact || ''
  const tip = directTip || data?.tip || ''

  // Has content to display
  const hasContent = Boolean(description || title)

  const updatePosition = useCallback(() => {
    if (!triggerRef.current || !tooltipRef.current) return

    const triggerRect = triggerRef.current.getBoundingClientRect()
    const tooltipRect = tooltipRef.current.getBoundingClientRect()
    const spacing = 8

    let top = 0
    let left = 0

    switch (placement) {
      case 'bottom':
        top = triggerRect.bottom + spacing
        left = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2
        break
      case 'left':
        top = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2
        left = triggerRect.left - tooltipRect.width - spacing
        break
      case 'right':
        top = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2
        left = triggerRect.right + spacing
        break
      case 'top':
      default:
        top = triggerRect.top - tooltipRect.height - spacing
        left = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2
        break
    }

    // Viewport collision boundary checks (Apple HIG & Google Core Vitals polish)
    const padding = 12
    const maxLeft = window.innerWidth - tooltipRect.width - padding
    const maxTop = window.innerHeight - tooltipRect.height - padding

    // Flip vertical if overflowing window boundary
    if (placement === 'top' && top < padding) {
      top = triggerRect.bottom + spacing
    } else if (placement === 'bottom' && top > maxTop) {
      top = triggerRect.top - tooltipRect.height - spacing
    }

    left = Math.max(padding, Math.min(left, maxLeft))
    top = Math.max(padding, Math.min(top, maxTop))

    setCoords({ top, left })
  }, [placement])

  const handleMouseEnter = () => {
    if (disabled || !hasContent) return
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      setIsOpen(true)
    }, delayMs)
  }

  const handleMouseLeave = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      setIsOpen(false)
    }, 150)
  }

  useEffect(() => {
    if (isOpen) {
      updatePosition()
      const handleScrollOrResize = () => updatePosition()
      window.addEventListener('scroll', handleScrollOrResize, true)
      window.addEventListener('resize', handleScrollOrResize)
      return () => {
        window.removeEventListener('scroll', handleScrollOrResize, true)
        window.removeEventListener('resize', handleScrollOrResize)
      }
    }
  }, [isOpen, updatePosition])

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case 'Security':
        return <Shield className="size-3 text-foreground" />
      case 'Architecture':
        return <Cpu className="size-3 text-foreground" />
      case 'Performance':
        return <Activity className="size-3 text-foreground" />
      case 'Reliability':
        return <Zap className="size-3 text-foreground" />
      default:
        return <Sparkles className="size-3 text-foreground" />
    }
  }

  return (
    <>
      <div
        ref={triggerRef}
        className={`inline-flex items-center gap-1 cursor-help ${className}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocus={handleMouseEnter}
        onBlur={handleMouseLeave}
        aria-describedby={isOpen ? tooltipId : undefined}
      >
        {children}
        {showInfoIcon && (
          <Info className="size-3.5 text-muted-foreground hover:text-foreground transition-colors shrink-0" />
        )}
      </div>

      {isOpen && hasContent && typeof window !== 'undefined' && (
        <div
          ref={tooltipRef}
          id={tooltipId}
          role="tooltip"
          style={{
            position: 'fixed',
            top: `${coords.top}px`,
            left: `${coords.left}px`,
            zIndex: 9999,
          }}
          className={`
            pointer-events-none w-80 max-w-[calc(100vw-24px)] rounded-xl
            border border-border bg-card/95 p-3.5 text-foreground shadow-2xl backdrop-blur-md
            animate-in fade-in-0 zoom-in-95 duration-150 ease-[cubic-bezier(0.16,1,0.3,1)]
          `}
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-2 border-b border-border/60 pb-2">
            <span className="font-semibold text-xs tracking-tight text-foreground flex items-center gap-1.5 truncate">
              {title || 'Feature Insight'}
            </span>
            {category && (
              <span className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase text-muted-foreground shrink-0">
                {getCategoryIcon(category)}
                {category}
              </span>
            )}
          </div>

          {/* Description */}
          <div className="mt-2 text-xs leading-relaxed text-muted-foreground">
            {description}
          </div>

          {/* Business & FinOps Impact */}
          {impact && (
            <div className="mt-2.5 rounded-lg border border-border/80 bg-secondary/60 p-2 text-[11px] leading-snug">
              <span className="font-semibold text-foreground mr-1">Impact:</span>
              <span className="text-muted-foreground">{impact}</span>
            </div>
          )}

          {/* Actionable Tip */}
          {tip && (
            <div className="mt-2 flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <HelpCircle className="size-3 text-foreground shrink-0" />
              <span className="truncate">{tip}</span>
            </div>
          )}
        </div>
      )}
    </>
  )
}
