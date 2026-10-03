'use client'

import React, { memo } from 'react'
import {
  Menu,
  PanelLeft,
  Search,
  RefreshCw,
  Moon,
  Sun,
  Terminal,
  Plus,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { FeatureExplainer } from '@/components/ui/feature-explainer'
import { NAVIGATION_ITEMS, connectionKey } from '@/lib/constants'
import { useDashboardStore } from '@/stores/useDashboardStore'
import { useOptimisticToast } from '@/components/ui/optimistic-toast'
import { apiUrl } from '@/lib/formatters'
import type { Currency, CloudProvider } from '@/types/dashboard'

interface DashboardHeaderProps {
  onOpenCommandPalette: () => void
  onOpenCliInstall: () => void
  onOpenConnect: () => void
  onSwitchAccount: (account: any) => Promise<void>
}

export const DashboardHeader = memo(function DashboardHeader({
  onOpenCommandPalette,
  onOpenCliInstall,
  onOpenConnect,
  onSwitchAccount,
}: DashboardHeaderProps) {
  const view = useDashboardStore((s) => s.view)
  const collapsed = useDashboardStore((s) => s.collapsed)
  const setCollapsed = useDashboardStore((s) => s.setCollapsed)
  const setMobileNavOpen = useDashboardStore((s) => s.setMobileNavOpen)
  const provider = useDashboardStore((s) => s.provider)
  const setProvider = useDashboardStore((s) => s.setProvider)
  const currency = useDashboardStore((s) => s.currency)
  const setCurrency = useDashboardStore((s) => s.setCurrency)
  const light = useDashboardStore((s) => s.light)
  const setLight = useDashboardStore((s) => s.setLight)
  const autoRefresh = useDashboardStore((s) => s.autoRefresh)
  const toggleAutoRefresh = useDashboardStore((s) => s.toggleAutoRefresh)
  const syncing = useDashboardStore((s) => s.syncing)
  const storeFetchData = useDashboardStore((s) => s.fetchData)
  const connectionState = useDashboardStore((s) => s.connectionState)
  const connectedAccounts = useDashboardStore((s) => s.connectedAccounts)
  const selectedAccountKey = useDashboardStore((s) => s.selectedAccountKey)
  const disconnectAccount = useDashboardStore((s) => s.disconnectAccount)

  const { toast } = useOptimisticToast()

  const currentNavItem = NAVIGATION_ITEMS.find((i) => i.id === view)
  const isConnected = connectionState?.connected

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-border bg-card/95 px-3 sm:px-4 md:px-6 backdrop-blur-md transition-colors">
      {/* Left: Mobile Nav Button + Desktop Collapse + View Title */}
      <div className="flex items-center gap-2 sm:gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden size-8 sm:size-9"
          onClick={() => setMobileNavOpen(true)}
          aria-label="Open mobile navigation"
        >
          <Menu className="size-5" />
        </Button>

        <Button
          variant="ghost"
          size="icon"
          className="hidden lg:flex size-8 sm:size-9 text-muted-foreground hover:text-foreground"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <PanelLeft className="size-4" />
        </Button>

        <div className="flex items-center gap-2">
          <h1 className="text-sm sm:text-base font-bold text-foreground tracking-tight">
            {currentNavItem?.label || 'Dashboard'}
          </h1>
        </div>
      </div>

      {/* Middle: Command Palette Quick Search Button */}
      <div className="flex-1 max-w-xs md:max-w-sm mx-2 sm:mx-4 hidden sm:block">
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="flex w-full items-center justify-between rounded-lg border border-border bg-muted/40 hover:bg-muted/70 px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <div className="flex items-center gap-2">
            <Search className="size-3.5 text-sky-600 dark:text-sky-400" />
            <span className="truncate">Search views, instances, actions...</span>
          </div>
          <kbd className="pointer-events-none hidden md:inline-flex h-5 select-none items-center gap-0.5 rounded border border-border bg-background px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
            <span className="text-xs">⌘</span>K
          </kbd>
        </button>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-1.5 sm:gap-2">
        {/* Connected Account Switcher */}
        {isConnected && (
          <FeatureExplainer featureKey="control-account-selector" placement="bottom">
            <Select
              value={selectedAccountKey || connectionKey(connectionState)}
              onValueChange={(val) => {
                if (val === '__disconnect__') {
                  disconnectAccount()
                  toast({
                    title: 'Account Disconnected',
                    description: 'CloudPulse credentials and active session cleared from this workspace.',
                    type: 'info',
                  })
                  return
                }
                const matched = connectedAccounts.find((a: any) => connectionKey(a) === val)
                if (matched) {
                  onSwitchAccount(matched)
                }
              }}
            >
              <SelectTrigger className="h-8 sm:h-9 max-w-[130px] sm:max-w-[200px] border-border bg-card text-xs font-medium">
                <span className="truncate flex items-center gap-1.5">
                  <span className="size-2 rounded-full bg-emerald-500 shrink-0" aria-hidden="true" />
                  {(() => {
                    const matched = connectedAccounts.find(
                      (a: any) => connectionKey(a) === (selectedAccountKey || connectionKey(connectionState))
                    )
                    if (matched?.account_name) return `${matched.account_name} (${matched.region || 'us-east-1'})`
                    if (connectionState?.account_name)
                      return `${connectionState.account_name} (${connectionState.region || 'us-east-1'})`
                    return 'Connected AWS'
                  })()}
                </span>
              </SelectTrigger>
              <SelectContent>
                {(Array.isArray(connectedAccounts) && connectedAccounts.length > 0
                  ? connectedAccounts
                  : [connectionState]
                ).map((account: any) => (
                  <SelectItem key={connectionKey(account)} value={connectionKey(account)}>
                    {account?.account_name || 'Connected account'} · {account?.region || 'us-east-1'}
                    {account?.active ? ' · Active' : ''}
                  </SelectItem>
                ))}
                <SelectItem value="__disconnect__" className="text-red-500 focus:text-red-400">
                  Disconnect Account
                </SelectItem>
              </SelectContent>
            </Select>
          </FeatureExplainer>
        )}

        {/* Provider Filter */}
        <FeatureExplainer featureKey="control-provider-filter" placement="bottom">
          <Select
            value={provider}
            onValueChange={(val) => {
              const next = (val as CloudProvider) || 'all'
              setProvider(next)
              toast({
                title: `Provider: ${next.toUpperCase()}`,
                description:
                  next === 'all'
                    ? 'Displaying resources across all active cloud accounts.'
                    : `Filtered views to ${next.toUpperCase()} infrastructure.`,
                type: 'info',
              })
            }}
          >
            <SelectTrigger className="hidden h-9 w-28 border-border bg-card text-xs font-medium sm:flex">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All providers</SelectItem>
              <SelectItem value="aws">AWS</SelectItem>
              <SelectItem value="gcp">GCP</SelectItem>
              <SelectItem value="azure">Azure</SelectItem>
            </SelectContent>
          </Select>
        </FeatureExplainer>

        {/* Currency Switcher */}
        <FeatureExplainer featureKey="control-currency-switcher" placement="bottom">
          <Select
            value={currency}
            onValueChange={(val) => {
              const next = (val as Currency) || 'USD'
              setCurrency(next)
              toast({
                title: `Currency: ${next}`,
                description:
                  next === 'INR'
                    ? 'Recalculated all fleet costs and savings to INR (₹ Lakhs / Crores).'
                    : 'Recalculated all fleet costs and savings to USD ($).',
                type: 'info',
              })
            }}
          >
            <SelectTrigger className="hidden h-9 w-28 border-border bg-card text-xs font-medium sm:flex">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="USD">USD ($)</SelectItem>
              <SelectItem value="INR">INR (₹ Lakhs)</SelectItem>
            </SelectContent>
          </Select>
        </FeatureExplainer>

        {/* Mobile Currency Toggle Button */}
        <Button
          variant="outline"
          size="sm"
          className="h-8 px-2 text-xs font-semibold sm:hidden border-border bg-card"
          onClick={() => {
            const next = currency === 'USD' ? 'INR' : 'USD'
            setCurrency(next)
            toast({
              title: `Currency: ${next}`,
              description: `Active display currency changed to ${next}.`,
              type: 'info',
            })
          }}
          aria-label="Toggle currency between USD and INR"
        >
          {currency === 'USD' ? '$' : '₹'}
        </Button>

        {/* Auto-Refresh Toggle */}
        <Button
          variant={autoRefresh ? 'secondary' : 'ghost'}
          size="sm"
          onClick={() => {
            toggleAutoRefresh()
            toast({
              title: !autoRefresh ? 'Autonomous Live Sync Active' : 'Auto-Sync Paused',
              description: !autoRefresh
                ? 'Sub-minute autonomous telemetry streaming engaged.'
                : 'Switched to manual sync mode.',
              type: !autoRefresh ? 'success' : 'info',
            })
          }}
          aria-label={autoRefresh ? 'Auto-refresh is active. Click to pause.' : 'Auto-refresh is paused. Click to enable.'}
          className={`h-8 px-2 text-xs font-medium border transition-all ${
            autoRefresh
              ? 'bg-primary text-primary-foreground border-primary'
              : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'
          }`}
        >
          <span
            className={`mr-1.5 size-1.5 rounded-full ${autoRefresh ? 'bg-background' : 'bg-muted-foreground'}`}
            aria-hidden="true"
          />
          <span className="hidden lg:inline">{autoRefresh ? 'Auto-sync ON' : 'Auto-sync OFF'}</span>
          <span className="lg:hidden">{autoRefresh ? 'Auto' : 'Manual'}</span>
        </Button>

        {/* Manual Refresh */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            storeFetchData(apiUrl, true)
            toast({
              title: 'Syncing Multi-Cloud Telemetry',
              description: 'Querying AWS CloudWatch, hypervisors, and telemetry ring buffers...',
              type: 'info',
            })
          }}
          aria-label="Refresh telemetry data"
          className="size-8 sm:size-9"
        >
          <RefreshCw className={`size-4 ${syncing ? 'animate-spin text-foreground' : ''}`} />
        </Button>

        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            setLight(!light)
            toast({
              title: light ? 'Dark Theme Active' : 'Light Theme Active',
              description: 'Workspace palette updated.',
              type: 'info',
            })
          }}
          aria-label={light ? 'Switch to dark theme' : 'Switch to light theme'}
          className="size-8 sm:size-9"
        >
          {light ? <Moon className="size-4" /> : <Sun className="size-4" />}
        </Button>

        {/* CLI Modal Trigger */}
        <Button
          variant="outline"
          size="sm"
          onClick={onOpenCliInstall}
          className="h-8 sm:h-9 border-border bg-card hover:bg-muted text-foreground px-2.5 sm:px-3 text-xs sm:text-sm font-medium"
          aria-label="Open CLI Installation instructions"
        >
          <Terminal className="size-4 shrink-0 text-foreground" />
          <span className="hidden sm:inline ml-1.5">CLI Tool</span>
        </Button>

        {/* Connect Account Primary CTA */}
        <FeatureExplainer featureKey="control-connect-account" placement="bottom">
          <Button
            size="sm"
            onClick={onOpenConnect}
            className="h-8 sm:h-9 bg-primary text-primary-foreground hover:bg-primary/90 px-2.5 sm:px-3 text-xs sm:text-sm font-medium transition-all"
            aria-label="Connect a cloud account"
          >
            <Plus className="size-4 shrink-0" />
            <span className="hidden sm:inline ml-1">Connect Account</span>
            <span className="sm:hidden ml-1">Connect</span>
          </Button>
        </FeatureExplainer>
      </div>
    </header>
  )
})
