'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  AlertCircle,
  Badge as LucideBadge,
  Bell,
  Bot,
  Calendar,
  Check,
  CheckCircle2,
  CircleDollarSign,
  History,
  Loader2,
  Plus,
  RefreshCw,
  Server,
  ShieldCheck,
  Sparkles,
  X,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState, TableSkeleton } from '@/components/empty-state'
import { MetricCard, SectionTitle } from '@/components/dashboard'
import { useOptimisticToast } from '@/components/ui/optimistic-toast'
import { formatCurrency, formatInteger } from '@/lib/formatters'
import type { Currency, ComputeNode } from '@/types/dashboard'

export function SchedulerPrewarmView({ currency = 'USD', apiUrl, nodes = [] }: any) {
  const { toast } = useOptimisticToast();
  const runningNode = useMemo(() => {
    if (!Array.isArray(nodes) || nodes.length === 0) return null;
    return nodes.find((n: any) => n.state === 'running' || n.instance_state === 'running') || nodes[0];
  }, [nodes]);

  const defaultInstanceId = runningNode?.instance_id || '';

  const [schedules, setSchedules] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [activeTab, setActiveTab] = useState<'schedules' | 'jobs'>('schedules');
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error' | 'warning'; message: string } | null>(null);

  // New Schedule Form state
  const [formInstanceId, setFormInstanceId] = useState(defaultInstanceId);
  const [formTimezone, setFormTimezone] = useState('Asia/Kolkata');
  const [formStartTime, setFormStartTime] = useState('08:00');
  const [formStopTime, setFormStopTime] = useState('20:00');
  const [formDays, setFormDays] = useState({
    monday: true,
    tuesday: true,
    wednesday: true,
    thursday: true,
    friday: true,
    saturday: false,
    sunday: false,
  });
  const [formPrewarmMins, setFormPrewarmMins] = useState(15);
  const [formGraceMins, setFormGraceMins] = useState(10);

  // Manual Trigger state
  const [manualInstanceId, setManualInstanceId] = useState(defaultInstanceId);
  const [manualAction, setManualAction] = useState('STOP');
  const [manualDryRun, setManualDryRun] = useState(true);
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    if (defaultInstanceId) {
      if (!formInstanceId) setFormInstanceId(defaultInstanceId);
      if (!manualInstanceId) setManualInstanceId(defaultInstanceId);
    }
  }, [defaultInstanceId, formInstanceId, manualInstanceId]);

  const fetchSchedulerData = useCallback(async (isInitial = false) => {
    if (isInitial) setLoading(true);
    try {
      const [sRes, jRes] = await Promise.all([
        fetch(apiUrl('/api/v2/schedules')),
        fetch(apiUrl('/api/v2/schedules/jobs?limit=50')),
      ]);
      if (sRes.ok) {
        const sd = await sRes.json();
        setSchedules(Array.isArray(sd?.schedules) ? sd.schedules : []);
      }
      if (jRes.ok) {
        const jd = await jRes.json();
        setJobs(Array.isArray(jd?.jobs) ? jd.jobs : []);
      }
    } catch (err) {
      console.error('Failed to load scheduler data:', err);
    } finally {
      if (isInitial) setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    fetchSchedulerData(true);
    const interval = setInterval(() => fetchSchedulerData(false), 30000); // 30s background auto-refresh
    return () => clearInterval(interval);
  }, [fetchSchedulerData]);

  const handleSaveSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formInstanceId.trim()) return;
    try {
      const res = await fetch(apiUrl('/api/v2/schedules'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instance_id: formInstanceId.trim(),
          timezone: formTimezone,
          start_time: formStartTime,
          stop_time: formStopTime,
          ...formDays,
          prewarm_minutes: Number(formPrewarmMins),
          grace_period_minutes: Number(formGraceMins),
          enabled: true,
        }),
      });
      if (res.ok) {
        setFeedback({ type: 'success', message: `Schedule created for ${formInstanceId} successfully!` });
        setCreateModalOpen(false);
        setFormInstanceId('');
        fetchSchedulerData();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to create schedule' });
      }
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    }
  };

  const handleDeleteSchedule = async (id: string) => {
    try {
      const res = await fetch(apiUrl(`/api/v2/schedules/${id}`), { method: 'DELETE' });
      if (res.ok) {
        setFeedback({ type: 'success', message: 'Schedule removed successfully.' });
        fetchSchedulerData();
      }
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    }
  };

  const handleOverride = async (jobId: string, action: 'KEEP_RUNNING' | 'STOP_NOW', hours = 2) => {
    // Instant optimistic update
    setJobs((prev: any[]) =>
      prev.map((j: any) =>
        j.id === jobId ? { ...j, status: action === 'KEEP_RUNNING' ? 'OVERRIDDEN' : 'EXECUTING' } : j
      )
    );
    toast({
      title: action === 'KEEP_RUNNING' ? 'Instance Keep-Running Engaged' : 'Immediate Stop Dispatched',
      description: action === 'KEEP_RUNNING' ? `Extended schedule runtime by ${hours} hours. Auto-shutdown delayed.` : 'Immediate shutdown command issued.',
      type: 'info'
    });

    try {
      const res = await fetch(apiUrl(`/api/v2/schedules/jobs/${jobId}/override`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, extension_hours: hours }),
      });
      if (res.ok) {
        const data = await res.json();
        setFeedback({ type: 'success', message: data.message || 'Override registered successfully!' });
        fetchSchedulerData(false);
      } else {
        const err = await res.json().catch(() => ({}));
        setFeedback({ type: 'error', message: err.detail || 'Override failed' });
        toast({
          title: 'Override Sync Failed',
          description: err.detail || 'Could not communicate override to scheduler.',
          type: 'error'
        });
      }
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
      toast({
        title: 'Network Sync Error',
        description: err.message,
        type: 'error'
      });
    }
  };

  const handleEvaluateNow = async (dryRun = true) => {
    setEvaluating(true);
    try {
      const res = await fetch(apiUrl(`/api/v2/schedules/evaluate-now?dry_run=${dryRun}`), {
        method: 'POST',
      });
      if (res.ok) {
        setFeedback({ type: 'success', message: `Evaluation complete! Checked active operational schedules.` });
        fetchSchedulerData();
      }
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setEvaluating(false);
    }
  };

  const handleManualTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualInstanceId.trim()) return;
    setTriggering(true);
    try {
      const res = await fetch(apiUrl('/api/v2/schedules/jobs/manual-trigger'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instance_id: manualInstanceId.trim(),
          action: manualAction,
          dry_run: manualDryRun,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const job = data.job;
        if (job.status === 'BLOCKED') {
          setFeedback({ type: 'warning', message: `Guardian Blocked ${manualAction}: ${job.blocked_reason}` });
        } else {
          setFeedback({ type: 'success', message: `Job executed with status: ${job.status}` });
        }
        setTriggerModalOpen(false);
        setManualInstanceId('');
        fetchSchedulerData();
      }
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setTriggering(false);
    }
  };

  // Predictive AI Telemetry Analysis state
  const [predictiveRecommendation, setPredictiveRecommendation] = useState<any | null>(null);
  const [analyzingTelemetry, setAnalyzingTelemetry] = useState(false);

  const handleAnalyzeTelemetry = async () => {
    const targetId = formInstanceId.trim() || defaultInstanceId;
    if (!targetId) {
      setFeedback({ type: 'warning', message: 'No EC2 instance selected. Please select an instance or enter an instance ID to analyze.' });
      return;
    }
    setAnalyzingTelemetry(true);
    try {
      const res = await fetch(apiUrl(`/api/v2/schedules/predictive/recommendations?instance_id=${encodeURIComponent(targetId)}&days=14`));
      if (res.ok) {
        const data = await res.json();
        setPredictiveRecommendation(data.recommendation);
        if (data.telemetry_points_analyzed === 0) {
          setFeedback({
            type: 'warning',
            message: data.recommendation?.reason || `No CloudWatch telemetry available for ${targetId}.`
          });
        } else {
          setFeedback({
            type: 'success',
            message: `Analyzed ${data.telemetry_points_analyzed} CloudWatch datapoints for ${targetId}. Pattern confidence: ${Math.round((data.recommendation?.confidence || 0) * 100)}%.`
          });
        }
      }
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setAnalyzingTelemetry(false);
    }
  };

  const handleApplyPredictive = async () => {
    if (!predictiveRecommendation) return;
    try {
      const res = await fetch(apiUrl('/api/v2/schedules/predictive/apply'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instance_id: predictiveRecommendation.instance_id,
          start_time: predictiveRecommendation.recommended_start_time,
          stop_time: predictiveRecommendation.recommended_stop_time,
          prewarm_minutes: predictiveRecommendation.prewarm_minutes,
        }),
      });
      if (res.ok) {
        setFeedback({ type: 'success', message: `Predictive Pre-Warming schedule active! Starts at ${predictiveRecommendation.recommended_start_time}.` });
        fetchSchedulerData();
      }
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    }
  };

  // Find active grace period alerts (deduplicated by instance_id, showing only real active instances)
  const notifyingJobs = useMemo(() => {
    const active = jobs.filter(
      (j: any) =>
        (j.status === 'NOTIFYING' || (j.status === 'PENDING' && j.action === 'STOP')) &&
        j.instance_id !== 'i-0a1b2c3d4e5f60718'
    );
    const seen = new Set<string>();
    const unique: any[] = [];
    for (const j of active) {
      if (!seen.has(j.instance_id)) {
        seen.add(j.instance_id);
        unique.push(j);
      }
    }
    return unique;
  }, [jobs]);

  return (
    <div className="space-y-6">
      <SectionTitle
        eyebrow="FINOPS AUTOMATION & PRE-WARMING"
        title="OptiScale Operational Scheduling & Guardian Pipeline"
        description="Autonomous instance lifecycle scheduling, 10-minute developer grace periods, and pre-flight Guardian safety validations."
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleAnalyzeTelemetry}
              disabled={analyzingTelemetry}
              className="border-border bg-background text-foreground hover:bg-muted"
            >
              {analyzingTelemetry ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <Bot className="size-3.5 mr-1.5" />}
              AI Telemetry Analysis
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleEvaluateNow(true)}
              disabled={evaluating}
              className="border-border bg-background text-foreground hover:bg-muted"
            >
              {evaluating ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <RefreshCw className="size-3.5 mr-1.5" />}
              Evaluate Now
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setTriggerModalOpen(true)}
              className="border-border bg-background text-foreground hover:bg-muted"
            >
              <Zap className="size-3.5 mr-1.5" />
              Manual Trigger
            </Button>
            <Button
              size="sm"
              onClick={() => setCreateModalOpen(true)}
              className="bg-primary text-primary-foreground hover:opacity-90 font-medium"
            >
              <Plus className="size-3.5 mr-1.5" />
              New Schedule
            </Button>
          </div>
        }
      />

      {predictiveRecommendation && (
        <div className="rounded-2xl border border-border bg-card p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="size-10 rounded-xl border border-border bg-muted flex items-center justify-center text-foreground shrink-0">
                <Sparkles className="size-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-foreground">Predictive Pre-Warming Pattern Detected</span>
                  <Badge className="border-border bg-muted text-foreground">
                    {Math.round(predictiveRecommendation.confidence * 100)}% Confidence
                  </Badge>
                </div>
                <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
                  {predictiveRecommendation.reason}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                  <span className="text-muted-foreground">Target: <code className="text-foreground font-mono font-semibold">{predictiveRecommendation.instance_id}</code></span>
                  <span className="text-muted-foreground">User Activity: <strong className="text-foreground">{predictiveRecommendation.detected_activity_start}</strong></span>
                  <span className="text-muted-foreground">Pre-Warm Start: <strong className="text-foreground">{predictiveRecommendation.recommended_start_time}</strong></span>
                  <span className="text-muted-foreground">Stop Time: <strong className="text-foreground">{predictiveRecommendation.recommended_stop_time}</strong></span>
                  <span className="text-foreground font-medium">Est. Waste Reduction: ~{predictiveRecommendation.estimated_savings_percent}%</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button
                size="sm"
                onClick={handleApplyPredictive}
                className="bg-primary text-primary-foreground hover:opacity-90 font-medium"
              >
                <Check className="size-3.5 mr-1.5" />
                Activate Schedule
              </Button>
            </div>
          </div>
        </div>
      )}

      {feedback && (
        <div
          className={`flex items-center justify-between p-3.5 rounded-xl border text-sm border-border bg-muted text-foreground`}
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{feedback.message}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </button>
        </div>
      )}

      {/* 10-Minute Grace Period Alert Notification Loop */}
      {notifyingJobs.length > 0 && (
        <div className="space-y-3">
          {notifyingJobs.map((job) => (
            <div
              key={job.id}
              className="rounded-2xl border border-border bg-card p-5"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="size-10 rounded-xl border border-border bg-muted flex items-center justify-center text-foreground shrink-0 animate-pulse">
                    <Bell className="size-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-foreground">10-Minute Grace Period Active</span>
                      <Badge className="border-border bg-muted text-foreground">PENDING STOP</Badge>
                    </div>
                    <p className="mt-1 text-xs sm:text-sm text-foreground">
                      Instance <code className="font-mono text-foreground font-bold">{job.instance_id}</code> will shut down according to scheduled business closure.
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Reason: {job.reason || 'Evening operational power-off window reached.'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleOverride(job.id, 'KEEP_RUNNING', 2)}
                    className="border-border bg-background text-foreground hover:bg-muted"
                  >
                    <CheckCircle2 className="size-3.5 mr-1.5" />
                    KEEP RUNNING (2h)
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleOverride(job.id, 'STOP_NOW')}
                    className="bg-primary text-primary-foreground hover:opacity-90 font-medium"
                  >
                    <Zap className="size-3.5 mr-1.5" />
                    STOP NOW
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          icon={Server}
          label="Managed EC2 Schedules"
          value={schedules.length}
          detail="Active operational time windows"
          tone="neutral"
        />
        <MetricCard
          icon={Zap}
          label="Predictive Pre-Warming"
          value="15m Lead"
          detail="Pre-heats instances before user surge"
          tone="neutral"
        />
        <MetricCard
          icon={ShieldCheck}
          label="Guardian Safety Gate"
          value="Online"
          detail="SSH, Backup & Tag checks enforced"
          tone="neutral"
        />
        <MetricCard
          icon={CircleDollarSign}
          label="Est. Off-Hours Savings"
          value="~68%"
          detail="Eliminates overnight & weekend waste"
          tone="neutral"
        />
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Button
            variant={activeTab === 'schedules' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('schedules')}
            className={activeTab === 'schedules' ? 'bg-primary text-primary-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}
          >
            Operational Schedules ({schedules.length})
          </Button>
          <Button
            variant={activeTab === 'jobs' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('jobs')}
            className={activeTab === 'jobs' ? 'bg-primary text-primary-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}
          >
            Execution & Guardian Audit ({jobs.length})
          </Button>
        </div>
        <span className="text-xs text-muted-foreground hidden sm:inline">
          Timezone: <span className="font-mono text-slate-300">Asia/Kolkata (IST)</span>
        </span>
      </div>

      {/* TAB 1: OPERATIONAL SCHEDULES */}
      {activeTab === 'schedules' && (
        <Card className="border-white/8 bg-card/70 backdrop-blur">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium flex items-center justify-between">
              <span>Configured Instance Schedules</span>
              <span className="text-xs font-normal text-muted-foreground">Evaluates every 60 seconds</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <TableSkeleton rows={4} cols={7} />
            ) : schedules.length === 0 ? (
              <EmptyState
                icon={Calendar}
                title="No Active Schedules"
                description="Configure working windows, grace periods, and pre-warm leads to eliminate off-hours idle waste."
                action={
                  <Button size="sm" className="bg-primary text-primary-foreground hover:opacity-90 font-medium" onClick={() => setCreateModalOpen(true)}>
                    <Plus className="mr-1.5 size-3.5" />
                    New Schedule
                  </Button>
                }
                className="my-4 border-0"
              />
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader className="bg-muted">
                    <TableRow className="border-border">
                      <TableHead className="text-xs">Instance ID</TableHead>
                      <TableHead className="text-xs">Working Window</TableHead>
                      <TableHead className="text-xs">Active Days</TableHead>
                      <TableHead className="text-xs">Pre-Warm Lead</TableHead>
                      <TableHead className="text-xs">Grace Period</TableHead>
                      <TableHead className="text-xs">Status</TableHead>
                      <TableHead className="text-xs text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {schedules.map((s) => {
                      const daysActive = [
                        s.monday && 'M',
                        s.tuesday && 'Tu',
                        s.wednesday && 'W',
                        s.thursday && 'Th',
                        s.friday && 'F',
                        s.saturday && 'Sa',
                        s.sunday && 'Su',
                      ].filter(Boolean).join(', ');

                      return (
                        <TableRow key={s.id} className="border-border hover:bg-muted/50">
                          <TableCell className="font-mono text-xs font-semibold text-foreground">
                            {s.instance_id}
                          </TableCell>
                          <TableCell className="text-xs">
                            <span className="font-medium text-foreground">{s.start_time}</span>
                            <span className="text-muted-foreground mx-1.5">to</span>
                            <span className="font-medium text-foreground">{s.stop_time}</span>
                            <span className="text-[10px] text-muted-foreground ml-1.5">({s.timezone})</span>
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground font-mono">
                            {daysActive || 'None'}
                          </TableCell>
                          <TableCell className="text-xs font-mono text-foreground">
                            {s.prewarm_minutes} mins
                          </TableCell>
                          <TableCell className="text-xs font-mono text-muted-foreground">
                            {s.grace_period_minutes} mins
                          </TableCell>
                          <TableCell>
                            <Badge className="border-border bg-muted text-foreground text-[10px]">
                              ENABLED
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteSchedule(s.id)}
                              className="text-muted-foreground hover:text-foreground underline h-7 px-2 text-xs"
                            >
                              Delete
                            </Button>
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
      )}

      {/* TAB 2: EXECUTION & GUARDIAN AUDIT LEDGER */}
      {activeTab === 'jobs' && (
        <Card className="border-border bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium flex items-center justify-between">
              <span>Auditable Job Pipeline & Guardian Safety Gate</span>
              <span className="text-xs font-normal text-muted-foreground">Full state lifecycle history</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <TableSkeleton rows={4} cols={6} />
            ) : jobs.length === 0 ? (
              <EmptyState
                icon={History}
                title="No Execution Jobs Recorded"
                description="Jobs triggered by schedules, pre-warming, or manual interventions will appear here."
                className="my-4 border-0"
              />
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader className="bg-muted">
                    <TableRow className="border-border">
                      <TableHead className="text-xs">Job ID / Time</TableHead>
                      <TableHead className="text-xs">Instance</TableHead>
                      <TableHead className="text-xs">Action</TableHead>
                      <TableHead className="text-xs">Status</TableHead>
                      <TableHead className="text-xs">Reason / Validation Details</TableHead>
                      <TableHead className="text-xs text-right">Grace Period Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {jobs.map((j) => {
                      const isBlocked = j.status === 'BLOCKED';
                      const isNotifying = j.status === 'NOTIFYING';

                      return (
                        <TableRow key={j.id} className="border-border hover:bg-muted/50">
                          <TableCell className="text-xs">
                            <div className="font-mono text-foreground font-semibold">{j.id.slice(0, 8)}...</div>
                            <div className="text-[10px] text-muted-foreground">
                              {j.scheduled_at ? new Date(j.scheduled_at).toLocaleTimeString() : 'N/A'}
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-xs text-foreground font-semibold">
                            {j.instance_id}
                          </TableCell>
                          <TableCell>
                            <span className="text-xs font-semibold px-2 py-0.5 rounded border border-border bg-muted text-foreground">
                              {j.action}
                            </span>
                          </TableCell>
                          <TableCell>
                            <Badge
                              className={`text-[10px] border-border ${
                                isBlocked
                                  ? 'bg-muted text-muted-foreground line-through'
                                  : isNotifying
                                  ? 'bg-muted text-foreground animate-pulse'
                                  : 'bg-muted text-foreground'
                              }`}
                            >
                              {j.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs max-w-xs">
                            {isBlocked ? (
                              <div className="text-foreground font-medium underline">Blocked: {j.blocked_reason}</div>
                            ) : (
                              <div className="text-muted-foreground">{j.reason || 'Normal schedule dispatch'}</div>
                            )}
                            {j.execution_details?.guardian_checks && (
                              <div className="text-[10px] text-muted-foreground mt-0.5">
                                SSH: {j.execution_details.guardian_checks.active_ssh ? 'Active' : 'Clear'} · Backup: {j.execution_details.guardian_checks.backup_running ? 'Active' : 'Clear'}
                              </div>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            {isNotifying && (
                              <div className="flex items-center justify-end gap-1.5">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleOverride(j.id, 'KEEP_RUNNING', 2)}
                                  className="text-foreground border border-border bg-background hover:bg-muted h-6 px-2 text-[10px]"
                                >
                                  Override (2h)
                                </Button>
                                <Button
                                  size="sm"
                                  onClick={() => handleOverride(j.id, 'STOP_NOW')}
                                  className="bg-primary text-primary-foreground hover:opacity-90 h-6 px-2 text-[10px]"
                                >
                                  Stop Now
                                </Button>
                              </div>
                            )}
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
      )}

      {/* CREATE SCHEDULE MODAL */}
      <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
        <DialogContent className="border-border bg-background text-foreground max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold flex items-center gap-2">
              <Zap className="size-4 text-foreground" />
              Create Operational Schedule
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Define daily operating windows, pre-warming lead times, and grace periods for an EC2 instance.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSaveSchedule} className="space-y-4 pt-2">
            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-foreground">EC2 Instance ID</label>
                {nodes && nodes.length > 0 && (
                  <span className="text-[10px] text-muted-foreground">
                    Discovered: {nodes.find((n: any) => n.instance_id === formInstanceId)?.name || defaultInstanceId || 'None'}
                  </span>
                )}
              </div>
              {nodes && nodes.length > 0 ? (
                <div className="space-y-1.5 mt-1">
                  <Select
                    value={formInstanceId || defaultInstanceId}
                    onValueChange={(val) => { if (val) setFormInstanceId(val); }}
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
                    value={formInstanceId}
                    onChange={(e) => setFormInstanceId(e.target.value)}
                    className="bg-background border-border text-foreground text-xs font-mono"
                    required
                  />
                </div>
              ) : (
                <Input
                  placeholder="e.g. i-1234567890abcdef0"
                  value={formInstanceId}
                  onChange={(e) => setFormInstanceId(e.target.value)}
                  className="mt-1 bg-background border-border text-foreground text-xs font-mono"
                  required
                />
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground">Timezone</label>
                <Select value={formTimezone} onValueChange={(val) => { if (val) setFormTimezone(val); }}>
                  <SelectTrigger className="mt-1 bg-background border-border text-foreground text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-background border-border text-foreground text-xs">
                    <SelectItem value="Asia/Kolkata">Asia/Kolkata (IST)</SelectItem>
                    <SelectItem value="UTC">UTC</SelectItem>
                    <SelectItem value="America/New_York">America/New_York (EST)</SelectItem>
                    <SelectItem value="Europe/London">Europe/London (GMT)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-xs font-medium text-foreground">Pre-Warm Lead (Mins)</label>
                <Input
                  type="number"
                  min="0"
                  max="60"
                  value={formPrewarmMins}
                  onChange={(e) => setFormPrewarmMins(Number(e.target.value))}
                  className="mt-1 bg-background border-border text-foreground text-xs font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground">START Time (24h)</label>
                <Input
                  type="time"
                  value={formStartTime}
                  onChange={(e) => setFormStartTime(e.target.value)}
                  className="mt-1 bg-background border-border text-foreground text-xs font-mono"
                  required
                />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground">STOP Time (24h)</label>
                <Input
                  type="time"
                  value={formStopTime}
                  onChange={(e) => setFormStopTime(e.target.value)}
                  className="mt-1 bg-background border-border text-foreground text-xs font-mono"
                  required
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-foreground block mb-1.5">Active Days</label>
              <div className="grid grid-cols-7 gap-1 text-center">
                {[
                  { key: 'monday', label: 'Mon' },
                  { key: 'tuesday', label: 'Tue' },
                  { key: 'wednesday', label: 'Wed' },
                  { key: 'thursday', label: 'Thu' },
                  { key: 'friday', label: 'Fri' },
                  { key: 'saturday', label: 'Sat' },
                  { key: 'sunday', label: 'Sun' },
                ].map((d) => (
                  <button
                    type="button"
                    key={d.key}
                    onClick={() => setFormDays(prev => ({ ...prev, [d.key]: !prev[d.key as keyof typeof prev] }))}
                    className={`py-1.5 text-xs rounded border transition-colors ${
                      formDays[d.key as keyof typeof formDays]
                        ? 'bg-primary text-primary-foreground font-semibold border-primary'
                        : 'bg-background border-border text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setCreateModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" className="bg-primary text-primary-foreground hover:opacity-90 font-medium">
                Save Operational Schedule
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* MANUAL TRIGGER MODAL */}
      <Dialog open={triggerModalOpen} onOpenChange={setTriggerModalOpen}>
        <DialogContent className="border-border bg-background text-foreground max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold flex items-center gap-2">
              <ShieldCheck className="size-4 text-foreground" />
              Manual Trigger (Guardian Protected)
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Immediately dispatch an EC2 power state request through the Guardian validation layer.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleManualTrigger} className="space-y-4 pt-2">
            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-foreground">EC2 Instance ID</label>
                {nodes && nodes.length > 0 && (
                  <span className="text-[10px] text-muted-foreground">
                    Discovered: {nodes.find((n: any) => n.instance_id === manualInstanceId)?.name || defaultInstanceId || 'None'}
                  </span>
                )}
              </div>
              {nodes && nodes.length > 0 ? (
                <div className="space-y-1.5 mt-1">
                  <Select
                    value={manualInstanceId || defaultInstanceId}
                    onValueChange={(val) => { if (val) setManualInstanceId(val); }}
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
                    value={manualInstanceId}
                    onChange={(e) => setManualInstanceId(e.target.value)}
                    className="bg-background border-border text-foreground text-xs font-mono"
                    required
                  />
                </div>
              ) : (
                <Input
                  placeholder="e.g. i-1234567890abcdef0"
                  value={manualInstanceId}
                  onChange={(e) => setManualInstanceId(e.target.value)}
                  className="mt-1 bg-background border-border text-foreground text-xs font-mono"
                  required
                />
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground">Action</label>
                <Select value={manualAction} onValueChange={(val) => { if (val) setManualAction(val); }}>
                  <SelectTrigger className="mt-1 bg-background border-border text-foreground text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-background border-border text-foreground text-xs">
                    <SelectItem value="START">START Instance</SelectItem>
                    <SelectItem value="STOP">STOP Instance</SelectItem>
                    <SelectItem value="PREWARM">PREWARM Instance</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-xs font-medium text-foreground">Execution Mode</label>
                <Select
                  value={manualDryRun ? 'dry_run' : 'live'}
                  onValueChange={(v) => setManualDryRun(v === 'dry_run')}
                >
                  <SelectTrigger className="mt-1 bg-background border-border text-foreground text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-background border-border text-foreground text-xs">
                    <SelectItem value="dry_run">Dry Run (Simulate)</SelectItem>
                    <SelectItem value="live">Live AWS Execution</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-muted p-3 text-xs text-foreground">
              <span className="font-semibold">Guardian Gate:</span> Every request will verify active SSH sessions, EBS snapshots, and tag guardrails before any cloud action.
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setTriggerModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={triggering} className="bg-primary text-primary-foreground hover:opacity-90 font-medium">
                {triggering ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <Zap className="size-3.5 mr-1.5" />}
                Dispatch through Guardian
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default SchedulerPrewarmView
