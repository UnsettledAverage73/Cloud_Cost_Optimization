'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  AlertTriangle,
  Check,
  CircleDollarSign,
  Copy,
  Cpu,
  FileCode,
  Layers,
  RefreshCw,
  Server,
  Settings,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, TableSkeleton } from '@/components/empty-state'
import { SectionTitle } from '@/components/dashboard'
import { formatCurrency, formatInteger } from '@/lib/formatters'
import type { Currency } from '@/types/dashboard'

export function KubernetesView({ currency = 'USD', apiUrl }: { currency: 'USD' | 'INR'; apiUrl: (path: string) => string }) {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [status, setStatus] = useState<any>(null);
  const [efficiency, setEfficiency] = useState<any>(null);
  const [allocations, setAllocations] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [selectedNamespace, setSelectedNamespace] = useState('all');
  const [activeYamlDiff, setActiveYamlDiff] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [customOpencostUrl, setCustomOpencostUrl] = useState('');
  const [configSaving, setConfigSaving] = useState(false);

  const fetchK8s = useCallback(async () => {
    setLoading(true);
    try {
      const [effRes, allocRes, recRes, statusRes] = await Promise.all([
        fetch(apiUrl(`/api/v2/kubernetes/efficiency?currency=${currency}&rate=84.0`)),
        fetch(apiUrl(`/api/v2/kubernetes/allocations?currency=${currency}&rate=84.0`)),
        fetch(apiUrl(`/api/v2/kubernetes/recommendations?currency=${currency}&rate=84.0`)),
        fetch(apiUrl('/api/v2/kubernetes/status')),
      ]);
      if (effRes.ok) setEfficiency(await effRes.json());
      if (allocRes.ok) {
        const a = await allocRes.json();
        setAllocations(Array.isArray(a) ? a : a.allocations || []);
      }
      if (recRes.ok) {
        const r = await recRes.json();
        setRecommendations(Array.isArray(r) ? r : r.recommendations || []);
      }
      if (statusRes.ok) {
        const s = await statusRes.json();
        setStatus(s);
        if (s.opencost_url) setCustomOpencostUrl(s.opencost_url);
      }
    } catch (err) {
      console.error('Failed to load Kubernetes data:', err);
    } finally {
      setLoading(false);
    }
  }, [currency, apiUrl]);

  useEffect(() => {
    fetchK8s();
  }, [fetchK8s]);

  const handleSyncTelemetry = async () => {
    setSyncing(true);
    try {
      await fetch(apiUrl('/api/v2/kubernetes/sync'), { method: 'POST' });
      await fetchK8s();
    } catch (e) {
      console.error('Telemetry sync failed:', e);
    } finally {
      setSyncing(false);
    }
  };

  const handleSaveConfig = async () => {
    setConfigSaving(true);
    try {
      await fetch(apiUrl('/api/v2/kubernetes/config'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ opencost_url: customOpencostUrl, mode: 'realtime' })
      });
      setShowConfigModal(false);
      await fetchK8s();
    } catch (e) {
      console.error('Config save failed:', e);
    } finally {
      setConfigSaving(false);
    }
  };

  const handleClearDemoData = async () => {
    setClearing(true);
    try {
      await fetch(apiUrl('/api/v2/kubernetes/clear-demo'), { method: 'POST' });
      await fetchK8s();
    } catch (e) {
      console.error('Clear demo failed:', e);
    } finally {
      setClearing(false);
    }
  };

  const namespaces = useMemo(() => {
    const set = new Set<string>();
    allocations.forEach(a => {
      if (a.namespace) set.add(a.namespace);
    });
    return ['all', ...Array.from(set)];
  }, [allocations]);

  const filteredAllocations = useMemo(() => {
    if (selectedNamespace === 'all') return allocations;
    return allocations.filter(a => a.namespace === selectedNamespace);
  }, [allocations, selectedNamespace]);

  const isConnected = Boolean(status?.connected);
  const providerLabel = status?.provider === 'opencost'
    ? 'Live OpenCost API'
    : status?.provider === 'kubectl'
    ? 'Live Kubernetes Cluster (kubectl)'
    : status?.provider === 'ingested'
    ? 'Live Ingested Telemetry'
    : status?.provider === 'demo'
    ? 'Demo Simulation'
    : 'No Live Telemetry Stream';

  return (
    <>
      <SectionTitle
        eyebrow="Container FinOps"
        title="Kubernetes & OpenCost Workload Allocation"
        description="Real-time container-level resource rightsizing, idle waste attribution, and 1-click YAML patch diffs."
        status={
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant="outline"
              className={
                isConnected
                  ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                  : 'border-amber-400/40 bg-amber-400/10 text-amber-300'
              }
            >
              <span className={`mr-1.5 inline-block size-1.5 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
              {providerLabel}
            </Badge>
            <Badge variant="outline" className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300 text-xs">
              OpenCost FOCUS 1.0
            </Badge>
          </div>
        }
      />

      {/* Real-Time Telemetry Control Strip */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-white/8 bg-card/60 p-4">
        <div className="flex items-center gap-3">
          <div className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${isConnected ? 'bg-emerald-500/15 text-emerald-400' : 'bg-white/5 text-muted-foreground'}`}>
            <Cpu className="size-4" />
          </div>
          <div>
            <div className="text-xs font-medium text-foreground">
              {isConnected ? (
                <span>Connected: <span className="font-mono text-cyan-300">{status?.cluster_name || 'Kubernetes Cluster'}</span> via <span className="font-semibold text-emerald-400">{status?.provider?.toUpperCase()}</span></span>
              ) : (
                <span>Cluster Stream: <span className="text-muted-foreground">Waiting for Live OpenCost / K8s Telemetry</span></span>
              )}
            </div>
            <div className="text-[11px] text-muted-foreground">
              {status?.last_sync ? `Last Synced: ${new Date(status.last_sync).toLocaleTimeString()}` : 'No active cluster telemetry stream'}
              {status?.opencost_url && ` • Endpoint: ${status.opencost_url}`}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={syncing}
            onClick={handleSyncTelemetry}
            className="border-cyan-400/30 bg-cyan-400/10 text-xs text-cyan-300 hover:bg-cyan-400/20"
          >
            <RefreshCw className={`mr-1.5 size-3.5 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Syncing...' : 'Sync Telemetry'}
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowConfigModal(true)}
            className="border-white/10 bg-white/5 text-xs text-foreground hover:bg-white/10"
          >
            <Settings className="mr-1.5 size-3.5 text-muted-foreground" />
            Configure Endpoint
          </Button>

          {status?.provider === 'demo' && (
            <Button
              size="sm"
              variant="outline"
              disabled={clearing}
              onClick={handleClearDemoData}
              className="border-amber-400/30 bg-amber-400/10 text-xs text-amber-300 hover:bg-amber-400/20"
            >
              {clearing ? 'Clearing...' : 'Remove Mock Data'}
            </Button>
          )}
        </div>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Cluster Efficiency</span>
              <Cpu className="size-4 text-cyan-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-cyan-300">
              {efficiency?.overall_efficiency_pct ? `${efficiency.overall_efficiency_pct.toFixed(1)}%` : '0.0%'}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Active utilization vs requests</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Monthly Requested</span>
              <CircleDollarSign className="size-4 text-slate-400" />
            </div>
            <div className="mt-3 text-2xl font-bold">
              {formatCurrency(efficiency?.monthly_requested_cost || 0.0, currency)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Allocated cluster cost/mo</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Recoverable Idle Waste</span>
              <AlertTriangle className="size-4 text-amber-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-amber-400">
              {formatCurrency(efficiency?.monthly_idle_waste || 0.0, currency)}/mo
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Unused reserved CPU & memory</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Active Workloads</span>
              <Server className="size-4 text-emerald-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-emerald-300">
              {formatInteger(efficiency?.total_workloads || allocations.length || 0)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Across {namespaces.length > 1 ? namespaces.length - 1 : 0} namespaces</div>
          </CardContent>
        </Card>
      </div>

      <div className="mb-6">
        <div className="mb-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <h2 className="text-base sm:text-lg font-semibold tracking-tight">Overprovisioned Workloads & Rightsizing Recommendations</h2>
          <Badge variant="outline" className="border-emerald-400/30 text-emerald-300 w-fit">
            {recommendations.length} Actionable Rightsizing Diffs
          </Badge>
        </div>
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i} className="border-white/8 bg-card/70 p-5 space-y-3">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-8 w-28 ml-auto" />
              </Card>
            ))}
          </div>
        ) : (!Array.isArray(recommendations) || recommendations.length === 0) ? (
          <EmptyState
            icon={Layers}
            title="All Workloads Optimized"
            description="Kubernetes CPU and memory requests align with actual telemetry. No rightsizing required."
            className="my-4 py-10"
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recommendations.map((rec: any, idx: number) => (
              <Card key={`${rec.workload}-${idx}`} className="border-white/8 bg-card/70">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline" className="border-white/10 text-xs">{rec.namespace}</Badge>
                    <span className="text-xs font-semibold text-emerald-400">
                      +{formatCurrency(rec.monthly_savings, currency)}/mo
                    </span>
                  </div>
                  <CardTitle className="pt-2 text-base font-semibold">{rec.workload}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 text-xs">
                  <div className="grid grid-cols-2 gap-2 rounded-lg border border-white/8 bg-white/5 p-2.5">
                    <div>
                      <span className="text-muted-foreground">CPU Request:</span>
                      <div className="font-mono font-medium text-amber-300">{rec.current_cpu} ➔ <span className="text-emerald-300">{rec.recommended_cpu}</span></div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">RAM Request:</span>
                      <div className="font-mono font-medium text-amber-300">{rec.current_memory} ➔ <span className="text-emerald-300">{rec.recommended_memory}</span></div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-muted-foreground">Kind: <b>{rec.kind || 'Deployment'}</b></span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-cyan-400/30 bg-cyan-400/10 text-xs text-cyan-300 hover:bg-cyan-400/20"
                      onClick={() => { setActiveYamlDiff(rec.yaml_diff); setCopied(false); }}
                    >
                      View YAML Diff
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <Card className="border-white/8 bg-card/70">
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <CardTitle className="text-base font-semibold">Workload Allocations by Namespace</CardTitle>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Filter Namespace:</span>
            <Select value={selectedNamespace} onValueChange={(val: string | null) => { if (val) setSelectedNamespace(val) }}>
              <SelectTrigger className="h-8 w-36 border-white/10 bg-white/5 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {namespaces.map((ns: string) => (
                  <SelectItem key={ns} value={ns}>{ns.toUpperCase()}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <TableSkeleton rows={5} cols={8} />
          ) : filteredAllocations.length === 0 ? (
            selectedNamespace !== 'all' ? (
              <EmptyState
                icon={Server}
                title="No Workload Allocations Found"
                description={`No pods or deployments found in namespace "${selectedNamespace}".`}
                action={
                  <Button variant="outline" size="sm" onClick={() => setSelectedNamespace('all')}>
                    Show all namespaces
                  </Button>
                }
                className="my-4 border-0"
              />
            ) : (
              <div className="rounded-xl border border-dashed border-white/15 bg-white/[0.02] p-8 text-center my-4">
                <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-400 mb-4">
                  <Cpu className="size-6" />
                </div>
                <h3 className="text-base font-semibold text-foreground">Waiting for Live Kubernetes Telemetry</h3>
                <p className="mt-1.5 max-w-md mx-auto text-xs text-muted-foreground">
                  CloudPulse is running in 100% real-time mode with all mock data removed. Connect your OpenCost endpoint or trigger a cluster scan to stream live pod allocations.
                </p>
                <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                  <Button
                    size="sm"
                    onClick={() => setShowConfigModal(true)}
                    className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 text-xs"
                  >
                    <Settings className="mr-1.5 size-3.5" />
                    Configure OpenCost Endpoint
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={syncing}
                    onClick={handleSyncTelemetry}
                    className="border-white/10 bg-white/5 text-xs text-foreground hover:bg-white/10"
                  >
                    <RefreshCw className={`mr-1.5 size-3.5 ${syncing ? 'animate-spin' : ''}`} />
                    {syncing ? 'Scanning Cluster...' : 'Scan Cluster (kubectl)'}
                  </Button>
                </div>
              </div>
            )
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-white/8 hover:bg-transparent">
                    <TableHead className="text-xs">Workload</TableHead>
                    <TableHead className="text-xs">Namespace</TableHead>
                    <TableHead className="text-xs">Kind</TableHead>
                    <TableHead className="text-xs text-right">CPU (Req / Util)</TableHead>
                    <TableHead className="text-xs text-right">RAM (Req / Util)</TableHead>
                    <TableHead className="text-xs text-right">Monthly Spend</TableHead>
                    <TableHead className="text-xs text-right">Idle Waste</TableHead>
                    <TableHead className="text-xs text-right">Efficiency</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAllocations.map((alloc: any, idx: number) => (
                  <TableRow key={`${alloc.workload}-${idx}`} className="border-white/8">
                    <TableCell className="font-mono text-xs font-semibold text-cyan-300">{alloc.workload}</TableCell>
                    <TableCell className="text-xs">{alloc.namespace}</TableCell>
                    <TableCell className="text-xs">{alloc.kind}</TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {alloc.requested_cpu_cores} / {alloc.utilized_cpu_cores}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {alloc.requested_ram_gib}G / {alloc.utilized_ram_gib}G
                    </TableCell>
                    <TableCell className="text-right font-semibold text-xs">
                      {formatCurrency(alloc.monthly_requested_cost, currency)}
                    </TableCell>
                    <TableCell className="text-right text-xs font-semibold text-amber-400">
                      {formatCurrency(alloc.monthly_idle_waste, currency)}
                    </TableCell>
                    <TableCell className="text-right text-xs">
                      <Badge
                        variant="outline"
                        className={
                          alloc.overall_efficiency_pct > 60
                            ? 'border-emerald-400/30 text-emerald-300'
                            : 'border-amber-400/30 text-amber-300'
                        }
                      >
                        {alloc.overall_efficiency_pct?.toFixed(1)}%
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
      </Card>

      <Dialog open={!!activeYamlDiff} onOpenChange={() => setActiveYamlDiff(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto border-white/10 bg-slate-950 text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <FileCode className="size-4 text-cyan-400" />
              1-Click Kubernetes Rightsizing YAML Patch
            </DialogTitle>
            <DialogDescription>
              Review the production YAML resource request diff generated against real-world P95 utilization.
            </DialogDescription>
          </DialogHeader>
          <div className="relative mt-2">
            <pre className="max-h-80 overflow-auto rounded-lg border border-white/10 bg-black/60 p-4 font-mono text-xs text-emerald-300">
              {activeYamlDiff}
            </pre>
            <Button
              size="sm"
              variant="outline"
              className="absolute right-3 top-3 border-white/10 bg-white/5 text-xs"
              onClick={() => {
                if (activeYamlDiff) {
                  navigator.clipboard.writeText(activeYamlDiff);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }
              }}
            >
              {copied ? <Check className="mr-1 size-3 text-emerald-400" /> : <Copy className="mr-1 size-3" />}
              {copied ? 'Copied' : 'Copy Patch'}
            </Button>
          </div>
          <div className="flex justify-end pt-2">
            <Button size="sm" className="bg-cyan-400 text-slate-950 hover:bg-cyan-300" onClick={() => setActiveYamlDiff(null)}>
              Done
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Configure OpenCost Telemetry Endpoint Dialog */}
      <Dialog open={showConfigModal} onOpenChange={setShowConfigModal}>
        <DialogContent className="border-white/10 bg-slate-950 text-foreground max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <Settings className="size-4 text-cyan-400" />
              Configure Live OpenCost Telemetry
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Connect CloudPulse directly to your live Kubernetes cluster OpenCost API or in-cluster proxy.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground">OpenCost Allocation Endpoint</label>
              <Input
                value={customOpencostUrl}
                onChange={e => setCustomOpencostUrl(e.target.value)}
                placeholder="http://localhost:9003"
                className="font-mono text-xs border-white/10 bg-white/5"
              />
              <p className="text-[11px] text-muted-foreground">
                Default OpenCost port is 9003. When using port-forward: <code className="text-cyan-300">kubectl port-forward -n opencost svc/opencost 9003:9003</code>
              </p>
            </div>

            <div className="rounded-lg border border-white/8 bg-white/5 p-3 text-xs space-y-2">
              <div className="font-semibold text-slate-200">How to stream real-time cluster telemetry:</div>
              <div className="text-[11px] text-muted-foreground space-y-1">
                <div>1. <b>Install OpenCost</b>: <code className="text-emerald-300">helm install opencost --repo https://opencost.github.io/opencost-helm-chart opencost --namespace opencost --create-namespace</code></div>
                <div>2. <b>Port-Forward</b>: <code className="text-emerald-300">kubectl port-forward -n opencost svc/opencost 9003:9003</code></div>
                <div>3. <b>Direct Scan</b>: If your kubectl has an active context, CloudPulse automatically discovers pods, deployments, and node allocations.</div>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setShowConfigModal(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={configSaving}
              onClick={handleSaveConfig}
              className="bg-cyan-400 text-slate-950 hover:bg-cyan-300"
            >
              {configSaving ? 'Connecting...' : 'Connect & Sync'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}


export default KubernetesView
