'use client'

import React from 'react'
import {
  Activity,
  CheckCircle2,
  Cloud,
  Command,
  Moon,
  RefreshCw,
  Search,
  Sun,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { formatCurrency } from '@/lib/formatters'
import type { Currency, ConnectionState } from '@/types/dashboard'

interface TopContextBarProps {
  connectionState: ConnectionState
  currency: Currency
  onToggleCurrency: () => void
  hourlyBurnRate?: number
  syncing?: boolean
  lastSynced?: string | null
  onRefresh?: () => void
  onOpenCommandPalette: () => void
  light: boolean
  onToggleTheme: () => void
  onOpenConnect: () => void
}

export function TopContextBar({
  connectionState,
  currency,
  onToggleCurrency,
  hourlyBurnRate = 0.18,
  syncing = false,
  lastSynced,
  onRefresh,
  onOpenCommandPalette,
  light,
  onToggleTheme,
  onOpenConnect,
}: TopContextBarProps) {
  const isConnected = connectionState?.connected
  const provider = connectionState?.provider || 'AWS'
  const accountName = connectionState?.account_name || 'Production Account'
  const region = connectionState?.region || 'us-east-1'

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-white/8 bg-card/80 px-4 sm:px-6 backdrop-blur-md transition-colors duration-200">
      {/* Left: Account & Connection Status Context */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenConnect}
          className="flex items-center gap-2 rounded-lg border border-white/8 bg-white/[0.03] px-2.5 py-1.5 text-xs transition-colors hover:border-sky-500/30 hover:bg-white/[0.06]"
        >
          <div className="flex size-5 items-center justify-center rounded-full bg-sky-500/10 text-sky-400">
            <Cloud className="size-3" />
          </div>
          <span className="font-semibold text-foreground tracking-tight">{accountName}</span>
          <Badge variant="outline" className="border-sky-500/30 text-sky-300 bg-sky-500/10 text-[10px] font-mono px-1.5 py-0">
            {provider} · {region}
          </Badge>
          <span className="relative flex size-2">
            {isConnected ? (
              <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full size-2 bg-emerald-400" />
              </>
            ) : (
              <span className="relative inline-flex rounded-full size-2 bg-amber-400" />
            )}
          </span>
        </button>

        {/* Real-time Burn Rate pill */}
        <div className="hidden md:flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1 text-xs text-emerald-300">
          <Zap className="size-3.5 text-emerald-400" />
          <span className="text-muted-foreground text-[11px]">Burn rate:</span>
          <strong className="font-mono font-semibold text-emerald-300">
            {formatCurrency(hourlyBurnRate, currency)}/hr
          </strong>
        </div>
      </div>

      {/* Center: Quick Search / Command Palette shortcut trigger */}
      <div className="flex-1 max-w-sm mx-4 hidden lg:block">
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="flex w-full items-center justify-between rounded-lg border border-white/8 bg-white/[0.03] px-3 py-1.5 text-xs text-muted-foreground transition hover:border-white/15 hover:bg-white/[0.06]"
        >
          <div className="flex items-center gap-2">
            <Search className="size-3.5 text-sky-400" />
            <span>Search or jump anywhere...</span>
          </div>
          <div className="flex items-center gap-1">
            <kbd className="rounded border border-white/15 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              ⌘K
            </kbd>
          </div>
        </button>
      </div>

      {/* Right Controls: Sync indicator, Currency Switcher, Theme, Mobile Search */}
      <div className="flex items-center gap-2">
        {/* Mobile Command Palette trigger */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenCommandPalette}
          className="lg:hidden text-muted-foreground hover:text-foreground"
          aria-label="Open Command Palette"
        >
          <Search className="size-4" />
        </Button>

        {/* Background sync & refresh button */}
        <button
          onClick={onRefresh}
          disabled={syncing}
          className="flex items-center gap-1.5 rounded-lg border border-white/8 bg-white/[0.03] px-2 py-1 text-[11px] text-muted-foreground transition hover:border-white/15 hover:bg-white/[0.06] disabled:opacity-50"
        >
          <RefreshCw className={`size-3 text-sky-400 ${syncing ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">
            {syncing ? 'Syncing...' : lastSynced ? `Synced ${lastSynced}` : 'Live'}
          </span>
        </button>

        {/* Currency Switcher */}
        <Button
          variant="outline"
          size="sm"
          onClick={onToggleCurrency}
          className="h-8 border-white/10 bg-white/5 font-mono text-xs font-semibold text-foreground hover:bg-white/10 hover:border-sky-500/40"
        >
          {currency === 'USD' ? '$ USD' : '₹ INR'}
        </Button>

        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleTheme}
          className="size-8 text-muted-foreground hover:text-foreground"
          aria-label="Toggle dark/light theme"
        >
          {light ? <Moon className="size-4" /> : <Sun className="size-4 text-amber-400" />}
        </Button>
      </div>
    </header>
  )
}
export default TopContextBar
