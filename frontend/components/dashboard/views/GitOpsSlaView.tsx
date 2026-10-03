'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Activity,
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  FileCode,
  FileText,
  Flame,
  Gauge,
  GitBranch,
  GitPullRequest,
  History,
  Loader2,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  TrendingDown,
  TrendingUp,
  XCircle,
  Zap,
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

  const defaultInstanceId = runningNode?.instance_id || '';

  const [activeTab, setActiveTab] = useState<'watchdog' | 'audit' | 'sre'>('watchdog');
  const [watches, setWatches] = useState<any[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Google SRE Golden Signals & Error Budget state
  const [sreSignals, setSreSignals] = useState<any>(null);
  const [sreBudget, setSreBudget] = useState<any>(null);
  const [sreCanary, setSreCanary] = useState<any>(null);
  const [sreLoading, setSreLoading] = useState(false);

  // Blameless Postmortem state
  const [postmortemOpen, setPostmortemOpen] = useState(false);
  const [postmortemLoading, setPostmortemLoading] = useState(false);
  const [postmortemData, setPostmortemData] = useState<any>(null);
  const [postmortemCopied, setPostmortemCopied] = useState(false);
  const [postmortemTitle, setPostmortemTitle] = useState('P95 Tail Latency Regression on Downsized EC2 Cluster');
  const [postmortemSeverity, setPostmortemSeverity] = useState('P1');
  const [postmortemIncidentId, setPostmortemIncidentId] = useState('');

  // Enroll Watch state
  const [enrollModalOpen, setEnrollModalOpen] = useState(false);
  const [enrollResourceId, setEnrollResourceId] = useState(defaultInstanceId);
  const [enrollAction, setEnrollAction] = useState('migrate_graviton');
  const [enrolling, setEnrolling] = useState(false);

  useEffect(() => {
    if (defaultInstanceId && !enrollResourceId) {
      setEnrollResourceId(defaultInstanceId);
    }
  }, [defaultInstanceId, enrollResourceId]);

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

  const fetchSreData = useCallback(async () => {
    setSreLoading(true);
    try {
      const [sigRes, budRes, canRes] = await Promise.allSettled([
        fetch(apiUrl('/api/v2/sre/golden-signals')),
        fetch(apiUrl('/api/v2/sre/error-budget')),
        fetch(apiUrl('/api/v2/sre/canary-analysis')),
      ]);
      if (sigRes.status === 'fulfilled' && sigRes.value.ok) {
        setSreSignals(await sigRes.value.json());
      }
      if (budRes.status === 'fulfilled' && budRes.value.ok) {
        setSreBudget(await budRes.value.json());
      }
      if (canRes.status === 'fulfilled' && canRes.value.ok) {
        setSreCanary(await canRes.value.json());
      }
    } catch (err) {
      console.error('Failed to load SRE telemetry:', err);
    } finally {
      setSreLoading(false);
    }
  }, [apiUrl]);

  const handleGeneratePostmortem = async () => {
    setPostmortemLoading(true);
    try {
      const res = await fetch(apiUrl('/api/v2/sre/postmortem/generate'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          incident_id: postmortemIncidentId.trim() || undefined,
          title: postmortemTitle.trim() || 'P95 Tail Latency Regression on Downsized EC2 Cluster',
          severity: postmortemSeverity,
          duration_minutes: 24,
          lead_sre: 'CloudPulse Autopilot SRE',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setPostmortemData(data.postmortem);
      }
    } catch (err) {
      console.error('Failed to generate postmortem:', err);
    } finally {
      setPostmortemLoading(false);
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
    fetchSreData();
  }, [fetchSlaData, fetchSreData]);

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
          <Badge variant="outline" className="border-border bg-muted text-foreground">
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
              className="border-border bg-background text-foreground hover:bg-muted"
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
              className="border-border bg-background text-foreground hover:bg-muted"
            >
              <Plus className="mr-1.5 size-3.5" /> Enroll Watch
            </Button>
            <Button
              size="sm"
              className="bg-primary text-primary-foreground hover:opacity-90 font-medium"
              onClick={handleGenerateBatch}
            >
              <GitBranch className="mr-1.5 size-4" /> Synthesize Batch GitOps PR
            </Button>
          </div>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-border bg-card">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Active 60-Min Watches</span>
              <Activity className="size-4 text-foreground" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">{watches.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">Live monitored workloads</div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Meeting SLA Targets</span>
              <ShieldCheck className="size-4 text-foreground" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">{healthyWatches.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">P95 latency degradation &lt; 15%</div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Protected by Auto-Rollback</span>
              <RotateCcw className="size-4 text-foreground" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">{breachedWatches.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">Safe git revert PRs issued</div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Total GitOps PRs</span>
              <GitPullRequest className="size-4 text-foreground" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">{auditLog.length}</div>
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
          <TabsTrigger value="sre" className="flex items-center gap-1.5 text-xs whitespace-nowrap">
            <Gauge className="size-3.5" />
            <span className="hidden sm:inline">Google SRE & Golden Signals</span>
            <span className="sm:hidden">Google SRE</span>
            {sreSignals?.overall_health && (
              <span
                className={`ml-1 size-2 rounded-full ${
                  sreSignals.overall_health === 'HEALTHY' ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'
                }`}
              />
            )}
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
                        <TableRow className="border-border hover:bg-transparent">
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
                            <TableRow key={w.watch_id} className="border-border hover:bg-muted/50">
                              <TableCell className="font-mono text-xs font-semibold text-foreground">
                                {w.resource_id}
                                <div className="text-[10px] text-muted-foreground font-sans">{w.watch_id}</div>
                              </TableCell>
                              <TableCell className="text-xs capitalize">
                                <Badge variant="outline" className="border-border bg-muted text-foreground text-[11px]">
                                  {w.remediation_action?.replace('_', ' ')}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-xs font-mono text-muted-foreground">
                                <span className="text-muted-foreground">{w.previous_config?.instance_type || 'original'}</span>
                                <span className="mx-1 text-foreground">→</span>
                                <span className="text-foreground font-semibold">{w.applied_config?.instance_type || 'optimized'}</span>
                              </TableCell>
                              <TableCell className="text-right font-mono text-xs text-muted-foreground">
                                {w.baseline_metrics?.p95_latency_ms ? `${w.baseline_metrics.p95_latency_ms} ms` : 'N/A'}
                              </TableCell>
                              <TableCell className="text-right font-mono text-xs font-medium text-foreground">
                                <span>
                                  {w.current_metrics?.p95_latency_ms ? `${w.current_metrics.p95_latency_ms} ms` : 'N/A'}
                                </span>
                                {latencyDiffPct !== '0.0' && (
                                  <span className="ml-1 text-[10px] text-muted-foreground">
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
                                      ? 'border-border bg-muted text-muted-foreground line-through'
                                      : 'border-border bg-muted text-foreground'
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
                                    className="h-7 text-[11px] border-border bg-background text-foreground hover:bg-muted"
                                    disabled={evaluatingId === w.watch_id}
                                    onClick={() => handleEvaluate(w.watch_id)}
                                  >
                                    {evaluatingId === w.watch_id ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Activity className="mr-1 size-3 text-foreground" />}
                                    Evaluate
                                  </Button>
                                  {w.rollback_pr ? (
                                    <Button
                                      size="sm"
                                      className="h-7 text-[11px] bg-primary text-primary-foreground hover:opacity-90 font-medium"
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
                                      className="h-7 text-[11px] border-border bg-background text-foreground hover:bg-muted"
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
          <Card className="border-border bg-card">
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
                      <TableRow className="border-border hover:bg-transparent">
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
                          <TableRow key={`${log.pr_id || idx}`} className="border-border hover:bg-muted/50">
                            <TableCell className="text-xs text-muted-foreground font-mono">
                              {timeStr}
                            </TableCell>
                            <TableCell className="text-xs font-medium max-w-xs">
                              {log.pull_request_url ? (
                                <a
                                  href={log.pull_request_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-foreground hover:underline flex items-center gap-1"
                                >
                                  <span className="truncate">{log.title || log.pr_title || 'Autonomous Optimization PR'}</span>
                                  <ExternalLink className="size-3 shrink-0" />
                                </a>
                              ) : (
                                <span className="truncate">{log.title || log.pr_title || 'Autonomous Optimization PR'}</span>
                              )}
                            </TableCell>
                            <TableCell className="text-xs font-mono font-semibold text-foreground">
                              {targetRes}
                            </TableCell>
                            <TableCell className="text-xs font-mono text-muted-foreground">
                              {log.branch_name || 'main'}
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {log.repo_name || 'infrastructure/aws-workloads'}
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge
                                variant="outline"
                                className="border-border bg-muted text-foreground text-[10px]"
                              >
                                {isRollback ? 'ROLLBACK PR' : (log.status || 'PR_READY')}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right text-xs font-semibold text-foreground">
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

        <TabsContent value="sre">
          <div className="space-y-6">
            {/* Header & Quick Actions */}
            <Card className="border-border bg-card">
              <CardHeader className="p-5 pb-3">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className="border-border bg-muted text-foreground text-[10px]">
                        Google SRE Standards
                      </Badge>
                      <Badge
                        variant="outline"
                        className={
                          sreSignals?.overall_health === 'HEALTHY'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-[10px]'
                            : 'border-amber-500/30 bg-amber-500/10 text-amber-400 text-[10px]'
                        }
                      >
                        {sreSignals?.overall_health || 'HEALTHY'}
                      </Badge>
                    </div>
                    <CardTitle className="text-base">Four Golden Signals & Error Budget Guardrails</CardTitle>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Tail latency distribution (P50/P90/P95/P99), Multi-Window Multi-Burn-Rate Error Budget tracking (Google SRE Ch. 4), Automated Canary Analysis (ACA), and autonomous deployment freeze guardrails.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={fetchSreData}
                      disabled={sreLoading}
                      className="border-border bg-background text-foreground hover:bg-muted text-xs h-8"
                    >
                      <RefreshCw className={`mr-1.5 size-3.5 ${sreLoading ? 'animate-spin' : ''}`} /> Refresh Telemetry
                    </Button>
                    <Button
                      size="sm"
                      className="bg-primary text-primary-foreground hover:opacity-90 font-medium text-xs h-8"
                      onClick={() => {
                        setPostmortemOpen(true);
                        if (!postmortemData) {
                          handleGeneratePostmortem();
                        }
                      }}
                    >
                      <FileText className="mr-1.5 size-3.5" /> Blameless Postmortem (Ch. 15)
                    </Button>
                  </div>
                </div>
              </CardHeader>
            </Card>

            {/* The Four Golden Signals */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {/* 1. Latency */}
              <Card className="border-border bg-card">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                      <Clock className="size-3.5 text-foreground" /> Latency (Tail Distribution)
                    </span>
                    <Badge variant="outline" className="text-[10px] border-border bg-muted text-foreground">
                      {sreSignals?.latency?.unit || 'ms'}
                    </Badge>
                  </div>
                  <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-foreground">
                      {sreSignals?.latency?.p95_ms ?? 38.0}
                    </span>
                    <span className="text-xs text-muted-foreground">P95 ms</span>
                  </div>
                  <div className="mt-3 pt-3 border-t border-border grid grid-cols-4 gap-1 text-center font-mono">
                    <div className="p-1 rounded bg-muted/60">
                      <div className="text-[9px] text-muted-foreground uppercase">P50</div>
                      <div className="text-[11px] font-semibold text-foreground">
                        {sreSignals?.latency?.p50_ms ?? 12.4}
                      </div>
                    </div>
                    <div className="p-1 rounded bg-muted/60">
                      <div className="text-[9px] text-muted-foreground uppercase">P90</div>
                      <div className="text-[11px] font-semibold text-foreground">
                        {sreSignals?.latency?.p90_ms ?? 24.1}
                      </div>
                    </div>
                    <div className="p-1 rounded bg-muted/60">
                      <div className="text-[9px] text-muted-foreground uppercase">P95</div>
                      <div className="text-[11px] font-semibold text-foreground">
                        {sreSignals?.latency?.p95_ms ?? 38.0}
                      </div>
                    </div>
                    <div className="p-1 rounded bg-muted/60">
                      <div className="text-[9px] text-muted-foreground uppercase">P99</div>
                      <div className="text-[11px] font-semibold text-foreground">
                        {sreSignals?.latency?.p99_ms ?? 72.5}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 2. Traffic */}
              <Card className="border-border bg-card">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                      <Zap className="size-3.5 text-foreground" /> Traffic (Demand Throughput)
                    </span>
                    <Badge variant="outline" className="text-[10px] border-border bg-muted text-foreground">
                      RPS & IOPS
                    </Badge>
                  </div>
                  <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-foreground">
                      {sreSignals?.traffic?.rps ?? 245.8}
                    </span>
                    <span className="text-xs text-muted-foreground">req/sec</span>
                  </div>
                  <div className="mt-3 pt-3 border-t border-border grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <div className="text-[10px] text-muted-foreground">Active Conns</div>
                      <div className="font-mono font-semibold text-foreground mt-0.5">
                        {formatInteger(sreSignals?.traffic?.active_connections ?? 1420)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground">Storage Throughput</div>
                      <div className="font-mono font-semibold text-foreground mt-0.5">
                        {formatInteger(sreSignals?.traffic?.iops ?? 3120)} IOPS
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 3. Errors */}
              <Card className="border-border bg-card">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                      <AlertTriangle className="size-3.5 text-foreground" /> Errors (Failure Rate)
                    </span>
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${
                        (sreSignals?.errors?.rate_pct ?? 0.02) <= 0.1
                          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                          : 'border-red-500/30 bg-red-500/10 text-red-400'
                      }`}
                    >
                      {(sreSignals?.errors?.rate_pct ?? 0.02) <= 0.1 ? 'Target Met' : 'Breach'}
                    </Badge>
                  </div>
                  <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-foreground">
                      {sreSignals?.errors?.rate_pct ?? 0.02}%
                    </span>
                    <span className="text-xs text-muted-foreground">&lt; 0.10% target</span>
                  </div>
                  <div className="mt-3 pt-3 border-t border-border grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <div className="text-[10px] text-muted-foreground">5xx Server Errors</div>
                      <div className="font-mono font-semibold text-foreground mt-0.5">
                        {sreSignals?.errors?.['5xx_count'] ?? 2}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground">4xx Client Errors</div>
                      <div className="font-mono font-semibold text-foreground mt-0.5">
                        {sreSignals?.errors?.['4xx_count'] ?? 38}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 4. Saturation */}
              <Card className="border-border bg-card">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                      <Sliders className="size-3.5 text-foreground" /> Saturation & Headroom
                    </span>
                    <Badge variant="outline" className="text-[10px] border-border bg-muted text-foreground">
                      {sreSignals?.saturation?.headroom_pct ?? 58.0}% Headroom
                    </Badge>
                  </div>
                  <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-foreground">
                      {sreSignals?.saturation?.overall_saturation_pct ?? 42.0}%
                    </span>
                    <span className="text-xs text-muted-foreground">system utilization</span>
                  </div>
                  <div className="mt-3 pt-3 border-t border-border grid grid-cols-3 gap-1 text-center font-mono">
                    <div className="p-1 rounded bg-muted/60">
                      <div className="text-[9px] text-muted-foreground uppercase">CPU</div>
                      <div className="text-[11px] font-semibold text-foreground">
                        {sreSignals?.saturation?.cpu_pct ?? 38.5}%
                      </div>
                    </div>
                    <div className="p-1 rounded bg-muted/60">
                      <div className="text-[9px] text-muted-foreground uppercase">Mem</div>
                      <div className="text-[11px] font-semibold text-foreground">
                        {sreSignals?.saturation?.memory_pct ?? 54.2}%
                      </div>
                    </div>
                    <div className="p-1 rounded bg-muted/60">
                      <div className="text-[9px] text-muted-foreground uppercase">Disk</div>
                      <div className="text-[11px] font-semibold text-foreground">
                        {sreSignals?.saturation?.disk_io_pct ?? 32.0}%
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Error Budget & Burn Rate Section */}
            <Card className="border-border bg-card">
              <CardHeader className="p-5 pb-3 border-b border-border">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Flame className="size-4 text-foreground" /> Multi-Window Multi-Burn-Rate Error Budget
                    </CardTitle>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      30-Day Rolling Window targeting {sreBudget?.slo_target_pct ?? 99.9}% Availability SLO. Evaluates consumption velocity across multiple lookback windows.
                    </p>
                  </div>
                  <Badge variant="outline" className="border-border bg-muted text-foreground text-xs self-start sm:self-auto">
                    Current Availability: {sreBudget?.current_availability_pct ?? 99.975}%
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-5 space-y-5">
                {/* Budget Progress Meter */}
                <div>
                  <div className="flex items-center justify-between text-xs mb-2">
                    <span className="font-medium text-foreground">Remaining Error Budget</span>
                    <span className="font-mono font-bold text-foreground">
                      {sreBudget?.budget_remaining_pct ?? 75.0}% Remaining
                      <span className="text-muted-foreground font-normal ml-1.5">
                        ({formatInteger(sreBudget?.budget_remaining_bad_events ?? 750)} / {formatInteger(sreBudget?.budget_total_allowed_bad_events ?? 1000)} allowed bad events)
                      </span>
                    </span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-3 overflow-hidden border border-border">
                    <div
                      className={`h-full transition-all duration-500 rounded-full ${
                        (sreBudget?.budget_remaining_pct ?? 75.0) > 50
                          ? 'bg-emerald-500'
                          : (sreBudget?.budget_remaining_pct ?? 75.0) > 20
                          ? 'bg-amber-500'
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.max(0, Math.min(100, sreBudget?.budget_remaining_pct ?? 75.0))}%` }}
                    />
                  </div>
                </div>

                {/* 4-Window Burn Rate Breakdown */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3.5 rounded-lg border border-border bg-muted/40">
                    <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                      <span>1-Hour Burn Rate</span>
                      <Badge variant="outline" className="text-[9px] border-border bg-muted">Limit: 14.4x</Badge>
                    </div>
                    <div className="text-xl font-bold font-mono text-foreground">
                      {sreBudget?.burn_rate_1h ?? 1.2}x
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1">
                      {sreBudget?.alert_status?.fast_burn_alert ? '🚨 Fast burn alert' : 'Steady state consumption'}
                    </div>
                  </div>

                  <div className="p-3.5 rounded-lg border border-border bg-muted/40">
                    <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                      <span>6-Hour Burn Rate</span>
                      <Badge variant="outline" className="text-[9px] border-border bg-muted">Limit: 6.0x</Badge>
                    </div>
                    <div className="text-xl font-bold font-mono text-foreground">
                      {sreBudget?.burn_rate_6h ?? 0.8}x
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1">
                      {sreBudget?.alert_status?.slow_burn_alert ? '⚠️ Slow burn alert' : 'Within budget forecast'}
                    </div>
                  </div>

                  <div className="p-3.5 rounded-lg border border-border bg-muted/40">
                    <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                      <span>24-Hour Burn Rate</span>
                      <Badge variant="outline" className="text-[9px] border-border bg-muted">Limit: 3.0x</Badge>
                    </div>
                    <div className="text-xl font-bold font-mono text-foreground">
                      {sreBudget?.burn_rate_24h ?? 0.5}x
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1">Daily trend trajectory</div>
                  </div>

                  <div className="p-3.5 rounded-lg border border-border bg-muted/40">
                    <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                      <span>3-Day Burn Rate</span>
                      <Badge variant="outline" className="text-[9px] border-border bg-muted">Limit: 1.0x</Badge>
                    </div>
                    <div className="text-xl font-bold font-mono text-foreground">
                      {sreBudget?.burn_rate_3d ?? 0.3}x
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1">Multi-day rolling mean</div>
                  </div>
                </div>

                {/* SRE Deployment Freeze Guardrail Alert */}
                {sreBudget?.deployment_freeze_recommended ? (
                  <div className="p-4 rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 flex items-start gap-3">
                    <ShieldAlert className="size-5 shrink-0 text-red-400 mt-0.5" />
                    <div>
                      <div className="font-semibold text-sm text-red-200">
                        🚨 AUTOMATED DEPLOYMENT FREEZE ENFORCED
                      </div>
                      <p className="text-xs text-red-300 mt-0.5">
                        Google SRE guardrail triggered: The error budget burn rate has breached safety limits. All non-emergency production GitOps PR merges are locked until system stability and error budget replenish above safety thresholds.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 flex items-start gap-3">
                    <ShieldCheck className="size-5 shrink-0 text-emerald-400 mt-0.5" />
                    <div>
                      <div className="font-semibold text-sm text-emerald-200">
                        ✅ DEPLOYMENT FREEZE GUARDRAIL INACTIVE
                      </div>
                      <p className="text-xs text-emerald-300 mt-0.5">
                        Error budget consumption is healthy and within Google SRE limits. Continuous GitOps autopilot and workload rightsizing PRs are actively authorized for production deployment.
                      </p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Automated Canary Analysis (ACA) Scoring */}
            <Card className="border-border bg-card">
              <CardHeader className="p-5 pb-3 border-b border-border">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <CheckCircle2 className="size-4 text-foreground" /> Automated Canary Analysis (ACA) Verification
                    </CardTitle>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Statistical telemetry comparison between baseline production workload vs rightsized canary instance.
                    </p>
                  </div>
                  <Badge
                    variant="outline"
                    className={
                      sreCanary?.decision === 'PROMOTE'
                        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400 font-semibold'
                        : 'border-red-500/30 bg-red-500/10 text-red-400 font-semibold'
                    }
                  >
                    DECISION: {sreCanary?.decision || 'PROMOTE'}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-5 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="p-3.5 rounded-lg border border-border bg-muted/40">
                    <div className="text-[11px] text-muted-foreground">Baseline Spec</div>
                    <div className="mt-1 font-mono text-xs font-semibold text-foreground truncate">
                      {sreCanary?.baseline_version || 'v2.4.1 (Current Production)'}
                    </div>
                  </div>
                  <div className="p-3.5 rounded-lg border border-border bg-muted/40">
                    <div className="text-[11px] text-muted-foreground">Canary Spec</div>
                    <div className="mt-1 font-mono text-xs font-semibold text-foreground truncate">
                      {sreCanary?.canary_version || 'v2.5.0-rightsized (Graviton t4g)'}
                    </div>
                  </div>
                  <div className="p-3.5 rounded-lg border border-border bg-muted/40">
                    <div className="text-[11px] text-muted-foreground">ACA Composite Score</div>
                    <div className="mt-1 text-base font-bold text-foreground">
                      {sreCanary?.score ?? 92.5} / 100
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-xs">
                  <div className="p-2.5 rounded border border-border bg-muted/20 text-center">
                    <div className="text-[10px] text-muted-foreground">P95 Latency Delta</div>
                    <div className="font-semibold text-foreground mt-0.5">
                      {sreCanary?.metrics?.latency_p95_delta_pct != null
                        ? `${sreCanary.metrics.latency_p95_delta_pct > 0 ? '+' : ''}${sreCanary.metrics.latency_p95_delta_pct}%`
                        : '-4.2%'}
                    </div>
                  </div>
                  <div className="p-2.5 rounded border border-border bg-muted/20 text-center">
                    <div className="text-[10px] text-muted-foreground">Error Rate Delta</div>
                    <div className="font-semibold text-foreground mt-0.5">
                      {sreCanary?.metrics?.error_rate_delta_pct != null
                        ? `${sreCanary.metrics.error_rate_delta_pct > 0 ? '+' : ''}${sreCanary.metrics.error_rate_delta_pct}%`
                        : '0.0%'}
                    </div>
                  </div>
                  <div className="p-2.5 rounded border border-border bg-muted/20 text-center">
                    <div className="text-[10px] text-muted-foreground">CPU Delta</div>
                    <div className="font-semibold text-foreground mt-0.5">
                      {sreCanary?.metrics?.cpu_delta_pct != null
                        ? `${sreCanary.metrics.cpu_delta_pct > 0 ? '+' : ''}${sreCanary.metrics.cpu_delta_pct}%`
                        : '-18.5%'}
                    </div>
                  </div>
                  <div className="p-2.5 rounded border border-border bg-muted/20 text-center">
                    <div className="text-[10px] text-muted-foreground">Cost Reduction</div>
                    <div className="font-semibold text-emerald-400 mt-0.5">
                      {sreCanary?.metrics?.cost_reduction_pct != null
                        ? `${sreCanary.metrics.cost_reduction_pct}%`
                        : '28.0%'}
                    </div>
                  </div>
                </div>

                {Array.isArray(sreCanary?.reasons) && sreCanary.reasons.length > 0 && (
                  <div className="pt-2">
                    <div className="text-xs text-muted-foreground mb-1.5 font-medium">
                      Automated Verification Criteria:
                    </div>
                    <div className="space-y-1">
                      {sreCanary.reasons.map((r: string, idx: number) => (
                        <div key={idx} className="flex items-center gap-2 text-xs text-foreground">
                          <Check className="size-3.5 text-emerald-400 shrink-0" />
                          <span>{r}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Manual Rollback Trigger Dialog */}
      <Dialog open={!!rollbackWatch} onOpenChange={() => setRollbackWatch(null)}>
        <DialogContent className="sm:max-w-lg w-[95vw] max-h-[88vh] overflow-y-auto border-border bg-background text-foreground p-6 shadow-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base text-foreground font-semibold">
              <RotateCcw className="size-4" /> Trigger Safe Rollback PR
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to revert the optimization on <span className="font-mono text-foreground font-semibold">{rollbackWatch?.resource_id}</span>?
            </DialogDescription>
          </DialogHeader>
          <div className="py-3 text-xs text-muted-foreground space-y-2">
            <p>
              CloudPulse will immediately open a Git revert Pull Request to restore the workload configuration from <span className="text-foreground font-semibold font-mono">{rollbackWatch?.applied_config?.instance_type}</span> back to <span className="text-foreground font-semibold font-mono">{rollbackWatch?.previous_config?.instance_type}</span>.
            </p>
          </div>
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setRollbackWatch(null)}>Cancel</Button>
            <Button
              size="sm"
              className="bg-primary text-primary-foreground hover:opacity-90 font-medium"
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
        <DialogContent className="sm:max-w-3xl lg:max-w-4xl w-[95vw] max-h-[88vh] flex flex-col p-0 gap-0 border-border bg-background text-foreground shadow-2xl overflow-hidden">
          <DialogHeader className="p-6 pb-4 border-b border-border shrink-0">
            <DialogTitle className="flex items-center gap-2 text-base text-foreground font-semibold">
              <RotateCcw className="size-4" /> Automated Safe Revert Pull Request Ready
            </DialogTitle>
            <DialogDescription>
              A safety pull request has been synthesized to protect production performance SLA.
            </DialogDescription>
          </DialogHeader>
          {rollbackPackage && (
            <>
              <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-lg border border-border bg-muted p-3">
                    <span className="text-[11px] text-muted-foreground">Rollback Branch</span>
                    <div className="mt-1 font-mono text-xs font-semibold text-foreground truncate">
                      {rollbackPackage.branch_name}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-muted p-3">
                    <span className="text-[11px] text-muted-foreground">Restored Configuration</span>
                    <div className="mt-1 font-mono text-xs font-semibold text-foreground truncate">
                      {rollbackPackage.restored_config?.instance_type || 'Original Spec'}
                    </div>
                  </div>
                </div>

                <div>
                  <span className="text-xs text-muted-foreground block mb-1.5 font-medium">Terraform Git Revert Diff:</span>
                  <pre className="max-h-72 overflow-auto rounded-lg border border-border bg-muted p-3.5 font-mono text-xs text-foreground">
                    {rollbackPackage.revert_diff || rollbackPackage.diff || '# Revert diff generated'}
                  </pre>
                </div>
              </div>

              <div className="px-6 py-3.5 border-t border-border bg-muted/20 shrink-0 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3">
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
                    <Button size="sm" className="w-full sm:w-auto bg-primary text-primary-foreground hover:opacity-90 font-medium">
                      <ExternalLink className="mr-1.5 size-3.5" /> View Rollback on GitHub
                    </Button>
                  </a>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Batch GitOps PR Modal */}
      <Dialog open={batchOpen} onOpenChange={setBatchOpen}>
        <DialogContent className="sm:max-w-3xl lg:max-w-4xl w-[95vw] max-h-[88vh] flex flex-col p-0 gap-0 border-border bg-background text-foreground shadow-2xl overflow-hidden">
          <DialogHeader className="p-6 pb-4 border-b border-border shrink-0">
            <DialogTitle className="flex items-center gap-2 text-base text-foreground font-semibold">
              <GitBranch className="size-4" /> Multi-Resource Batch GitOps Pull Request
            </DialogTitle>
            <DialogDescription>
              Synthesized Terraform changes across all 5 resource vectors into a unified Pull Request.
            </DialogDescription>
          </DialogHeader>
          {batchGenerating ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 flex-1">
              <Loader2 className="size-8 animate-spin text-foreground" />
              <span className="text-xs text-muted-foreground">Synthesizing batch Terraform changes across all 5 vectors...</span>
            </div>
          ) : batchResult ? (
            <>
              <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="rounded-lg border border-border bg-muted p-3">
                    <span className="text-[11px] text-muted-foreground">Branch</span>
                    <div className="mt-1 font-mono text-xs font-semibold text-foreground truncate">
                      {batchResult.branch_name}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-muted p-3">
                    <span className="text-[11px] text-muted-foreground">Monthly Net Savings</span>
                    <div className="mt-1 text-xs font-bold text-foreground">
                      {formatCurrency(batchResult.total_monthly_savings, currency)}/mo
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-muted p-3">
                    <span className="text-[11px] text-muted-foreground">Annual Run-Rate ROI</span>
                    <div className="mt-1 text-xs font-bold text-foreground">
                      {formatCurrency(batchResult.total_annual_savings, currency)}/yr
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
                    <span className="flex items-center gap-1"><FileCode className="size-3.5 text-foreground" /> Batch Terraform HCL Diff</span>
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
                      {copiedBatch ? <Check className="mr-1 size-3 text-foreground" /> : <Copy className="mr-1 size-3" />}
                      {copiedBatch ? 'Copied' : 'Copy Diff'}
                    </Button>
                  </div>
                  <pre className="max-h-72 overflow-auto rounded-lg border border-border bg-muted p-3.5 font-mono text-xs text-foreground">
                    {batchResult.diff || '# Batch diff synthesized'}
                  </pre>
                </div>
              </div>

              <div className="px-6 py-3.5 border-t border-border bg-muted/20 shrink-0 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3">
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
                    <Button size="sm" className="w-full sm:w-auto bg-primary text-primary-foreground hover:opacity-90 font-medium">
                      <ExternalLink className="mr-1.5 size-3.5" /> View Batch PR on GitHub
                    </Button>
                  </a>
                </div>
              </div>
            </>
          ) : (
            <div className="py-12 text-center text-xs text-muted-foreground flex-1">
              Failed to generate batch GitOps package.
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Enroll SLA Watch Modal */}
      <Dialog open={enrollModalOpen} onOpenChange={setEnrollModalOpen}>
        <DialogContent className="border-border bg-background text-foreground sm:max-w-lg w-[95vw] max-h-[88vh] overflow-y-auto p-6 shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold flex items-center gap-2">
              <Activity className="size-4 text-foreground" />
              Enroll in 60-Minute SLA Watchdog
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Launches automated post-remediation CloudWatch P95 latency & error monitoring with zero-downtime rollback protection.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleEnrollWatch} className="space-y-4 pt-2">
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-foreground">Target AWS Resource</label>
                {nodes && nodes.length > 0 && (
                  <span className="text-[10px] text-muted-foreground">
                    Discovered: {nodes.find((n: any) => n.instance_id === enrollResourceId)?.name || defaultInstanceId || 'None'}
                  </span>
                )}
              </div>
              {nodes && nodes.length > 0 ? (
                <div className="space-y-1.5">
                  <Select
                    value={enrollResourceId || defaultInstanceId}
                    onValueChange={(val) => { if (val) setEnrollResourceId(val); }}
                  >
                    <SelectTrigger className="bg-background border-border text-foreground text-xs font-mono">
                      <SelectValue placeholder="Select instance..." />
                    </SelectTrigger>
                    <SelectContent className="bg-background border-border text-foreground text-xs">
                      {nodes.map((n: any) => (
                        <SelectItem key={n.instance_id} value={n.instance_id}>
                          {n.instance_id} ({n.name || 'EC2'} · {n.state})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder="e.g. i-1234567890abcdef0"
                    value={enrollResourceId}
                    onChange={(e) => setEnrollResourceId(e.target.value)}
                    className="bg-background border-border text-foreground text-xs font-mono"
                    required
                  />
                </div>
              ) : (
                <Input
                  placeholder="e.g. i-1234567890abcdef0"
                  value={enrollResourceId}
                  onChange={(e) => setEnrollResourceId(e.target.value)}
                  className="bg-background border-border text-foreground text-xs font-mono"
                  required
                />
              )}
            </div>

            <div>
              <label className="text-xs font-medium text-foreground">Remediation Action Type</label>
              <Select value={enrollAction} onValueChange={(val) => { if (val) setEnrollAction(val); }}>
                <SelectTrigger className="mt-1 bg-background border-border text-foreground text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-background border-border text-foreground text-xs">
                  <SelectItem value="migrate_graviton">Migrate to AWS Graviton (t4g/m7g)</SelectItem>
                  <SelectItem value="downsize">Downsize Idle Compute</SelectItem>
                  <SelectItem value="upgrade_gp3">Modernize Storage gp2 -&gt; gp3</SelectItem>
                  <SelectItem value="release_eip">Release Unattached Elastic IP</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="rounded-lg border border-border bg-muted p-3 text-xs text-foreground">
              🛡️ <strong>Safety Guarantee:</strong> During the 60-minute window, if P95 latency degrades by &gt;15%, CloudPulse automatically generates an autonomous git revert PR.
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setEnrollModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={enrolling} className="bg-primary text-primary-foreground hover:opacity-90 font-medium">
                {enrolling ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Activity className="mr-1.5 size-3.5" />}
                Enroll in Watchdog
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Google SRE Blameless Postmortem Dialog (Chapter 15) */}
      <Dialog open={postmortemOpen} onOpenChange={setPostmortemOpen}>
        <DialogContent className="sm:max-w-3xl lg:max-w-4xl w-[95vw] max-h-[88vh] flex flex-col p-0 gap-0 border-border bg-background text-foreground shadow-2xl overflow-hidden">
          <DialogHeader className="p-6 pb-4 border-b border-border shrink-0">
            <div className="flex items-center justify-between">
              <DialogTitle className="flex items-center gap-2 text-base text-foreground font-semibold">
                <FileText className="size-4" /> Google SRE Blameless Postmortem Generator
              </DialogTitle>
              <Badge variant="outline" className="text-[10px] border-border bg-muted">
                Google SRE Book Ch. 15
              </Badge>
            </div>
            <DialogDescription className="text-xs text-muted-foreground mt-0.5">
              Automated root-cause analysis, 5 Whys deduction, timeline reconstruction, and prioritized remediation actions.
            </DialogDescription>
          </DialogHeader>

          <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1">
            {/* Incident Controls */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 rounded-lg border border-border bg-muted/40">
              <div className="sm:col-span-2 space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground">Incident Title</label>
                <Input
                  value={postmortemTitle}
                  onChange={(e) => setPostmortemTitle(e.target.value)}
                  placeholder="e.g. P95 Tail Latency Spike on Downsized EC2 Workloads"
                  className="bg-background border-border text-xs h-8"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground">Severity</label>
                <div className="flex gap-2">
                  <Select value={postmortemSeverity} onValueChange={(val) => { if (val) setPostmortemSeverity(val); }}>
                    <SelectTrigger className="bg-background border-border text-xs h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-background border-border text-xs">
                      <SelectItem value="P0">P0 - Critical Outage</SelectItem>
                      <SelectItem value="P1">P1 - High Degradation</SelectItem>
                      <SelectItem value="P2">P2 - Moderate Latency</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    size="sm"
                    className="h-8 text-xs bg-primary text-primary-foreground shrink-0"
                    disabled={postmortemLoading}
                    onClick={handleGeneratePostmortem}
                  >
                    {postmortemLoading ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
                  </Button>
                </div>
              </div>
            </div>

            {postmortemLoading ? (
              <div className="py-16 flex flex-col items-center justify-center gap-3">
                <Loader2 className="size-8 animate-spin text-foreground" />
                <span className="text-xs text-muted-foreground">
                  Synthesizing blameless postmortem &amp; 5 Whys root cause analysis...
                </span>
              </div>
            ) : postmortemData ? (
              <div className="space-y-5">
                {/* Header Metrics */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg border border-border bg-muted/30">
                    <span className="text-[10px] text-muted-foreground">Incident ID</span>
                    <div className="mt-0.5 font-mono text-xs font-semibold truncate">
                      {postmortemData.incident_id}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg border border-border bg-muted/30">
                    <span className="text-[10px] text-muted-foreground">Lead SRE</span>
                    <div className="mt-0.5 text-xs font-semibold truncate">
                      {postmortemData.lead_sre}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg border border-border bg-muted/30">
                    <span className="text-[10px] text-muted-foreground">MTTD (Mean Time to Detect)</span>
                    <div className="mt-0.5 font-mono text-xs font-bold text-foreground">
                      {postmortemData.mttd_minutes} mins
                    </div>
                  </div>
                  <div className="p-3 rounded-lg border border-border bg-muted/30">
                    <span className="text-[10px] text-muted-foreground">MTTR (Mean Time to Resolve)</span>
                    <div className="mt-0.5 font-mono text-xs font-bold text-foreground">
                      {postmortemData.mttr_minutes} mins
                    </div>
                  </div>
                </div>

                {/* User Impact */}
                <div className="p-3.5 rounded-lg border border-border bg-muted/20">
                  <span className="text-xs font-semibold text-foreground block mb-1">
                    User Impact Summary
                  </span>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {postmortemData.user_impact_summary}
                  </p>
                </div>

                {/* Root Cause Analysis (5 Whys) */}
                <div className="p-3.5 rounded-lg border border-border bg-muted/20 space-y-2">
                  <span className="text-xs font-semibold text-foreground block">
                    Root Cause Analysis (Google SRE 5 Whys Chain)
                  </span>
                  <div className="space-y-2 pt-1">
                    {postmortemData.root_cause_5_whys?.map((why: string, idx: number) => (
                      <div key={idx} className="flex items-start gap-2.5 text-xs">
                        <span className="font-mono font-bold text-primary shrink-0">Why {idx + 1}:</span>
                        <span className="text-muted-foreground">{why}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Timeline */}
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-foreground block">
                    Chronological Incident Timeline
                  </span>
                  <div className="rounded-lg border border-border overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="border-border hover:bg-transparent">
                          <TableHead className="text-xs w-28">Timestamp</TableHead>
                          <TableHead className="text-xs w-24">Phase</TableHead>
                          <TableHead className="text-xs">Event Description</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {postmortemData.timeline?.map((event: any, idx: number) => (
                          <TableRow key={idx} className="border-border hover:bg-muted/50">
                            <TableCell className="font-mono text-xs text-muted-foreground">
                              {event.timestamp}
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline" className="text-[10px] border-border bg-muted">
                                {event.phase}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs text-foreground">
                              {event.event}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>

                {/* Prioritized Action Items */}
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-foreground block">
                    Prioritized SRE Action Items (Google Book Standard)
                  </span>
                  <div className="rounded-lg border border-border overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="border-border hover:bg-transparent">
                          <TableHead className="text-xs w-20">Priority</TableHead>
                          <TableHead className="text-xs">Action Item</TableHead>
                          <TableHead className="text-xs w-28">Owner</TableHead>
                          <TableHead className="text-xs w-20 text-center">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {postmortemData.action_items?.map((item: any, idx: number) => (
                          <TableRow key={idx} className="border-border hover:bg-muted/50">
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={`text-[10px] font-mono ${
                                  item.priority === 'P0'
                                    ? 'border-red-500/30 bg-red-500/10 text-red-400 font-bold'
                                    : item.priority === 'P1'
                                    ? 'border-amber-500/30 bg-amber-500/10 text-amber-400 font-semibold'
                                    : 'border-border bg-muted text-foreground'
                                }`}
                              >
                                {item.priority}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs text-foreground font-medium">
                              {item.action}
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground font-mono">
                              {item.owner}
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge variant="outline" className="text-[9px] border-border bg-muted">
                                {item.status}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>

                {/* Lessons Learned */}
                {postmortemData.lessons_learned && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                    <div className="p-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5">
                      <span className="text-xs font-semibold text-emerald-400 block mb-1.5">What went well</span>
                      <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                        {postmortemData.lessons_learned.what_went_well?.map((item: string, idx: number) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="p-3 rounded-lg border border-red-500/20 bg-red-500/5">
                      <span className="text-xs font-semibold text-red-400 block mb-1.5">What went wrong</span>
                      <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                        {postmortemData.lessons_learned.what_went_wrong?.map((item: string, idx: number) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="p-3 rounded-lg border border-cyan-500/20 bg-cyan-500/5">
                      <span className="text-xs font-semibold text-cyan-400 block mb-1.5">Where we got lucky</span>
                      <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                        {postmortemData.lessons_learned.where_we_got_lucky?.map((item: string, idx: number) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-muted-foreground">
                Click &quot;Synthesize Postmortem&quot; to generate blameless postmortem report.
              </div>
            )}
          </div>

          <div className="px-6 py-3.5 border-t border-border bg-muted/20 shrink-0 flex items-center justify-between gap-3">
            <span className="text-xs text-muted-foreground">
              Format: <span className="font-mono text-foreground">Google SRE Postmortem Template</span>
            </span>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => setPostmortemOpen(false)}>
                Close
              </Button>
              {postmortemData && (
                <Button
                  size="sm"
                  className="bg-primary text-primary-foreground hover:opacity-90 font-medium text-xs"
                  onClick={() => {
                    const md = `# Google SRE Blameless Postmortem: ${postmortemData.title}
**Incident ID:** ${postmortemData.incident_id}
**Severity:** ${postmortemData.severity} | **Lead SRE:** ${postmortemData.lead_sre}
**Duration:** ${postmortemData.duration_minutes}m | **MTTD:** ${postmortemData.mttd_minutes}m | **MTTR:** ${postmortemData.mttr_minutes}m

## User Impact
${postmortemData.user_impact_summary}

## Root Cause Analysis (5 Whys)
${postmortemData.root_cause_5_whys?.map((w: string, i: number) => `${i + 1}. ${w}`).join('\n')}

## Incident Timeline
${postmortemData.timeline?.map((t: any) => `- **${t.timestamp}**: [${t.phase}] ${t.event}`).join('\n')}

## Action Items
| Priority | Action | Owner | Status |
|---|---|---|---|
${postmortemData.action_items?.map((a: any) => `| ${a.priority} | ${a.action} | ${a.owner} | ${a.status} |`).join('\n')}
`;
                    navigator.clipboard.writeText(md);
                    setPostmortemCopied(true);
                    setTimeout(() => setPostmortemCopied(false), 2000);
                  }}
                >
                  {postmortemCopied ? <Check className="mr-1.5 size-3.5" /> : <Copy className="mr-1.5 size-3.5" />}
                  {postmortemCopied ? 'Copied Markdown' : 'Copy Postmortem Markdown'}
                </Button>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}


export default GitOpsSlaView
