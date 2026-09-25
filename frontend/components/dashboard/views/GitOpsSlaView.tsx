'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Activity,
  Check,
  Copy,
  ExternalLink,
  FileCode,
  GitBranch,
  GitPullRequest,
  History,
  Loader2,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SectionTitle } from '@/components/dashboard'
import { formatCurrency, formatInteger } from '@/lib/formatters'
import type { Currency, ComputeNode, OptimizationRecommendation } from '@/types/dashboard'

export function GitOpsSlaView({ currency = 'USD', apiUrl, items = [], applied, setApplied, nodes = [] }: any) {
  const runningNode = useMemo(() => {
    if (!Array.isArray(nodes) || nodes.length === 0) return null;
    return nodes.find((n: any) => n.state === 'running' || n.instance_state === 'running') || nodes[0];
  }, [nodes]);

  const defaultInstanceId = runningNode?.instance_id || 'i-07d01b00f95a4cc41';

  const [activeTab, setActiveTab] = useState<'watchdog' | 'audit'>('watchdog');
  const [watches, setWatches] = useState<any[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Enroll Watch state
  const [enrollModalOpen, setEnrollModalOpen] = useState(false);
  const [enrollResourceId, setEnrollResourceId] = useState(defaultInstanceId);
  const [enrollAction, setEnrollAction] = useState('migrate_graviton');
  const [enrolling, setEnrolling] = useState(false);

  useEffect(() => {
    if (defaultInstanceId && !enrollResourceId) {
      setEnrollResourceId(defaultInstanceId);
    }
  }, [defaultInstanceId]);

  // SLA Evaluation state
  const [evaluatingId, setEvaluatingId] = useState<string | null>(null);
  const [evalFeedback, setEvalFeedback] = useState<{ id: string; type: 'success' | 'warning' | 'error'; message: string } | null>(null);

  // Rollback state
  const [rollbackWatch, setRollbackWatch] = useState<any | null>(null);
  const [rollingBack, setRollingBack] = useState(false);
  const [rollbackPackage, setRollbackPackage] = useState<any | null>(null);

  // Batch PR state
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [batchResult, setBatchResult] = useState<any | null>(null);
  const [copiedBatch, setCopiedBatch] = useState(false);

  const handleEnrollWatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enrollResourceId.trim()) return;
    setEnrolling(true);
    try {
      const isStorage = enrollResourceId.startsWith('vol-') || enrollAction.includes('gp3');
      const res = await fetch(apiUrl('/api/v2/sla/watch'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resource_id: enrollResourceId.trim(),
          remediation_action: enrollAction,
          file_path: isStorage ? 'terraform/storage.tf' : 'terraform/compute.tf',
          previous_config: isStorage ? { volume_type: 'gp2', monthly_cost: 8.0 } : { instance_type: 't3.large', monthly_cost: 60.80 },
          applied_config: isStorage ? { volume_type: 'gp3', monthly_cost: 6.4 } : { instance_type: 't4g.large', monthly_cost: 48.64 },
          baseline_metrics: isStorage
            ? { p95_latency_ms: 6.5, error_rate_pct: 0.0, cpu_utilization_avg: 0.0 }
            : { p95_latency_ms: 38.0, error_rate_pct: 0.0, cpu_utilization_avg: 4.5 },
          duration_minutes: 60,
          max_latency_increase_pct: 15.0,
        }),
      });
      if (res.ok) {
        setEvalFeedback({
          id: 'enroll-success',
          type: 'success',
          message: `Successfully registered 60-Minute SLA Watchdog for ${enrollResourceId.trim()}. Active CloudWatch monitoring initiated.`,
        });
        setEnrollModalOpen(false);
        fetchSlaData();
      }
    } catch (err: any) {
      setEvalFeedback({
        id: 'enroll-error',
        type: 'error',
        message: err.message || 'Failed to enroll resource in SLA Watchdog',
      });
    } finally {
      setEnrolling(false);
    }
  };

  const fetchSlaData = useCallback(async () => {
    setLoading(true);
    try {
      const [wRes, aRes] = await Promise.all([
        fetch(apiUrl('/api/v2/sla/watches')),
        fetch(apiUrl('/api/v2/gitops/audit-log')),
      ]);
      if (wRes.ok) {
        const wd = await wRes.json();
        setWatches(Array.isArray(wd?.watches) ? wd.watches : []);
      }
      if (aRes.ok) {
        const ad = await aRes.json();
        setAuditLog(Array.isArray(ad?.audit_trail) ? ad.audit_trail : []);
      }
    } catch (err) {
      console.error('Failed to load SLA watchdog data:', err);
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    fetchSlaData();
  }, [fetchSlaData]);

  const handleEvaluate = async (watchId: string) => {
    setEvaluatingId(watchId);
    setEvalFeedback(null);
    try {
      const res = await fetch(apiUrl(`/api/v2/sla/watches/${watchId}/evaluate`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      if (res.ok) {
        const status = data.status || data.evaluation?.status;
        if (status === 'ROLLED_BACK') {
          setEvalFeedback({
            id: watchId,
            type: 'error',
            message: '🚨 SLA Breach Detected! Latency degraded > 15%. Autonomous safe git revert rollback PR triggered.',
          });
        } else if (status === 'DEGRADED') {
          setEvalFeedback({
            id: watchId,
            type: 'warning',
            message: '⚠️ Moderate latency degradation detected above baseline, continuing active 60-min watchdog.',
          });
        } else {
          setEvalFeedback({
            id: watchId,
            type: 'success',
            message: '✅ CloudWatch SLA Healthy: P95 latency and error rates remain well within the 15% safety threshold.',
          });
        }
        await fetchSlaData();
      } else {
        setEvalFeedback({ id: watchId, type: 'error', message: data.detail || 'Evaluation failed' });
      }
    } catch (err: any) {
      setEvalFeedback({ id: watchId, type: 'error', message: err.message || 'Evaluation error' });
    } finally {
      setEvaluatingId(null);
    }
  };

  const handleTriggerRollback = async (watch: any) => {
    setRollingBack(true);
    try {
      const res = await fetch(apiUrl(`/api/v2/sla/watches/${watch.watch_id}/rollback`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reasons: ['Manual operator rollback triggered from CloudPulse Dashboard'] }),
      });
      const data = await res.json();
      if (res.ok && data.rollback_pr) {
        setRollbackPackage(data.rollback_pr);
        await fetchSlaData();
      }
    } catch (err) {
      console.error('Failed to trigger rollback:', err);
    } finally {
      setRollingBack(false);
    }
  };

  const handleGenerateBatch = async () => {
    setBatchOpen(true);
    setBatchGenerating(true);
    setBatchResult(null);
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
      });
      if (res.ok) {
        setBatchResult(await res.json());
        await fetchSlaData();
      }
    } catch (err) {
      console.error('Batch generation failed:', err);
    } finally {
      setBatchGenerating(false);
    }
  };

  const healthyWatches = watches.filter(w => w.status === 'HEALTHY' || (!w.sla_breached && w.status !== 'ROLLED_BACK'));
  const breachedWatches = watches.filter(w => w.status === 'ROLLED_BACK' || w.sla_breached);

  return (
    <>
      <SectionTitle
        eyebrow="Safe Autonomous Ops"
        title="GitOps Autopilot & SLA Watchdog"
        description="Autonomous Terraform HCL PR generation across 5 resource vectors paired with 60-minute CloudWatch SLA watchdog monitoring."
        status={
          <Badge variant="outline" className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            60-min Rollback Guarantee
          </Badge>
        }
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchSlaData}
              disabled={loading}
              className="border-white/10 bg-white/5"
            >
              <RefreshCw className={`mr-1.5 size-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (!enrollResourceId && defaultInstanceId) setEnrollResourceId(defaultInstanceId);
                setEnrollModalOpen(true);
              }}
              className="border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10"
            >
              <Plus className="mr-1.5 size-3.5" /> Enroll Watch
            </Button>
            <Button
              size="sm"
              className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium"
              onClick={handleGenerateBatch}
            >
              <GitBranch className="mr-1.5 size-4" /> Synthesize Batch GitOps PR
            </Button>
          </div>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Active 60-Min Watches</span>
              <Activity className="size-4 text-cyan-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">{watches.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">Live monitored workloads</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Meeting SLA Targets</span>
              <ShieldCheck className="size-4 text-emerald-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-emerald-300">{healthyWatches.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">P95 latency degradation &lt; 15%</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Protected by Auto-Rollback</span>
              <RotateCcw className="size-4 text-purple-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-purple-300">{breachedWatches.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">Safe git revert PRs issued</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Total GitOps PRs</span>
              <GitPullRequest className="size-4 text-indigo-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-indigo-300">{auditLog.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">Audit log entries recorded</div>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={(v: any) => setActiveTab(v)}>
        <TabsList className="mb-4 bg-white/5 w-full sm:w-auto overflow-x-auto justify-start max-w-full">
          <TabsTrigger value="watchdog" className="flex items-center gap-1.5 text-xs whitespace-nowrap">
            <Activity className="size-3.5" />
            <span className="hidden sm:inline">60-Minute SLA Watchdog Tracker</span>
            <span className="sm:hidden">SLA Watchdog</span>
            <span>({watches.length})</span>
          </TabsTrigger>
          <TabsTrigger value="audit" className="flex items-center gap-1.5 text-xs whitespace-nowrap">
            <History className="size-3.5" />
            <span className="hidden sm:inline">GitOps Pull Request Audit Trail</span>
            <span className="sm:hidden">PR Audit</span>
            <span>({auditLog.length})</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="watchdog">
          <Card className="border-white/8 bg-card/70">
            <CardHeader>
              <div>
                <CardTitle className="text-base">CloudWatch Post-Remediation Telemetry Watchdog</CardTitle>
                <p className="text-xs text-muted-foreground mt-1">
                  Every automated remediation enters a 60-minute evaluation period. If P95 latency increases &gt;15%, CloudPulse generates an autonomous git revert PR.
                </p>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="py-12 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                  <Loader2 className="size-4 animate-spin text-cyan-400" /> Loading active SLA watches...
                </div>
              ) : watches.length === 0 ? (
                <div className="py-12 text-center text-xs text-muted-foreground">
                  No active SLA watches. Remediate or downsize an instance to launch a 60-minute watchdog.
                </div>
              ) : (
                <div className="space-y-4">
                  {evalFeedback && (
                    <div
                      className={`p-3 rounded-lg text-xs border ${
                        evalFeedback.type === 'success'
                          ? 'bg-emerald-400/10 text-emerald-300 border-emerald-400/20'
                          : evalFeedback.type === 'warning'
                          ? 'bg-amber-400/10 text-amber-300 border-amber-400/20'
                          : 'bg-red-400/10 text-red-300 border-red-400/20'
                      }`}
                    >
                      {evalFeedback.message}
                    </div>
                  )}

                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow className="border-white/8 hover:bg-transparent">
                          <TableHead className="text-xs">Resource ID</TableHead>
                          <TableHead className="text-xs">Remediation</TableHead>
                          <TableHead className="text-xs">Config Transition</TableHead>
                          <TableHead className="text-xs text-right">Baseline P95</TableHead>
                          <TableHead className="text-xs text-right">Observed P95</TableHead>
                          <TableHead className="text-xs text-right">Error Rate</TableHead>
                          <TableHead className="text-xs text-center">Status</TableHead>
                          <TableHead className="text-xs text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {watches.map((w: any) => {
                          const isBreached = w.status === 'ROLLED_BACK' || w.sla_breached;
                          const latencyDiffPct = w.baseline_metrics?.p95_latency_ms && w.current_metrics?.p95_latency_ms
                            ? (((w.current_metrics.p95_latency_ms - w.baseline_metrics.p95_latency_ms) / w.baseline_metrics.p95_latency_ms) * 100).toFixed(1)
                            : '0.0';
                          return (
                            <TableRow key={w.watch_id} className="border-white/8">
                              <TableCell className="font-mono text-xs font-semibold text-cyan-300">
                                {w.resource_id}
                                <div className="text-[10px] text-muted-foreground font-sans">{w.watch_id}</div>
                              </TableCell>
                              <TableCell className="text-xs capitalize">
                                <Badge variant="outline" className="border-white/10 text-[11px]">
                                  {w.remediation_action?.replace('_', ' ')}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-xs font-mono text-muted-foreground">
                                <span className="text-slate-400">{w.previous_config?.instance_type || 'original'}</span>
                                <span className="mx-1 text-cyan-400">→</span>
                                <span className="text-emerald-300 font-semibold">{w.applied_config?.instance_type || 'optimized'}</span>
                              </TableCell>
                              <TableCell className="text-right font-mono text-xs text-muted-foreground">
                                {w.baseline_metrics?.p95_latency_ms ? `${w.baseline_metrics.p95_latency_ms} ms` : 'N/A'}
                              </TableCell>
                              <TableCell className="text-right font-mono text-xs font-medium">
                                <span className={Number(latencyDiffPct) > 15 ? 'text-red-400' : 'text-emerald-300'}>
                                  {w.current_metrics?.p95_latency_ms ? `${w.current_metrics.p95_latency_ms} ms` : 'N/A'}
                                </span>
                                {latencyDiffPct !== '0.0' && (
                                  <span className={`ml-1 text-[10px] ${Number(latencyDiffPct) > 15 ? 'text-red-400' : 'text-slate-400'}`}>
                                    ({Number(latencyDiffPct) > 0 ? `+${latencyDiffPct}%` : `${latencyDiffPct}%`})
                                  </span>
                                )}
                              </TableCell>
                              <TableCell className="text-right font-mono text-xs text-muted-foreground">
                                {w.current_metrics?.error_rate_pct != null ? `${w.current_metrics.error_rate_pct}%` : '0.0%'}
                              </TableCell>
                              <TableCell className="text-center">
                                <Badge
                                  variant="outline"
                                  className={
                                    isBreached
                                      ? 'border-purple-400/30 bg-purple-400/10 text-purple-300'
                                      : w.status === 'DEGRADED'
                                      ? 'border-amber-400/30 bg-amber-400/10 text-amber-300'
                                      : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
                                  }
                                >
                                  {isBreached ? 'ROLLED BACK' : w.status || 'MONITORING'}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-right">
                                <div className="flex items-center justify-end gap-1.5">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-7 text-[11px] border-white/10 bg-white/5 hover:bg-cyan-400/10 hover:text-cyan-300"
                                    disabled={evaluatingId === w.watch_id}
                                    onClick={() => handleEvaluate(w.watch_id)}
                                  >
                                    {evaluatingId === w.watch_id ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Activity className="mr-1 size-3 text-cyan-400" />}
                                    Evaluate
                                  </Button>
                                  {w.rollback_pr ? (
                                    <Button
                                      variant="secondary"
                                      size="sm"
                                      className="h-7 text-[11px] bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30"
                                      onClick={() => {
                                        setRollbackPackage(w.rollback_pr);
                                      }}
                                    >
                                      <RotateCcw className="mr-1 size-3" /> Revert PR
                                    </Button>
                                  ) : (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="h-7 text-[11px] border-red-400/20 bg-red-400/5 text-red-300 hover:bg-red-400/15"
                                      onClick={() => {
                                        setRollbackWatch(w);
                                      }}
                                    >
                                      <RotateCcw className="mr-1 size-3" /> Rollback
                                    </Button>
                                  )}
                                </div>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit">
          <Card className="border-white/8 bg-card/70">
            <CardHeader>
              <CardTitle className="text-base">GitOps Infrastructure Pull Request Audit Trail</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                Full cryptographic history of all synthesized pull requests, branches, and approvals for compliance audits.
              </p>
            </CardHeader>
            <CardContent>
              {auditLog.length === 0 ? (
                <div className="py-12 text-center text-xs text-muted-foreground">
                  No GitOps PRs generated yet.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-white/8 hover:bg-transparent">
                        <TableHead className="text-xs">Timestamp</TableHead>
                        <TableHead className="text-xs">PR Title / Summary</TableHead>
                        <TableHead className="text-xs">Resource</TableHead>
                        <TableHead className="text-xs">Branch</TableHead>
                        <TableHead className="text-xs">Repository</TableHead>
                        <TableHead className="text-xs text-center">Status</TableHead>
                        <TableHead className="text-xs text-right">Monthly Impact</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {auditLog.map((log: any, idx: number) => {
                        const rawTime = log.created_at || log.timestamp;
                        const timeStr = rawTime
                          ? new Date(typeof rawTime === 'number' && rawTime < 1e11 ? rawTime * 1000 : rawTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                          : 'Recent';
                        const savingsVal = log.monthly_savings || log.estimated_monthly_savings || log.total_monthly_savings || 0;
                        const targetRes = log.resource_id || log.target_resource || (log.findings_count ? `${log.findings_count} resources` : 'multi-resource');
                        const isRollback = log.is_rollback || log.status === 'rolled_back' || log.status === 'rollback_pr_ready';

                        return (
                          <TableRow key={`${log.pr_id || idx}`} className="border-white/8 hover:bg-white/[0.02]">
                            <TableCell className="text-xs text-muted-foreground font-mono">
                              {timeStr}
                            </TableCell>
                            <TableCell className="text-xs font-medium max-w-xs">
                              {log.pull_request_url ? (
                                <a
                                  href={log.pull_request_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-indigo-300 hover:text-indigo-200 underline decoration-indigo-500/30 flex items-center gap-1"
                                >
                                  <span className="truncate">{log.title || log.pr_title || 'Autonomous Optimization PR'}</span>
                                  <ExternalLink className="size-3 shrink-0" />
                                </a>
                              ) : (
                                <span className="truncate">{log.title || log.pr_title || 'Autonomous Optimization PR'}</span>
                              )}
                            </TableCell>
                            <TableCell className="text-xs font-mono text-cyan-300">
                              {targetRes}
                            </TableCell>
                            <TableCell className="text-xs font-mono text-slate-400">
                              {log.branch_name || 'main'}
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {log.repo_name || 'infrastructure/aws-workloads'}
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge
                                variant="outline"
                                className={
                                  isRollback
                                    ? 'border-purple-400/30 bg-purple-500/10 text-purple-300 text-[10px]'
                                    : 'border-emerald-400/30 bg-emerald-500/10 text-emerald-300 text-[10px]'
                                }
                              >
                                {isRollback ? 'ROLLBACK PR' : (log.status || 'PR_READY')}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right text-xs font-semibold text-emerald-300">
                              {savingsVal > 0 ? `Saves ${formatCurrency(savingsVal, currency)}` : (isRollback ? 'Safety Revert' : 'Optimized')}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Manual Rollback Trigger Dialog */}
      <Dialog open={!!rollbackWatch} onOpenChange={() => setRollbackWatch(null)}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto border-white/10 bg-slate-950 text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base text-red-300">
              <RotateCcw className="size-4" /> Trigger Safe Rollback PR
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to revert the optimization on <span className="font-mono text-foreground font-semibold">{rollbackWatch?.resource_id}</span>?
            </DialogDescription>
          </DialogHeader>
          <div className="py-3 text-xs text-muted-foreground space-y-2">
            <p>
              CloudPulse will immediately open a Git revert Pull Request to restore the workload configuration from <span className="text-emerald-300 font-mono">{rollbackWatch?.applied_config?.instance_type}</span> back to <span className="text-cyan-300 font-mono">{rollbackWatch?.previous_config?.instance_type}</span>.
            </p>
          </div>
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setRollbackWatch(null)}>Cancel</Button>
            <Button
              size="sm"
              className="bg-red-500 hover:bg-red-600 text-white font-medium"
              disabled={rollingBack}
              onClick={async () => {
                if (rollbackWatch) {
                  await handleTriggerRollback(rollbackWatch);
                  setRollbackWatch(null);
                }
              }}
            >
              {rollingBack ? <Loader2 className="mr-1 size-3.5 animate-spin" /> : <RotateCcw className="mr-1 size-3.5" />}
              Generate Revert PR
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Rollback Details Modal */}
      <Dialog open={!!rollbackPackage} onOpenChange={() => setRollbackPackage(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto border-white/10 bg-slate-950 text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base text-purple-300">
              <RotateCcw className="size-4" /> Automated Safe Revert Pull Request Ready
            </DialogTitle>
            <DialogDescription>
              A safety pull request has been synthesized to protect production performance SLA.
            </DialogDescription>
          </DialogHeader>
          {rollbackPackage && (
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="rounded-lg border border-white/8 bg-white/5 p-3">
                  <span className="text-[11px] text-muted-foreground">Rollback Branch</span>
                  <div className="mt-1 font-mono text-xs font-semibold text-purple-300 truncate">
                    {rollbackPackage.branch_name}
                  </div>
                </div>
                <div className="rounded-lg border border-white/8 bg-white/5 p-3">
                  <span className="text-[11px] text-muted-foreground">Restored Configuration</span>
                  <div className="mt-1 font-mono text-xs font-semibold text-emerald-300 truncate">
                    {rollbackPackage.restored_config?.instance_type || 'Original Spec'}
                  </div>
                </div>
              </div>

              <div>
                <span className="text-xs text-muted-foreground block mb-1.5 font-medium">Terraform Git Revert Diff:</span>
                <pre className="max-h-60 overflow-auto rounded-lg border border-white/10 bg-black/60 p-3.5 font-mono text-xs text-red-300">
                  {rollbackPackage.revert_diff || rollbackPackage.diff || '# Revert diff generated'}
                </pre>
              </div>

              <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3 pt-2">
                <span className="text-xs text-muted-foreground">
                  Target: <span className="font-mono text-foreground">main</span>
                </span>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setRollbackPackage(null)}>Close</Button>
                  <a
                    href={rollbackPackage.pull_request_url || `https://github.com/infrastructure/aws-workloads/pull/new/${rollbackPackage.branch_name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button size="sm" className="w-full sm:w-auto bg-purple-600 hover:bg-purple-500 text-white font-medium">
                      <ExternalLink className="mr-1.5 size-3.5" /> View Rollback on GitHub
                    </Button>
                  </a>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Batch GitOps PR Modal */}
      <Dialog open={batchOpen} onOpenChange={setBatchOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto border-white/10 bg-slate-950 text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base text-indigo-300">
              <GitBranch className="size-4" /> Multi-Resource Batch GitOps Pull Request
            </DialogTitle>
            <DialogDescription>
              Synthesized Terraform changes across all 5 resource vectors into a unified Pull Request.
            </DialogDescription>
          </DialogHeader>
          {batchGenerating ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3">
              <Loader2 className="size-8 animate-spin text-indigo-400" />
              <span className="text-xs text-muted-foreground">Synthesizing batch Terraform changes across all 5 vectors...</span>
            </div>
          ) : batchResult ? (
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="rounded-lg border border-white/8 bg-white/5 p-3">
                  <span className="text-[11px] text-muted-foreground">Branch</span>
                  <div className="mt-1 font-mono text-xs font-semibold text-cyan-300 truncate">
                    {batchResult.branch_name}
                  </div>
                </div>
                <div className="rounded-lg border border-white/8 bg-white/5 p-3">
                  <span className="text-[11px] text-muted-foreground">Monthly Net Savings</span>
                  <div className="mt-1 text-xs font-bold text-emerald-300">
                    {formatCurrency(batchResult.total_monthly_savings, currency)}/mo
                  </div>
                </div>
                <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-3">
                  <span className="text-[11px] text-emerald-300">Annual Run-Rate ROI</span>
                  <div className="mt-1 text-xs font-bold text-emerald-300">
                    {formatCurrency(batchResult.total_annual_savings, currency)}/yr
                  </div>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
                  <span className="flex items-center gap-1"><FileCode className="size-3.5 text-indigo-400" /> Batch Terraform HCL Diff</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[11px]"
                    onClick={() => {
                      navigator.clipboard.writeText(batchResult.diff || '');
                      setCopiedBatch(true);
                      setTimeout(() => setCopiedBatch(false), 2000);
                    }}
                  >
                    {copiedBatch ? <Check className="mr-1 size-3 text-emerald-400" /> : <Copy className="mr-1 size-3" />}
                    {copiedBatch ? 'Copied' : 'Copy Diff'}
                  </Button>
                </div>
                <pre className="max-h-60 overflow-auto rounded-lg border border-white/10 bg-black/60 p-3.5 font-mono text-xs text-emerald-300">
                  {batchResult.diff || '# Batch diff synthesized'}
                </pre>
              </div>

              <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3 pt-2">
                <span className="text-xs text-muted-foreground">
                  Target: <span className="font-mono text-foreground">{batchResult.target_branch || 'main'}</span>
                </span>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setBatchOpen(false)}>Close</Button>
                  <a
                    href={batchResult.pull_request_url || `https://github.com/${batchResult.repo_name || 'infrastructure/aws-workloads'}/pull/new/${batchResult.branch_name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button size="sm" className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-500 text-white font-medium">
                      <ExternalLink className="mr-1.5 size-3.5" /> View Batch PR on GitHub
                    </Button>
                  </a>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-muted-foreground">
              Failed to generate batch GitOps package.
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Enroll SLA Watch Modal */}
      <Dialog open={enrollModalOpen} onOpenChange={setEnrollModalOpen}>
        <DialogContent className="border-white/10 bg-slate-900 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold flex items-center gap-2">
              <Activity className="size-4 text-cyan-400" />
              Enroll in 60-Minute SLA Watchdog
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Launches automated post-remediation CloudWatch P95 latency & error monitoring with zero-downtime rollback protection.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleEnrollWatch} className="space-y-4 pt-2">
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-slate-300">Target AWS Resource</label>
                {nodes && nodes.length > 0 && (
                  <span className="text-[10px] text-cyan-400">
                    Discovered: {nodes.find((n: any) => n.instance_id === enrollResourceId)?.name || defaultInstanceId}
                  </span>
                )}
              </div>
              {nodes && nodes.length > 0 ? (
                <div className="space-y-1.5">
                  <Select
                    value={enrollResourceId || defaultInstanceId}
                    onValueChange={(val) => { if (val) setEnrollResourceId(val); }}
                  >
                    <SelectTrigger className="bg-white/5 border-white/10 text-xs font-mono">
                      <SelectValue placeholder="Select instance..." />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-900 border-white/10 text-white text-xs">
                      {nodes.map((n: any) => (
                        <SelectItem key={n.instance_id} value={n.instance_id}>
                          {n.instance_id} ({n.name || 'EC2'} · {n.state})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder={`e.g. ${defaultInstanceId}`}
                    value={enrollResourceId}
                    onChange={(e) => setEnrollResourceId(e.target.value)}
                    className="bg-white/5 border-white/10 text-xs font-mono"
                    required
                  />
                </div>
              ) : (
                <Input
                  placeholder={`e.g. ${defaultInstanceId}`}
                  value={enrollResourceId}
                  onChange={(e) => setEnrollResourceId(e.target.value)}
                  className="bg-white/5 border-white/10 text-xs font-mono"
                  required
                />
              )}
            </div>

            <div>
              <label className="text-xs font-medium text-slate-300">Remediation Action Type</label>
              <Select value={enrollAction} onValueChange={(val) => { if (val) setEnrollAction(val); }}>
                <SelectTrigger className="mt-1 bg-white/5 border-white/10 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-white/10 text-white text-xs">
                  <SelectItem value="migrate_graviton">Migrate to AWS Graviton (t4g/m7g)</SelectItem>
                  <SelectItem value="downsize">Downsize Idle Compute</SelectItem>
                  <SelectItem value="upgrade_gp3">Modernize Storage gp2 -&gt; gp3</SelectItem>
                  <SelectItem value="release_eip">Release Unattached Elastic IP</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-3 text-xs text-cyan-200">
              🛡️ <strong>Safety Guarantee:</strong> During the 60-minute window, if P95 latency degrades by &gt;15%, CloudPulse automatically generates an autonomous git revert PR.
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setEnrollModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={enrolling} className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-medium">
                {enrolling ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Activity className="mr-1.5 size-3.5" />}
                Enroll in Watchdog
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}


export default GitOpsSlaView
