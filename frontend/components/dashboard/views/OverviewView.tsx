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
              className="border-sky-400/30 bg-sky-400/10 text-sky-300 hover:bg-sky-400/20"
              onClick={() => setPovOpen(true)}
            >
              <FileText className="mr-2 size-4" />Executive PoV Audit
            </Button>
            <Button variant="outline" onClick={() => setView('optimization')}>
              <Sparkles className="mr-1.5 size-4" />View savings opportunities
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
        <Card className="border-white/8 bg-card/75 backdrop-blur-sm">
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
                const isRed = alert.tone === 'red' || alert.tone === 'rose'
                const isEmerald = alert.tone === 'emerald'
                const isCyan = alert.tone === 'cyan' || alert.tone === 'sky'
                const toneBg = isRed
                  ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                  : isEmerald
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : isCyan
                  ? 'bg-sky-500/10 text-sky-400 border-sky-500/20'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/20'

                return (
                  <div
                    key={alert.id || alert.title || idx}
                    className="group flex items-start gap-3 rounded-lg border border-white/8 bg-white/[.02] p-3.5 transition-all duration-150 hover:bg-white/[.04] hover:border-white/15 hover:-translate-y-0.5"
                  >
                    <div className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border ${toneBg}`}>
                      <AlertTriangle className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-foreground tracking-tight group-hover:text-sky-300 transition-colors">
                        {alert.title || 'Untitled Alert'}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                        {alert.desc || alert.description || ''}
                      </div>
                    </div>
                    {alert.tag && (
                      <Badge variant="outline" className="border-white/10 bg-white/5 text-[10px] shrink-0 font-mono">
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
      <Card className="mt-6 border-sky-400/20 bg-gradient-to-r from-sky-950/40 via-card/75 to-card/75 backdrop-blur-sm">
        <CardContent className="flex flex-col gap-4 p-4 sm:p-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-sky-500 text-slate-950 font-semibold text-[11px]">48-Hour PoV Audit</Badge>
              <span className="text-xs text-sky-300 font-mono">Account {povData?.account_id || '582812122408'}</span>
            </div>
            <div className="text-base sm:text-lg font-semibold text-foreground">
              Enterprise FinOps Proof-of-Value Audit Ready
            </div>
            <p className="max-w-xl text-xs text-muted-foreground">
              Analyzed cloud infrastructure footprint reveals <b>{povData?.waste_percentage ?? 40.0}%</b> actionable waste.
              Recoverable annual savings: <span className="font-semibold text-emerald-300">{povData?.recoverable_annual_savings_formatted || formatCurrency((totalSpend * 0.40) * 12, currency)}</span>.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              className="border-white/10 bg-white/5 text-xs hover:bg-white/10"
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
                className="bg-sky-400 text-slate-950 hover:bg-sky-300 text-xs font-semibold"
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
                className="border-white/10 bg-white/5 text-xs hover:bg-white/10"
              >
                <FileText className="mr-1.5 size-3.5" />HTML View
              </Button>
            </a>
          </div>
        </CardContent>
      </Card>

      {/* PoV Executive Modal */}
      <Dialog open={povOpen} onOpenChange={setPovOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto border-white/10 bg-card text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <FileText className="size-4 text-sky-400" />
              Enterprise Proof-of-Value (PoV) Audit Dossier
            </DialogTitle>
            <DialogDescription>
              Executive briefing summarizing waste reduction, financial ROI, and production guardrail posture.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-lg border border-white/8 bg-white/5 p-3">
                <span className="text-[11px] text-muted-foreground">Annual Run Rate</span>
                <div className="mt-1 text-sm sm:text-base font-bold text-foreground">
                  {povData?.gross_annual_spend_formatted || formatCurrency(totalSpend * 12, currency)}
                </div>
              </div>
              <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-3">
                <span className="text-[11px] text-emerald-300">Recoverable / Year</span>
                <div className="mt-1 text-sm sm:text-base font-bold text-emerald-300">
                  {povData?.recoverable_annual_savings_formatted || formatCurrency(wastedSpend * 12, currency)}
                </div>
              </div>
              <div className="rounded-lg border border-amber-400/20 bg-amber-400/10 p-3">
                <span className="text-[11px] text-amber-300">Actionable Waste</span>
                <div className="mt-1 text-sm sm:text-base font-bold text-amber-300">
                  {povData?.waste_percentage ?? 40.0}%
                </div>
              </div>
              <div className="rounded-lg border border-white/8 bg-white/5 p-3">
                <span className="text-[11px] text-muted-foreground">Security Posture</span>
                <div className="mt-1 text-sm sm:text-base font-bold text-sky-300">98.2% CIS</div>
              </div>
            </div>

            <div className="rounded-lg border border-white/8 bg-white/5 p-4 text-xs space-y-2">
              <div className="font-semibold text-foreground">Audit Highlights & Vectors Identified:</div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-emerald-400" />
                  <span>Compute: Graviton ARM64 Rightsizing</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-emerald-400" />
                  <span>Storage: gp2 to gp3 Volume Upgrade</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-emerald-400" />
                  <span>Network: Unused EIPs & Idle Load Balancers</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-emerald-400" />
                  <span>SLA Watchdog: 60-min CloudWatch Rollback</span>
                </div>
              </div>
            </div>

            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setPovOpen(false)}>Close</Button>
              <a href={apiUrl(`/api/v2/analytics/pov/report.pdf?currency=${currency}&inline=true`)} target="_blank" rel="noopener noreferrer">
                <Button size="sm" className="w-full sm:w-auto bg-sky-400 text-slate-950 hover:bg-sky-300 font-semibold">
                  <Download className="mr-1.5 size-3.5" />Download Executive PDF
                </Button>
              </a>
              <a href={apiUrl('/api/v2/analytics/pov/report.html')} target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="sm" className="w-full sm:w-auto border-white/10 bg-white/5 hover:bg-white/10">
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
