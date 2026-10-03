'use client'

import React, { memo } from 'react'
import { CloudCog } from 'lucide-react'
import { Sheet, SheetContent } from '@/components/ui/sheet'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { NAVIGATION_ITEMS } from '@/lib/constants'
import { useDashboardStore } from '@/stores/useDashboardStore'
import { useOptimisticToast } from '@/components/ui/optimistic-toast'
import type { Currency, CloudProvider } from '@/types/dashboard'

export const MobileNavSheet = memo(function MobileNavSheet() {
  const mobileNavOpen = useDashboardStore((s) => s.mobileNavOpen)
  const setMobileNavOpen = useDashboardStore((s) => s.setMobileNavOpen)
  const view = useDashboardStore((s) => s.view)
  const setView = useDashboardStore((s) => s.setView)
  const provider = useDashboardStore((s) => s.provider)
  const setProvider = useDashboardStore((s) => s.setProvider)
  const currency = useDashboardStore((s) => s.currency)
  const setCurrency = useDashboardStore((s) => s.setCurrency)

  const { toast } = useOptimisticToast()

  return (
    <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
      <SheetContent
        side="left"
        className="flex w-72 max-w-[85vw] flex-col justify-between border-r border-border bg-sidebar p-0"
      >
        <div className="flex flex-1 flex-col overflow-y-auto">
          {/* Header */}
          <div className="flex h-16 items-center border-b border-border px-4">
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-lg bg-foreground text-background">
                <CloudCog className="size-5" />
              </div>
              <span className="text-lg font-bold tracking-tight text-foreground">CloudPulse</span>
            </div>
          </div>

          {/* Quick Context Filters */}
          <div className="border-b border-border bg-secondary/50 p-3">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Quick Filters
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="mb-1 block text-[10px] text-muted-foreground">Provider</label>
                <Select
                  value={provider}
                  onValueChange={(val) => {
                    const next = (val as CloudProvider) || 'all'
                    setProvider(next)
                    toast({
                      title: `Provider: ${next.toUpperCase()}`,
                      description: `Filtered views to ${next.toUpperCase()} infrastructure.`,
                      type: 'info',
                    })
                  }}
                >
                  <SelectTrigger className="h-8 w-full border-border bg-background text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="aws">AWS</SelectItem>
                    <SelectItem value="gcp">GCP</SelectItem>
                    <SelectItem value="azure">Azure</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="mb-1 block text-[10px] text-muted-foreground">Currency</label>
                <Select
                  value={currency}
                  onValueChange={(val) => {
                    const next = (val as Currency) || 'USD'
                    setCurrency(next)
                    toast({
                      title: `Currency: ${next}`,
                      description: `Active display currency changed to ${next}.`,
                      type: 'info',
                    })
                  }}
                >
                  <SelectTrigger className="h-8 w-full border-border bg-background text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USD">USD ($)</SelectItem>
                    <SelectItem value="INR">INR (₹)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Nav Links */}
          <nav className="flex flex-col gap-1 p-3" aria-label="Mobile Navigation">
            {NAVIGATION_ITEMS.map((item) => {
              const Icon = item.icon
              const isActive = view === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setView(item.id)
                    setMobileNavOpen(false)
                  }}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                    isActive
                      ? 'bg-primary text-primary-foreground font-semibold'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  }`}
                >
                  <Icon className="size-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </button>
              )
            })}
          </nav>
        </div>
      </SheetContent>
    </Sheet>
  )
})
