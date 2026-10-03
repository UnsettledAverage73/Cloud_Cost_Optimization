'use client'

import React, { memo, useMemo, useDeferredValue } from 'react'
import dynamic from 'next/dynamic'
import { Cloud, AlertTriangle, Loader2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SectionErrorBoundary } from '@/components/error-boundary'
import { MetricCardSkeleton, TableSkeleton, ChartSkeleton } from '@/components/empty-state'
import { DATA_SOURCES } from '@/lib/constants'
import { apiUrl } from '@/lib/formatters'
import { useDashboardStore } from '@/stores/useDashboardStore'
import type { SyncState } from '@/types/dashboard'

// Next.js Dynamic View Imports with Skeleton Fallbacks
const OverviewView = dynamic(() => import('@/components/dashboard/views/OverviewView'), {
  loading: () => <MetricCardSkeleton />,
  ssr: false,
})
const InventoryView = dynamic(() => import('@/components/dashboard/views/InventoryView'), {
  loading: () => <TableSkeleton rows={8} />,
  ssr: false,
})
const TelemetryView = dynamic(() => import('@/components/dashboard/views/TelemetryView'), {
  loading: () => <ChartSkeleton height="h-64" />,
  ssr: false,
})
const SecurityView = dynamic(() => import('@/components/dashboard/views/SecurityView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const OptimizationView = dynamic(() => import('@/components/dashboard/views/OptimizationView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const SchedulerPrewarmView = dynamic(() => import('@/components/dashboard/views/SchedulerPrewarmView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const GitOpsSlaView = dynamic(() => import('@/components/dashboard/views/GitOpsSlaView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const FleetView = dynamic(() => import('@/components/dashboard/views/FleetView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const CiCdGuardrailView = dynamic(() => import('@/components/dashboard/views/CiCdGuardrailView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const CopilotView = dynamic(() => import('@/components/dashboard/views/CopilotView'), {
  loading: () => <div className="py-20 text-center text-xs text-muted-foreground">Loading FinOps Copilot...</div>,
  ssr: false,
})
const SettingsView = dynamic(() => import('@/components/dashboard/views/SettingsView'), {
  loading: () => <div className="py-20 text-center text-xs text-muted-foreground">Loading Settings...</div>,
  ssr: false,
})

interface DashboardViewRouterProps {
  onOpenConnect: () => void
  onSwitchAccount: (account: any) => Promise<void>
}

export const DashboardViewRouter = memo(function DashboardViewRouter({
  onOpenConnect,
  onSwitchAccount,
}: DashboardViewRouterProps) {
  const view = useDashboardStore((s) => s.view)
  const setView = useDashboardStore((s) => s.setView)
  const loading = useDashboardStore((s) => s.loading)
  const syncing = useDashboardStore((s) => s.syncing)
  const connectionState = useDashboardStore((s) => s.connectionState)
  const dataError = useDashboardStore((s) => s.dataError)
  const dataSources = useDashboardStore((s) => s.dataSources)
  const currency = useDashboardStore((s) => s.currency)
  const search = useDashboardStore((s) => s.search)
  const setSearch = useDashboardStore((s) => s.setSearch)
  const status = useDashboardStore((s) => s.status)
  const setStatus = useDashboardStore((s) => s.setStatus)
  const nodes = useDashboardStore((s) => s.nodes)
  const setSelectedNode = useDashboardStore((s) => s.setSelectedNode)
  const telemetry = useDashboardStore((s) => s.telemetry)
  const timeframe = useDashboardStore((s) => s.timeframe)
  const setTimeframe = useDashboardStore((s) => s.setTimeframe)
  const securityTab = useDashboardStore((s) => s.securityTab)
  const setSecurityTab = useDashboardStore((s) => s.setSecurityTab)
  const summary = useDashboardStore((s) => s.summary)
  const securityAudit = useDashboardStore((s) => s.securityAudit)
  const revokeSecurityGroupLocally = useDashboardStore((s) => s.revokeSecurityGroupLocally)
  const optimizations = useDashboardStore((s) => s.optimizations)
  const applied = useDashboardStore((s) => s.applied)
  const setApplied = useDashboardStore((s) => s.setApplied)
  const spend = useDashboardStore((s) => s.spend)
  const alerts = useDashboardStore((s) => s.alerts)
  const connectedAccounts = useDashboardStore((s) => s.connectedAccounts)
  const rememberedProfile = useDashboardStore((s) => s.rememberedProfile)
  const selectedAccountKey = useDashboardStore((s) => s.selectedAccountKey)
  const storeFetchData = useDashboardStore((s) => s.fetchData)

  const connectionAccessMode = connectionState?.access_mode || 'live'
  const connectionWarning = connectionState?.warning || ''

  // Filter instances with useDeferredValue for 60fps responsiveness
  const deferredSearch = useDeferredValue(search)
  const filteredNodes = useMemo(() => {
    if (!Array.isArray(nodes)) return []
    const q = (deferredSearch || '').toLowerCase()
    return nodes.filter(
      (n) =>
        ((n?.name || '') + (n?.instance_id || '')).toLowerCase().includes(q) &&
        (status === 'all' || n?.state === status)
    )
  }, [nodes, deferredSearch, status])

  // Full Initial Account Sync Skeleton
  if (loading) {
    return (
      <Card className="border-border bg-card">
        <CardContent className="flex min-h-96 flex-col items-center justify-center gap-4 p-8 text-center">
          <Loader2 className="size-8 animate-spin text-foreground" />
          <div>
            <h2 className="text-lg font-semibold text-foreground">Syncing AWS account</h2>
            <p className="mt-2 max-w-lg text-sm text-muted-foreground">
              Loading connected resources and checking which AWS data sources are available.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {DATA_SOURCES.map((source) => (
              <Badge key={source.key} variant="outline" className="border-border text-muted-foreground">
                {source.label}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  // Not Connected State
  if (!connectionState?.connected) {
    return (
      <Card className="border-border bg-card">
        <CardContent className="p-8 text-center">
          <Cloud className="mx-auto size-8 text-foreground" />
          <h2 className="mt-4 text-lg font-semibold text-foreground">Live AWS data is not loaded</h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">
            {dataError || 'Connect an AWS account to continue.'}
          </p>
          <Button
            className="mt-5 bg-primary text-primary-foreground hover:bg-primary/90 font-medium"
            onClick={onOpenConnect}
          >
            Connect AWS account
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      {/* Limited IAM Permissions Warning Notice */}
      {connectionAccessMode === 'limited' && (
        <Card className="mb-6 border-border bg-secondary">
          <CardContent className="flex items-start gap-3 p-4">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-foreground" />
            <div className="min-w-0">
              <div className="text-sm font-medium text-foreground">Restricted IAM Permissions</div>
              <p className="mt-1 text-sm text-muted-foreground">
                {connectionWarning ||
                  'AWS account connected. Additional read-only permissions (ec2:Describe*, cloudwatch:GetMetricData) are recommended to unlock full real-time telemetry.'}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Persona View Routing */}
      {view === 'overview' && (
        <SectionErrorBoundary title="Overview">
          <OverviewView
            accessMode={connectionAccessMode}
            setView={setView}
            spend={spend}
            alerts={alerts}
            summary={summary}
            currency={currency}
            apiUrl={apiUrl}
            sectionStatus={dataSources.summary?.status || (syncing ? 'loading' : 'idle')}
          />
        </SectionErrorBoundary>
      )}

      {view === 'inventory' && (
        <SectionErrorBoundary title="Compute Inventory">
          <InventoryView
            accessMode={connectionAccessMode}
            search={search}
            setSearch={setSearch}
            status={status}
            setStatus={setStatus}
            filteredNodes={filteredNodes}
            setSelectedNode={setSelectedNode}
            sectionStatus={dataSources.nodes?.status || (syncing ? 'loading' : 'idle')}
            apiUrl={apiUrl}
            currency={currency}
          />
        </SectionErrorBoundary>
      )}

      {view === 'telemetry' && (
        <SectionErrorBoundary title="Telemetry Analytics">
          <TelemetryView
            accessMode={connectionAccessMode}
            telemetry={telemetry}
            timeframe={timeframe}
            setTimeframe={setTimeframe}
            sectionStatus={dataSources.telemetry?.status || (syncing ? 'loading' : 'idle')}
            nodes={nodes}
            apiUrl={apiUrl}
          />
        </SectionErrorBoundary>
      )}

      {view === 'security' && (
        <SectionErrorBoundary title="Security Center">
          <SecurityView
            accessMode={connectionAccessMode}
            tab={securityTab}
            setTab={setSecurityTab}
            summary={summary}
            audit={securityAudit}
            sectionStatus={dataSources.security?.status || (syncing ? 'loading' : 'idle')}
            apiUrl={apiUrl}
            onRefresh={() => storeFetchData(apiUrl, true)}
            revokeSecurityGroupLocally={revokeSecurityGroupLocally}
          />
        </SectionErrorBoundary>
      )}

      {view === 'optimization' && (
        <SectionErrorBoundary title="Cost Optimization">
          <OptimizationView
            accessMode={connectionAccessMode}
            items={optimizations}
            applied={applied}
            setApplied={setApplied}
            currency={currency}
            apiUrl={apiUrl}
            sectionStatus={
              dataSources.optimizations?.status === 'error'
                ? 'error'
                : dataSources.optimizations?.status === 'partial' || dataSources.applied?.status === 'partial'
                ? 'partial'
                : dataSources.optimizations?.status === 'ready' || dataSources.applied?.status === 'ready'
                ? 'ready'
                : syncing
                ? 'loading'
                : 'idle'
            }
          />
        </SectionErrorBoundary>
      )}

      {view === 'scheduler' && (
        <SectionErrorBoundary title="Scheduler & Pre-Warming">
          <SchedulerPrewarmView currency={currency} apiUrl={apiUrl} nodes={nodes} />
        </SectionErrorBoundary>
      )}

      {view === 'gitops-sla' && (
        <SectionErrorBoundary title="GitOps & SLA Watchdog">
          <GitOpsSlaView
            currency={currency}
            apiUrl={apiUrl}
            items={optimizations}
            applied={applied}
            setApplied={setApplied}
            nodes={nodes}
          />
        </SectionErrorBoundary>
      )}

      {view === 'fleet' && (
        <SectionErrorBoundary title="Enterprise Fleet">
          <FleetView currency={currency} apiUrl={apiUrl} />
        </SectionErrorBoundary>
      )}

      {view === 'cicd' && (
        <SectionErrorBoundary title="CI/CD Guardrails">
          <CiCdGuardrailView currency={currency} apiUrl={apiUrl} />
        </SectionErrorBoundary>
      )}

      {view === 'copilot' && (
        <SectionErrorBoundary title="FinOps Copilot">
          <CopilotView apiUrl={apiUrl} />
        </SectionErrorBoundary>
      )}

      {view === 'settings' && (
        <SectionErrorBoundary title="Account Settings">
          <SettingsView
            connectionState={connectionState}
            connectedAccounts={connectedAccounts}
            rememberedProfile={rememberedProfile}
            onSwitchAccount={onSwitchAccount}
            selectedAccountKey={selectedAccountKey}
            apiUrl={apiUrl}
          />
        </SectionErrorBoundary>
      )}
    </>
  )
})
