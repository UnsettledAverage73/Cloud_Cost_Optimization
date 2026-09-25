'use client'

import { useState, useMemo } from 'react'
import {
  AlertTriangle,
  Bell,
  Check,
  CheckCircle2,
  Copy,
  ExternalLink,
  FileCode,
  GitBranch,
  GitPullRequest,
  Loader2,
  RotateCcw,
  Send,
  Sparkles,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/empty-state'
import { SectionTitle, SectionStatusBadge } from '@/components/dashboard'
import { useOptimisticToast } from '@/components/ui/optimistic-toast'
import { formatCurrency } from '@/lib/formatters'
import type { Currency, OptimizationRecommendation } from '@/types/dashboard'

interface OptimizationViewProps {
  accessMode?: string
  items: OptimizationRecommendation[]
  applied: string[]
  setApplied: (applied: string[] | ((prev: string[]) => string[])) => void
  sectionStatus?: 'idle' | 'loading' | 'ready' | 'partial' | 'error'
  currency?: Currency
  apiUrl: (path: string) => string
}

export function OptimizationView({
  items = [],
  applied = [],
  setApplied,
  sectionStatus = 'idle',
  currency = 'USD',
  apiUrl,
}: OptimizationViewProps) {
  const { toast } = useOptimisticToast()
  const [optFilter, setOptFilter] = useState<'all' | 'pending' | 'applied'>('all')
  const [broadcastOpen, setBroadcastOpen] = useState(false)
  const [broadcasting, setBroadcasting] = useState(false)
  const [broadcastTarget, setBroadcastTarget] = useState<'slack' | 'teams'>('slack')
  const [broadcastResult, setBroadcastResult] = useState<string | null>(null)

  const [gitopsOpen, setGitopsOpen] = useState(false)
  const [gitopsLoading, setGitopsLoading] = useState(false)
  const [gitopsPackage, setGitopsPackage] = useState<any | null>(null)
  const [gitopsCopied, setGitopsCopied] = useState(false)

  const appliedSet = useMemo(() => new Set(applied || []), [applied])
  const pendingItems = useMemo(() => items.filter((i: any) => !appliedSet.has(i.id)), [items, appliedSet])
  const appliedItems = useMemo(() => items.filter((i: any) => appliedSet.has(i.id)), [items, appliedSet])

  const pendingSavings = useMemo(() => {
    return pendingItems
      .filter((i: any) => !i.is_alternative)
      .reduce((sum: number, item: any) => sum + Number(item.savings ?? 0), 0)
  }, [pendingItems])

  const realizedSavings = useMemo(() => {
    return appliedItems
      .filter((i: any) => !i.is_alternative)
      .reduce((sum: number, item: any) => sum + Number(item.savings ?? 0), 0)
  }, [appliedItems])

  const filteredItems = useMemo(() => {
    return items.filter((item: any) => {
      const isDone = appliedSet.has(item.id)
      if (optFilter === 'pending') return !isDone
      if (optFilter === 'applied') return isDone
      return true
    })
  }, [items, appliedSet, optFilter])

  const toggleOptimization = async (id: string) => {
    const isApplied = appliedSet.has(id)
    const item = items.find((x: any) => x.id === id)
    const prevApplied = [...applied]
    const newApplied = isApplied ? applied.filter((x: string) => x !== id) : [...applied, id]

    // Instant optimistic local update
    setApplied(newApplied)
    toast({
      title: isApplied ? 'Optimization Reverted' : 'Recommendation Applied',
      description: isApplied
        ? `Reverted configuration change for ${item?.resource_id || id}.`
        : `Optimistically activated ${item?.type || 'rightsizing'} on ${item?.resource_id || id} (${formatCurrency(item?.savings, currency)}/mo savings).`,
      type: isApplied ? 'warning' : 'success',
    })

    try {
      const res = await fetch(apiUrl('/api/optimizations/apply'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, action: isApplied ? 'revert' : 'apply' }),
      })
      if (!res.ok) {
        setApplied(prevApplied)
        toast({
          title: 'Optimization Sync Failed',
          description: `Backend was unable to ${isApplied ? 'revert' : 'apply'} ${id}. Rolled back changes.`,
          type: 'error',
        })
      }
    } catch {
      setApplied(prevApplied)
      toast({
        title: 'Connection Error',
        description: 'Failed to communicate with optimization endpoint. Rolled back.',
        type: 'error',
      })
    }
  }

  const handleApplyAllRemaining = async () => {
    const idsToApply = pendingItems.map((i: any) => i.id)
    if (idsToApply.length === 0) return

    const newApplied = [...applied, ...idsToApply]
    setApplied(newApplied)
    toast({
      title: `Batch Enacted: ${idsToApply.length} Optimizations`,
      description: `Optimistically scheduled changes saving ~${formatCurrency(pendingSavings, currency)}/mo.`,
      type: 'success',
    })

    try {
      await Promise.all(
        pendingItems.map((i: any) =>
          fetch(apiUrl('/api/optimizations/apply'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: i.id, action: 'apply' }),
          })
        )
      )
    } catch {
      toast({
        title: 'Batch Sync Notice',
        description: 'Some items may need manual sync verification.',
        type: 'warning',
      })
    }
  }

  const handleRevertAll = async () => {
    const prevApplied = [...applied]
    setApplied([])
    toast({
      title: 'All Optimizations Reverted',
      description: `Restored baseline configurations for ${appliedItems.length} resources.`,
      type: 'warning',
    })

    try {
      await Promise.all(
        appliedItems.map((i: any) =>
          fetch(apiUrl('/api/optimizations/apply'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: i.id, action: 'revert' }),
          })
        )
      )
    } catch {
      setApplied(prevApplied)
    }
  }

  const handleBatchGitopsPr = async () => {
    setGitopsOpen(true)
    setGitopsLoading(true)
    setGitopsPackage(null)
    try {
      const res = await fetch(apiUrl('/api/v2/gitops/batch-pr'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          findings: items.map((i: any) => ({
            resource_id: i.resource_id || i.id,
            action: i.type?.toLowerCase().includes('storage') ? 'gp3_upgrade' : 'downsize',
            monthly_savings: Number(i.savings ?? 0),
            resource_type: i.type?.toLowerCase().includes('storage') ? 'ebs' : 'ec2',
          })),
          environment: 'production',
          repo_name: 'infrastructure/aws-workloads',
        }),
      })
      if (res.ok) {
        setGitopsPackage(await res.json())
      }
    } catch (e) {
      console.error('GitOps batch PR failed:', e)
    } finally {
      setGitopsLoading(false)
    }
  }

  const handleSingleGitopsPr = async (item: any) => {
    setGitopsOpen(true)
    setGitopsLoading(true)
    setGitopsPackage(null)
    try {
      const res = await fetch(apiUrl('/api/v2/gitops/pr'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resource_id: item.resource_id || item.id,
          action: item.type?.toLowerCase().includes('storage') ? 'gp3_upgrade' : 'downsize',
          monthly_savings: Number(item.savings ?? 0),
          environment: 'production',
          repo_name: 'infrastructure/aws-workloads',
        }),
      })
      if (res.ok) {
        setGitopsPackage(await res.json())
      }
    } catch (e) {
      console.error('Single GitOps PR failed:', e)
    } finally {
      setGitopsLoading(false)
    }
  }

  return (
    <>
      <SectionTitle
        eyebrow="Optimization engine"
        title="Make every cloud dollar count."
        description="Prioritized recommendations based on live usage, pricing, and risk signals."
        status={<SectionStatusBadge status={sectionStatus} />}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              className="border-indigo-500/30 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-500/20 text-xs font-medium"
              onClick={handleBatchGitopsPr}
            >
              <GitBranch className="mr-1.5 size-3.5" />Batch GitOps PR
            </Button>
            <Button
              variant="outline"
              className="border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 hover:bg-sky-500/20 text-xs font-medium"
              onClick={() => {
                setBroadcastOpen(true)
                setBroadcastResult(null)
              }}
            >
              <Bell className="mr-1.5 size-3.5" />Broadcast Digest
            </Button>
            {pendingItems.length > 0 ? (
              <Button
                onClick={handleApplyAllRemaining}
                className="bg-sky-600 text-white hover:bg-sky-500 text-xs font-semibold shadow-xs"
              >
                <Zap className="mr-1.5 size-3.5" />Apply remaining ({pendingItems.length})
              </Button>
            ) : (
              <Button
                variant="outline"
                onClick={handleRevertAll}
                className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/20 text-xs font-medium"
              >
                <RotateCcw className="mr-1.5 size-3.5" />Revert all optimizations
              </Button>
            )}
          </div>
        }
      />

      {/* FinOps Metrics & Lifecycle Counter Banner */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-3 shadow-xs">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full border border-border bg-muted px-3 py-1 text-muted-foreground font-medium">
            <strong className="text-foreground font-mono">{pendingItems.length}</strong> pending recommendations
          </span>
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 font-semibold text-amber-700 dark:text-amber-300">
            {formatCurrency(pendingSavings, currency)} potential savings remaining
          </span>
          {appliedItems.length > 0 && (
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 font-semibold text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5" />
              {appliedItems.length} enacted &middot; {formatCurrency(realizedSavings, currency)}/mo realized
            </span>
          )}
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1">
          <Button
            variant={optFilter === 'all' ? 'secondary' : 'ghost'}
            size="sm"
            className="h-7 text-xs px-2.5 font-medium"
            onClick={() => setOptFilter('all')}
          >
            All ({items.length})
          </Button>
          <Button
            variant={optFilter === 'pending' ? 'secondary' : 'ghost'}
            size="sm"
            className={`h-7 text-xs px-2.5 font-medium ${pendingItems.length > 0 ? 'text-amber-700 dark:text-amber-400 font-semibold' : ''}`}
            onClick={() => setOptFilter('pending')}
          >
            Pending ({pendingItems.length})
          </Button>
          <Button
            variant={optFilter === 'applied' ? 'secondary' : 'ghost'}
            size="sm"
            className="h-7 text-xs px-2.5 text-emerald-700 dark:text-emerald-400 font-semibold"
            onClick={() => setOptFilter('applied')}
          >
            Applied ({appliedItems.length})
          </Button>
        </div>
      </div>

      {sectionStatus === 'loading' ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="border border-border bg-card p-5 space-y-3 shadow-xs">
              <Skeleton className="h-5 w-20" />
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-16 w-full" />
              <div className="flex justify-between items-center pt-2">
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-8 w-20" />
              </div>
            </Card>
          ))}
        </div>
      ) : (!Array.isArray(items) || items.length === 0) ? (
        <EmptyState
          icon={Sparkles}
          title="Cloud Estate Fully Optimized"
          description="No idle, oversized, or unattached resource waste detected. All provisioned infrastructure is operating within target cost thresholds."
          className="my-6 py-12"
        />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title={optFilter === 'pending' ? 'All Recommendations Enacted' : 'No Enacted Optimizations'}
          description={
            optFilter === 'pending'
              ? 'Great job! All identified optimizations have been applied and tracked. Check back as new telemetry arrives.'
              : "No optimizations have been marked as enacted yet. Select 'Pending' to review open recommendations."
          }
          className="my-6 py-12"
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredItems.map((item: any) => {
            const done = appliedSet.has(item.id)
            return (
              <Card
                key={item.id}
                className={`border border-border bg-card transition-all duration-200 flex flex-col justify-between shadow-xs ${
                  done ? 'border-emerald-500/40 bg-emerald-500/[0.04]' : 'hover:border-border/90 hover:shadow-sm'
                }`}
              >
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge variant="outline" className="w-fit border-border text-xs font-mono font-medium">
                      {item.type}
                    </Badge>
                    {item.is_alternative ? (
                      <Badge variant="outline" className="border-amber-500/30 text-amber-700 dark:text-amber-300 bg-amber-500/10 text-[10px] font-semibold">
                        Alternative Strategy
                      </Badge>
                    ) : done ? (
                      <Badge variant="outline" className="border-emerald-500/30 text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 text-[10px] flex items-center gap-1 font-semibold">
                        <Check className="size-3" /> Enacted
                      </Badge>
                    ) : null}
                  </div>
                  <CardTitle className="pt-2 text-base font-bold text-foreground leading-snug">{item.title}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col justify-between flex-1">
                  <div>
                    <p className="min-h-10 text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
                    {item.conflict_note && (
                      <div className="mt-2.5 flex items-start gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-[11px] text-amber-800 dark:text-amber-200/90 leading-tight">
                        <AlertTriangle className="size-3.5 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
                        <span>{item.conflict_note}</span>
                      </div>
                    )}
                    {item.ai_rationale && item.ai_rationale !== item.desc && (
                      <div className="mt-3 rounded-lg border border-sky-500/30 bg-sky-500/10 p-2.5 text-xs text-sky-900 dark:text-sky-200">
                        <div className="mb-1 flex items-center gap-1.5 font-bold text-sky-700 dark:text-sky-300">
                          <Sparkles className="size-3.5" /> AI Architecture Rationale
                        </div>
                        {item.ai_rationale}
                      </div>
                    )}
                  </div>

                  <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
                    <div>
                      <div className="text-lg sm:text-xl font-bold text-emerald-700 dark:text-emerald-300 font-mono">
                        Saves {formatCurrency(Number(item.savings ?? 0), currency)}/mo
                      </div>
                      {item.is_alternative && (
                        <div className="text-[10px] text-muted-foreground">Alternative to primary plan</div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-xs text-sky-700 dark:text-sky-300 hover:bg-sky-500/10 px-2 font-medium"
                        onClick={() => handleSingleGitopsPr(item)}
                      >
                        <GitPullRequest className="mr-1 size-3" />GitOps PR
                      </Button>
                      <Button
                        size="sm"
                        variant={done ? 'secondary' : 'default'}
                        className={
                          done
                            ? 'border border-emerald-500/40 text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20 font-semibold shadow-xs'
                            : 'bg-sky-600 text-white hover:bg-sky-500 font-semibold shadow-xs'
                        }
                        onClick={() => toggleOptimization(item.id)}
                      >
                        {done ? (
                          <>
                            <Check className="mr-1 size-3.5 text-emerald-600 dark:text-emerald-400" />
                            Applied
                          </>
                        ) : (
                          'Enact'
                        )}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* GitOps PR Synthesis Modal */}
      <Dialog open={gitopsOpen} onOpenChange={setGitopsOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto border border-border bg-card text-foreground shadow-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              <GitBranch className="size-4 text-sky-600 dark:text-sky-400" />
              Autonomous GitOps Pull Request
            </DialogTitle>
            <DialogDescription>
              Production-ready Terraform HCL infrastructure diff created by CloudPulse GitOps engine.
            </DialogDescription>
          </DialogHeader>
          {gitopsLoading ? (
            <div className="flex flex-col items-center justify-center py-10 gap-3">
              <Loader2 className="size-8 animate-spin text-sky-600 dark:text-sky-400" />
              <span className="text-xs text-muted-foreground font-medium">Synthesizing Terraform HCL diff & creating Git branch...</span>
            </div>
          ) : gitopsPackage ? (
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="rounded-xl border border-border bg-muted/40 p-3 shadow-xs">
                  <span className="text-[11px] font-medium text-muted-foreground">Branch</span>
                  <div className="mt-1 font-mono text-xs font-semibold text-sky-700 dark:text-sky-300 truncate">
                    {gitopsPackage.branch_name}
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-muted/40 p-3 shadow-xs">
                  <span className="text-[11px] font-medium text-muted-foreground">Repository</span>
                  <div className="mt-1 font-mono text-xs font-semibold text-foreground truncate">
                    {gitopsPackage.repo_name}
                  </div>
                </div>
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 shadow-xs">
                  <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-300">Net Monthly Savings</span>
                  <div className="mt-1 text-xs font-bold text-emerald-700 dark:text-emerald-300 font-mono">
                    {formatCurrency(gitopsPackage.total_monthly_savings || gitopsPackage.monthly_savings, currency)}/mo
                  </div>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
                  <span className="flex items-center gap-1 font-medium"><FileCode className="size-3.5 text-sky-600 dark:text-sky-400" /> Terraform HCL Diff</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[11px]"
                    onClick={() => {
                      navigator.clipboard.writeText(gitopsPackage.diff || '')
                      setGitopsCopied(true)
                      setTimeout(() => setGitopsCopied(false), 2000)
                    }}
                  >
                    {gitopsCopied ? <Check className="mr-1 size-3 text-emerald-600 dark:text-emerald-400" /> : <Copy className="mr-1 size-3" />}
                    {gitopsCopied ? 'Copied' : 'Copy Diff'}
                  </Button>
                </div>
                <pre className="max-h-60 overflow-auto rounded-xl border border-border bg-slate-950 p-3.5 font-mono text-xs text-emerald-400 shadow-inner">
                  {gitopsPackage.diff || '# No HCL diff required'}
                </pre>
              </div>

              <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3 pt-2">
                <span className="text-xs text-muted-foreground">
                  Target: <span className="font-mono text-foreground font-semibold">{gitopsPackage.target_branch || 'main'}</span>
                </span>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setGitopsOpen(false)}>Close</Button>
                  <a
                    href={gitopsPackage.pull_request_url || gitopsPackage.pr_url || `https://github.com/${gitopsPackage.repo_name}/pull/new/${gitopsPackage.branch_name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button size="sm" className="w-full sm:w-auto bg-sky-600 text-white hover:bg-sky-500 font-semibold shadow-xs">
                      <ExternalLink className="mr-1.5 size-3.5" />View on GitHub
                    </Button>
                  </a>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-muted-foreground">
              Failed to generate GitOps package.
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={broadcastOpen} onOpenChange={setBroadcastOpen}>
        <DialogContent className="border border-border bg-card text-foreground sm:max-w-md max-h-[85vh] overflow-y-auto shadow-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              <Bell className="size-4 text-sky-600 dark:text-sky-400" />
              Broadcast FinOps Fleet Digest
            </DialogTitle>
            <DialogDescription>
              Dispatch the real-time cost optimization digest, health metrics, and 1-click GitOps buttons to your team channel.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-2">
            <div className="rounded-xl border border-border bg-muted/40 p-3 text-xs space-y-1.5 shadow-xs">
              <div className="font-semibold text-foreground">Digest Payload Preview:</div>
              <div className="flex justify-between text-muted-foreground"><span>Optimizations:</span><b className="text-foreground">{items.length} opportunities</b></div>
              <div className="flex justify-between text-muted-foreground"><span>Recoverable Savings:</span><b className="text-emerald-700 dark:text-emerald-300 font-mono font-bold">{formatCurrency(items.reduce((s: number, i: any) => s + Number(i.savings ?? 0), 0), currency)}/mo</b></div>
              <div className="flex justify-between text-muted-foreground"><span>Interactive Buttons:</span><span className="text-sky-700 dark:text-sky-300 font-medium">🚀 Batch PR, ⏰ Snooze</span></div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Select Destination Platform:</label>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Button
                  type="button"
                  variant={broadcastTarget === 'slack' ? 'default' : 'outline'}
                  className={broadcastTarget === 'slack' ? 'bg-sky-600 text-white hover:bg-sky-500 font-medium shadow-xs' : 'border-border bg-card hover:bg-muted'}
                  onClick={() => setBroadcastTarget('slack')}
                >
                  Slack (Block Kit)
                </Button>
                <Button
                  type="button"
                  variant={broadcastTarget === 'teams' ? 'default' : 'outline'}
                  className={broadcastTarget === 'teams' ? 'bg-indigo-600 text-white hover:bg-indigo-500 font-medium shadow-xs' : 'border-border bg-card hover:bg-muted'}
                  onClick={() => setBroadcastTarget('teams')}
                >
                  Microsoft Teams
                </Button>
              </div>
            </div>
            {broadcastResult && (
              <div className={`rounded-xl p-3 text-xs ${broadcastResult.startsWith('✅') ? 'bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-800 dark:text-rose-300 border border-rose-500/30'}`}>
                {broadcastResult}
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setBroadcastOpen(false)}>Cancel</Button>
              <Button
                size="sm"
                className="bg-sky-600 text-white hover:bg-sky-500 font-semibold shadow-xs"
                disabled={broadcasting}
                onClick={async () => {
                  setBroadcasting(true)
                  setBroadcastResult(null)
                  try {
                    const ep = broadcastTarget === 'slack' ? '/api/v2/notifications/slack/batch' : '/api/v2/notifications/teams/batch'
                    const res = await fetch(apiUrl(ep), {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ currency, rate: 84.0, channel: 'all-average' }),
                    })
                    const data = await res.json()
                    if (data.dispatched) {
                      setBroadcastResult(`✅ Broadcast delivered successfully to ${broadcastTarget === 'slack' ? 'Slack #all-average' : 'Microsoft Teams'}! Check your channel.`)
                    } else {
                      setBroadcastResult(`⚠️ Broadcast generated, but delivery failed. Please verify Slack credentials in Settings.`)
                    }
                  } catch (e: any) {
                    setBroadcastResult(`❌ Failed to broadcast: ${e.message || e}`)
                  } finally {
                    setBroadcasting(false)
                  }
                }}
              >
                {broadcasting ? <Loader2 className="mr-1 size-3.5 animate-spin" /> : <Send className="mr-1 size-3.5" />}
                Send Broadcast
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
export default OptimizationView
