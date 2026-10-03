'use client'

import React, { memo } from 'react'
import { CloudCog } from 'lucide-react'
import { FeatureExplainer } from '@/components/ui/feature-explainer'
import { NAVIGATION_ITEMS } from '@/lib/constants'
import { useDashboardStore } from '@/stores/useDashboardStore'
import type { ViewType } from '@/types/dashboard'

export const DashboardSidebar = memo(function DashboardSidebar() {
  const view = useDashboardStore((s) => s.view)
  const setView = useDashboardStore((s) => s.setView)
  const collapsed = useDashboardStore((s) => s.collapsed)

  return (
    <aside
      aria-label="Primary Navigation"
      className={`fixed inset-y-0 left-0 z-30 hidden border-r border-border bg-sidebar/95 transition-all lg:flex lg:flex-col ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between border-b border-border px-4">
        <a href="/" className="flex items-center gap-2.5 hover:opacity-85 transition-opacity" aria-label="CloudPulse Home">
          <div className="flex size-8 items-center justify-center rounded-lg bg-foreground text-background">
            <CloudCog className="size-5" />
          </div>
          {!collapsed && <span className="text-lg font-bold tracking-tight text-foreground">CloudPulse</span>}
        </a>
        {!collapsed && (
          <a
            href="/"
            className="rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            ← Home
          </a>
        )}
      </div>

      {/* Navigation List */}
      <nav className="flex flex-1 flex-col gap-1 p-3 overflow-y-auto" aria-label="Dashboard Views">
        {NAVIGATION_ITEMS.map((item) => {
          const Icon = item.icon
          const isActive = view === item.id
          return (
            <FeatureExplainer
              key={item.id}
              featureKey={`nav-${item.id}`}
              placement="right"
              className="w-full block"
            >
              <button
                type="button"
                onClick={() => setView(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`w-full group relative flex items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  isActive
                    ? 'bg-primary text-primary-foreground font-semibold border border-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <Icon className="size-4 shrink-0 transition-transform duration-150 group-hover:scale-105" />
                {!collapsed && <span className="truncate">{item.label}</span>}
                {item.id === 'security' && !collapsed && (
                  <span className="ml-auto flex size-2 relative" aria-hidden="true">
                    <span
                      className={`relative inline-flex rounded-full size-2 ${
                        isActive ? 'bg-primary-foreground' : 'bg-foreground'
                      }`}
                    />
                  </span>
                )}
              </button>
            </FeatureExplainer>
          )
        })}
      </nav>

      {/* Footer Info Badge */}
      {!collapsed && (
        <div className="border-t border-border p-3">
          <div className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="relative flex size-2" aria-hidden="true">
                <span className="relative inline-flex rounded-full size-2 bg-foreground" />
              </span>
              <span className="text-[11px] text-muted-foreground font-medium">FinOps Core</span>
            </div>
            <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-semibold text-foreground border border-border">
              Active
            </span>
          </div>
        </div>
      )}
    </aside>
  )
})
