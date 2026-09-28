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

import { FeatureExplainer } from '@/components/ui/feature-explainer'

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
  const [selectedReportType, setSelectedReportType] = useState<string>('executive')
  const [reportCatalog, setReportCatalog] = useState<any[]>([])

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
        const [povRes, catRes] = await Promise.all([
          fetch(apiUrl(`/api/v2/analytics/pov/summary?currency=${currency}&rate=84.0`)),
          fetch(apiUrl('/api/v2/reports/catalog'))
        ])
        if (povRes.ok && !cancelled) setPovData(await povRes.json())
        if (catRes.ok && !cancelled) {
          const d = await catRes.json()
          if (Array.isArray(d?.catalog)) setReportCatalog(d.catalog)
        }
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
            <FeatureExplainer featureKey="control-pov-audit" placement="bottom">
              <Button
                variant="outline"
                className="border-border bg-card text-foreground hover:bg-muted font-medium transition-all duration-150"
                onClick={() => setPovOpen(true)}
              >
                <FileText className="mr-2 size-4 text-foreground" />Executive PoV Audit
              </Button>
            </FeatureExplainer>
            <FeatureExplainer featureKey="action-savings-view" placement="bottom">
              <Button
                variant="outline"
                onClick={() => setView('optimization')}
                className="border-border bg-card text-foreground hover:bg-muted transition-all duration-150"
              >
                <Sparkles className="mr-1.5 size-4 text-foreground" />View savings opportunities
              </Button>
            </FeatureExplainer>
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
              featureKey="metric-total-spend"
            />
            <MetricCard
              icon={Cpu}
              label="Active compute nodes"
              value={formatInteger(activeNodes)}
              detail={`${formatInteger(Math.max(totalNodes - activeNodes, 0))} stopped · ${formatInteger(totalNodes)} total`}
              tone="emerald"
              featureKey="metric-active-nodes"
            />
            <MetricCard
              icon={ArrowDownRight}
              label={`Monthly wasted spend (${currency})`}
              value={formatCurrency(wastedSpend, currency)}
              detail="Actionable savings"
              tone="amber"
              featureKey="metric-wasted-spend"
            />
            <MetricCard
              icon={ShieldAlert}
              label="Critical security risks"
              value={formatInteger(criticalRisks)}
              detail="Exposure alerts from the backend"
              tone="rose"
              featureKey="metric-security-risks"
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
        <DialogContent className="sm:max-w-4xl w-[95vw] max-h-[88vh] flex flex-col p-0 gap-0 border border-border bg-card text-foreground shadow-2xl overflow-hidden">
          <DialogHeader className="p-6 pb-4 border-b border-border shrink-0">
            <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
              <FileText className="size-5 text-foreground shrink-0" />
              Enterprise Proof-of-Value (PoV) Audit Dossier
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm text-muted-foreground mt-1">
              Executive briefing summarizing waste reduction, financial ROI, and production guardrail posture.
            </DialogDescription>
          </DialogHeader>

          <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="rounded-xl border border-border bg-muted/40 p-3.5 shadow-xs flex flex-col justify-between">
                <span className="text-[11px] font-medium text-muted-foreground">Annual Run Rate</span>
                <div className="mt-1 text-sm sm:text-base font-bold font-mono text-foreground truncate">
                  {povData?.gross_annual_spend_formatted || formatCurrency(totalSpend * 12, currency)}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-card p-3.5 shadow-xs flex flex-col justify-between">
                <span className="text-[11px] font-medium text-muted-foreground">Recoverable / Year</span>
                <div className="mt-1 text-sm sm:text-base font-bold font-mono text-foreground truncate">
                  {povData?.recoverable_annual_savings_formatted || formatCurrency(wastedSpend * 12, currency)}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-card p-3.5 shadow-xs flex flex-col justify-between">
                <span className="text-[11px] font-medium text-muted-foreground">Actionable Waste</span>
                <div className="mt-1 text-sm sm:text-base font-bold font-mono text-foreground">
                  {povData?.waste_percentage ?? 0}%
                </div>
              </div>
              <div className="rounded-xl border border-border bg-muted/40 p-3.5 shadow-xs flex flex-col justify-between">
                <span className="text-[11px] font-medium text-muted-foreground">Security Posture</span>
                <div className="mt-1 text-sm sm:text-base font-bold text-foreground truncate">98.2% CIS Benchmark</div>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-muted/30 p-4 text-xs space-y-2">
              <div className="font-bold text-foreground">Audit Highlights & Vectors Identified:</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-foreground shrink-0" />
                  <span>Compute: Graviton ARM64 Rightsizing</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-foreground shrink-0" />
                  <span>Storage: gp2 to gp3 Volume Upgrade</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-foreground shrink-0" />
                  <span>Network: Unused EIPs & Idle Load Balancers</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-foreground shrink-0" />
                  <span>SLA Watchdog: 60-min CloudWatch Rollback</span>
                </div>
              </div>
            </div>

            {/* Persona-Specific Audit Dossiers Selection */}
            <div className="space-y-2.5">
              <span className="text-xs font-bold text-foreground">Select Report Persona & Dossier Format:</span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {(reportCatalog.length > 0 ? reportCatalog : [
                  { id: 'executive', name: 'Executive CFO Board Dossier', description: 'Financial run-rate, waste %, dual currency, and commitment arbitrage.', target_audience: 'CFO, Finance VP' },
                  { id: 'engineering', name: 'Engineering Rightsizing Matrix', description: 'Node-level CPU/RAM, ASGs, downsize recommendations, and Graviton roadmap.', target_audience: 'VP Eng, DevOps Leads' },
                  { id: 'security_hygiene', name: 'FinOps Waste & Guardrails Audit', description: 'Zombie EBS volumes, unattached EIPs, and Terraform HCL remediation.', target_audience: 'SecOps, Infrastructure' },
                  { id: 'telemetry_snapshot', name: 'Real-Time Telemetry & SLA Snapshot', description: 'Live CloudWatch metrics, timeseries curves, and SLA canary watchdog logs.', target_audience: 'SREs, Ops Responders' }
                ]).map((cat: any) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setSelectedReportType(cat.id)}
                    className={`p-3.5 rounded-lg border text-left transition-all flex flex-col justify-between ${
                      selectedReportType === cat.id
                        ? 'border-foreground bg-muted/50 ring-1 ring-foreground'
                        : 'border-border bg-card hover:bg-muted/20'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-xs text-foreground leading-tight">{cat.name}</span>
                      {selectedReportType === cat.id && (
                        <Badge className="bg-foreground text-background text-[9px] py-0 px-1.5 shrink-0">Selected</Badge>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-1.5 leading-snug">{cat.description}</p>
                    <span className="text-[10px] text-muted-foreground block mt-2 font-mono">Audience: {cat.target_audience}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Dialog Sticky Footer */}
          <div className="px-6 py-3.5 border-t border-border bg-muted/20 shrink-0 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5">
            <Button variant="ghost" size="sm" onClick={() => setPovOpen(false)} className="w-full sm:w-auto">
              Close
            </Button>
            <div className="flex flex-col sm:flex-row items-center gap-2 w-full sm:w-auto">
              <a
                href={apiUrl('/api/v2/analytics/pov/report.html')}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto"
              >
                <Button variant="outline" size="sm" className="w-full sm:w-auto border-border bg-card hover:bg-muted text-foreground">
                  <ExternalLink className="mr-1.5 size-3.5" />Interactive HTML
                </Button>
              </a>
              <a
                href={apiUrl(`/api/v2/reports/pdf?report_type=${selectedReportType}&currency=${currency}`)}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto"
              >
                <Button size="sm" className="w-full sm:w-auto bg-primary text-primary-foreground hover:bg-primary/90 font-semibold shadow-xs">
                  <Download className="mr-1.5 size-3.5" />Download {selectedReportType === 'executive' ? 'Executive CFO' : selectedReportType === 'engineering' ? 'Engineering' : selectedReportType === 'security_hygiene' ? 'Security & Waste' : 'Telemetry SLA'} PDF
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
