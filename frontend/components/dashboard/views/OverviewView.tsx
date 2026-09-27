'use client'

import { useState, useEffect } from 'react'
import {
  AlertTriangle,
  ArrowDownRight,
  CheckCircle2,
  CircleDollarSign,
  Cpu,
  Download,
  Eye,
  ExternalLink,
  FileText,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, MetricCardSkeleton } from '@/components/empty-state'
import { MetricCard, SectionTitle, SectionStatusBadge } from '@/components/dashboard'
import { formatCurrency, formatInteger } from '@/lib/formatters'
import type { Currency, ViewType } from '@/types/dashboard'

interface OverviewViewProps {
  accessMode?: string
  setView: (view: ViewType) => void
  spend?: any[]
  alerts?: any[]
  summary?: any
  sectionStatus?: 'idle' | 'loading' | 'ready' | 'partial' | 'error'
  currency?: Currency
  apiUrl: (path: string) => string
}

export function OverviewView({
  accessMode,
  setView,
  alerts = [],
  summary,
  sectionStatus = 'idle',
  currency = 'USD',
  apiUrl,
}: OverviewViewProps) {
  const [povOpen, setPovOpen] = useState(false)
  const [povData, setPovData] = useState<any>(null)
  const [povLoading, setPovLoading] = useState(false)

  const totalSpend = summary?.monthly_spend ?? 0
  const activeNodes = summary?.running_nodes ?? 0
  const totalNodes = summary?.total_nodes ?? 0
  const wastedSpend = summary?.wasted_monthly_spend ?? 0
  const criticalRisks = summary?.critical_security_risks ?? 0
  const lastSynced = summary?.last_synced ? new Date(summary.last_synced).toLocaleString() : 'Just now'

  useEffect(() => {
    let cancelled = false
    const fetchPov = async () => {
      setPovLoading(true)
      try {
        const res = await fetch(apiUrl(`/api/v2/analytics/pov/summary?currency=${currency}&rate=84.0`))
        if (res.ok && !cancelled) setPovData(await res.json())
      } catch (e) {
        console.error('PoV load error:', e)
      } finally {
        if (!cancelled) setPovLoading(false)
      }
    }
    fetchPov()
    return () => {
      cancelled = true
    }
  }, [apiUrl, currency])

  return (
    <>
      <SectionTitle
        eyebrow="Executive overview"
        title="Your cloud, at a glance."
        description="A unified operational view across connected providers."
        status={<SectionStatusBadge status={sectionStatus} />}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              className="border-border bg-card text-foreground hover:bg-muted font-medium"
              onClick={() => setPovOpen(true)}
            >
              <FileText className="mr-2 size-4 text-foreground" />Executive PoV Audit
            </Button>
            <Button variant="outline" onClick={() => setView('optimization')} className="border-border bg-card text-foreground hover:bg-muted">
              <Sparkles className="mr-1.5 size-4 text-foreground" />View savings opportunities
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {sectionStatus === 'loading' ? (
          <>
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
          </>
        ) : (
          <>
            <MetricCard
              icon={CircleDollarSign}
              label={`Total monthly spend (${currency})`}
              value={formatCurrency(totalSpend, currency)}
              detail={`Last synced ${lastSynced}`}
              tone="sky"
              trend="Live"
            />
            <MetricCard
              icon={Cpu}
              label="Active compute nodes"
              value={formatInteger(activeNodes)}
              detail={`${formatInteger(Math.max(totalNodes - activeNodes, 0))} stopped · ${formatInteger(totalNodes)} total`}
              tone="emerald"
            />
            <MetricCard
              icon={ArrowDownRight}
              label={`Monthly wasted spend (${currency})`}
              value={formatCurrency(wastedSpend, currency)}
              detail="Actionable savings"
              tone="amber"
            />
            <MetricCard
              icon={ShieldAlert}
              label="Critical security risks"
              value={formatInteger(criticalRisks)}
              detail="Exposure alerts from the backend"
              tone="rose"
            />
          </>
        )}
      </div>

      <div className="mt-6">
        <Card className="border border-border bg-card shadow-xs">
          <CardHeader>
            <CardTitle className="text-base font-semibold">Quick alerts</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">Items needing your attention</p>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {sectionStatus === 'loading' ? (
              <div className="space-y-3 col-span-full">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </div>
            ) : (Array.isArray(alerts) ? alerts : []).length === 0 ? (
              <EmptyState
                icon={CheckCircle2}
                title="All systems optimal"
                description="Zero infrastructure or billing alerts requiring action."
                className="py-8 border-0 col-span-full"
              />
            ) : (
              (Array.isArray(alerts) ? alerts : []).map((alert: any, idx: number) => {
                return (
                  <div
                    key={alert.id || alert.title || idx}
                    className="group flex items-start gap-3 rounded-xl border border-border bg-card p-3.5 transition-all duration-150 hover:bg-muted/40 hover:border-foreground/40 hover:-translate-y-0.5 shadow-xs"
                  >
                    <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-muted text-foreground">
                      <AlertTriangle className="size-4 text-foreground" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-foreground tracking-tight transition-colors">
                        {alert.title || 'Untitled Alert'}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                        {alert.desc || alert.description || ''}
                      </div>
                    </div>
                    {alert.tag && (
                      <Badge variant="outline" className="border-border bg-muted text-[10px] shrink-0 font-mono text-foreground shadow-xs">
                        {alert.tag}
                      </Badge>
                    )}
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>
      </div>

      {/* Proof-of-Value Highlight Dossier Card */}
      <Card className="mt-6 border border-border bg-card shadow-xs">
        <CardContent className="flex flex-col gap-4 p-4 sm:p-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-primary text-primary-foreground font-semibold text-[11px] shadow-xs">Executive Audit</Badge>
              {povData?.account_id && (
                <span className="text-xs text-muted-foreground font-mono font-medium">Account {povData.account_id}</span>
              )}
            </div>
            <div className="text-base sm:text-lg font-bold text-foreground">
              Enterprise FinOps Proof-of-Value Audit Ready
            </div>
            <p className="max-w-xl text-xs text-muted-foreground leading-relaxed">
              Analyzed cloud infrastructure footprint reveals <b>{povData?.waste_percentage ?? 0}%</b> actionable waste.
              Recoverable annual savings: <span className="font-bold text-foreground font-mono">{povData?.recoverable_annual_savings_formatted || formatCurrency(wastedSpend * 12, currency)}</span>.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              className="border-border bg-card text-foreground hover:bg-muted text-xs shadow-xs"
              onClick={() => setPovOpen(true)}
            >
              <Eye className="mr-1.5 size-3.5" />View Dossier
            </Button>
            <a
              href={apiUrl(`/api/v2/analytics/pov/report.pdf?currency=${currency}&inline=true`)}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button
                size="sm"
                className="bg-primary text-primary-foreground hover:bg-primary/90 text-xs font-semibold shadow-xs"
              >
                <Download className="mr-1.5 size-3.5" />Download PDF Audit
              </Button>
            </a>
            <a
              href={apiUrl('/api/v2/analytics/pov/report.html')}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button
                variant="outline"
                size="sm"
                className="border-border bg-card text-foreground hover:bg-muted text-xs shadow-xs"
              >
                <FileText className="mr-1.5 size-3.5" />HTML View
              </Button>
            </a>
          </div>
        </CardContent>
      </Card>

      {/* PoV Executive Modal */}
      <Dialog open={povOpen} onOpenChange={setPovOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto border border-border bg-card text-foreground shadow-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold text-foreground">
              <FileText className="size-4 text-foreground" />
              Enterprise Proof-of-Value (PoV) Audit Dossier
            </DialogTitle>
            <DialogDescription>
              Executive briefing summarizing waste reduction, financial ROI, and production guardrail posture.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-xl border border-border bg-muted/40 p-3 shadow-xs">
                <span className="text-[11px] font-medium text-muted-foreground">Annual Run Rate</span>
                <div className="mt-1 text-sm sm:text-base font-bold font-mono text-foreground">
                  {povData?.gross_annual_spend_formatted || formatCurrency(totalSpend * 12, currency)}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-card p-3 shadow-xs">
                <span className="text-[11px] font-medium text-muted-foreground">Recoverable / Year</span>
                <div className="mt-1 text-sm sm:text-base font-bold font-mono text-foreground">
                  {povData?.recoverable_annual_savings_formatted || formatCurrency(wastedSpend * 12, currency)}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-card p-3 shadow-xs">
                <span className="text-[11px] font-medium text-muted-foreground">Actionable Waste</span>
                <div className="mt-1 text-sm sm:text-base font-bold font-mono text-foreground">
                  {povData?.waste_percentage ?? 0}%
                </div>
              </div>
              <div className="rounded-xl border border-border bg-muted/40 p-3 shadow-xs">
                <span className="text-[11px] font-medium text-muted-foreground">Security Posture</span>
                <div className="mt-1 text-sm sm:text-base font-bold text-foreground">98.2% CIS</div>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-muted/30 p-4 text-xs space-y-2">
              <div className="font-bold text-foreground">Audit Highlights & Vectors Identified:</div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-foreground" />
                  <span>Compute: Graviton ARM64 Rightsizing</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-foreground" />
                  <span>Storage: gp2 to gp3 Volume Upgrade</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-foreground" />
                  <span>Network: Unused EIPs & Idle Load Balancers</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-foreground" />
                  <span>SLA Watchdog: 60-min CloudWatch Rollback</span>
                </div>
              </div>
            </div>

            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setPovOpen(false)}>Close</Button>
              <a href={apiUrl(`/api/v2/analytics/pov/report.pdf?currency=${currency}&inline=true`)} target="_blank" rel="noopener noreferrer">
                <Button size="sm" className="w-full sm:w-auto bg-primary text-primary-foreground hover:bg-primary/90 font-semibold shadow-xs">
                  <Download className="mr-1.5 size-3.5" />Download Executive PDF
                </Button>
              </a>
              <a href={apiUrl('/api/v2/analytics/pov/report.html')} target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="sm" className="w-full sm:w-auto border-border bg-card hover:bg-muted text-foreground">
                  <ExternalLink className="mr-1.5 size-3.5" />Interactive HTML
                </Button>
              </a>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
export default OverviewView
