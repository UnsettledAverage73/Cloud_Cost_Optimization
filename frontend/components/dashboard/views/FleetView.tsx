'use client'

import React, { useState, useEffect, useCallback, useMemo, useDeferredValue } from 'react'
import {
  Activity,
  CircleDollarSign,
  Loader2,
  Network,
  Play,
  Plus,
  Search,
  Server,
  Layers,
  ShieldCheck,
  Cpu,
  FileSpreadsheet,
  ChevronRight,
  ChevronDown,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  TrendingUp,
  GitPullRequest,
  Copy,
  Check,
  Sliders
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState, TableSkeleton } from '@/components/empty-state'
import { SectionTitle } from '@/components/dashboard'
import { validateForm, enrollAccountSchema } from '@/lib/validations/forms'
import { addBreadcrumb, captureException } from '@/lib/monitoring/logger'
import { formatCurrency, formatInteger } from '@/lib/formatters'
import type { Currency } from '@/types/dashboard'

export function FleetView({ currency = 'USD', apiUrl }: { currency: 'USD' | 'INR'; apiUrl: (path: string) => string }) {
  const [activeTab, setActiveTab] = useState<'accounts' | 'workloads' | 'guardrails' | 'commitments'>('accounts');
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<any>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [discoverResult, setDiscoverResult] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanFeedback, setScanFeedback] = useState<any | null>(null);
  const [scanningAccId, setScanningAccId] = useState<string | null>(null);

  // Hyperscale Workload Tree State
  const [workloadTree, setWorkloadTree] = useState<any>(null);
  const [expandedTeams, setExpandedTeams] = useState<Record<string, boolean>>({});
  const [curSyncing, setCurSyncing] = useState(false);
  const [curSyncResult, setCurSyncResult] = useState<any | null>(null);

  // Policy Guardrails State
  const [policies, setPolicies] = useState<any[]>([]);
  const [policyEval, setPolicyEval] = useState<any | null>(null);
  const [evaluatingPolicies, setEvaluatingPolicies] = useState(false);
  const [simulateHyperscale, setSimulateHyperscale] = useState(true);

  // Remediation Modal State
  const [remediateModalOpen, setRemediateModalOpen] = useState(false);
  const [remediationData, setRemediationData] = useState<any | null>(null);
  const [remediatingPolicyId, setRemediatingPolicyId] = useState<string | null>(null);
  const [copiedTf, setCopiedTf] = useState(false);

  // Commitment Portfolio State
  const [portfolio, setPortfolio] = useState<any | null>(null);
  const [coverageTarget, setCoverageTarget] = useState<number>(0.75);
  const [loadingPortfolio, setLoadingPortfolio] = useState(false);
  const [copiedCli, setCopiedCli] = useState(false);

  // Enroll Account state
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [newAccId, setNewAccId] = useState('');
  const [newAccName, setNewAccName] = useState('');
  const [newAccRole, setNewAccRole] = useState('');
  const [newAccRegion, setNewAccRegion] = useState('us-east-1');
  const [isMgmtAcc, setIsMgmtAcc] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollErrors, setEnrollErrors] = useState<Record<string, string>>({});

  const fetchFleet = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, accRes, treeRes, polRes] = await Promise.all([
        fetch(apiUrl('/api/v2/fleet/summary')),
        fetch(apiUrl('/api/v2/fleet/accounts')),
        fetch(apiUrl('/api/v2/workloads/tree')),
        fetch(apiUrl('/api/v2/policies'))
      ]);
      if (sumRes.ok) setSummary(await sumRes.json());
      if (accRes.ok) {
        const d = await accRes.json();
        setAccounts(Array.isArray(d?.accounts) ? d.accounts : []);
      }
      if (treeRes.ok) setWorkloadTree(await treeRes.json());
      if (polRes.ok) {
        const p = await polRes.json();
        setPolicies(p?.policies || []);
      }
    } catch (err) {
      console.error('Failed to load fleet data:', err);
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    fetchFleet();
  }, [fetchFleet]);

  const handleDiscover = async () => {
    setDiscovering(true);
    setDiscoverResult(null);
    try {
      const res = await fetch(apiUrl('/api/v2/fleet/discover'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_name: 'CloudPulseReadOnlyRole' }),
      });
      const data = await res.json();
      if (res.ok) {
        setDiscoverResult(`✅ Successfully auto-discovered ${data.discovered_count} member accounts via AWS Organizations API!`);
        await fetchFleet();
      } else {
        setDiscoverResult(`❌ Discovery error: ${data.detail || 'Could not reach AWS Organizations'}`);
      }
    } catch (err: any) {
      setDiscoverResult(`❌ Discovery failed: ${err.message}`);
    } finally {
      setDiscovering(false);
    }
  };

  const handleScanFleet = async (specificIds?: string[]) => {
    if (specificIds?.length === 1) {
      setScanningAccId(specificIds[0]);
    } else {
      setScanning(true);
    }
    setScanFeedback(null);
    try {
      const res = await fetch(apiUrl('/api/v2/fleet/scan'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_ids: specificIds }),
      });
      const data = await res.json();
      if (res.ok) {
        setScanFeedback(data);
        await fetchFleet();
      }
    } catch (err) {
      console.error('Parallel fleet scan failed:', err);
    } finally {
      setScanning(false);
      setScanningAccId(null);
    }
  };

  const handleSyncCUR = async () => {
    setCurSyncing(true);
    setCurSyncResult(null);
    try {
      const res = await fetch(apiUrl('/api/v2/cur/sync'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (res.ok) {
        setCurSyncResult(data);
        await fetchFleet();
      }
    } catch (err: any) {
      console.error('CUR sync error:', err);
    } finally {
      setCurSyncing(false);
    }
  };

  const handleEvaluatePolicies = async () => {
    setEvaluatingPolicies(true);
    try {
      const res = await fetch(apiUrl(`/api/v2/policies/evaluate?simulate=${simulateHyperscale}`), { method: 'POST' });
      if (res.ok) {
        setPolicyEval(await res.json());
      }
    } catch (err) {
      console.error('Policy evaluation failed:', err);
    } finally {
      setEvaluatingPolicies(false);
    }
  };

  const handleRemediatePolicy = async (policyId: string, resourceId?: string) => {
    setRemediatingPolicyId(policyId);
    try {
      const res = await fetch(apiUrl(`/api/v2/policies/${policyId}/remediate`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resource_id: resourceId })
      });
      if (res.ok) {
        const data = await res.json();
        setRemediationData(data);
        setRemediateModalOpen(true);
      }
    } catch (err) {
      console.error('Failed to remediate policy:', err);
    } finally {
      setRemediatingPolicyId(null);
    }
  };

  const fetchPortfolio = useCallback(async (target: number) => {
    setLoadingPortfolio(true);
    try {
      const res = await fetch(apiUrl(`/api/v2/commitments/portfolio?coverage_target=${target}`));
      if (res.ok) {
        setPortfolio(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch commitment portfolio:', err);
    } finally {
      setLoadingPortfolio(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    if (activeTab === 'commitments') {
      fetchPortfolio(coverageTarget);
    }
  }, [activeTab, coverageTarget, fetchPortfolio]);

  const handleTogglePolicy = async (policyId: string, currentEnabled: boolean) => {
    try {
      const res = await fetch(apiUrl(`/api/v2/policies/${policyId}/toggle`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_enabled: !currentEnabled })
      });
      if (res.ok) {
        setPolicies(prev => prev.map(p => p.id === policyId ? { ...p, is_enabled: !currentEnabled } : p));
      }
    } catch (err) {
      console.error('Failed to toggle policy:', err);
    }
  };

  const handleEnrollSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnrollErrors({});
    const validation = validateForm(enrollAccountSchema, {
      account_id: newAccId,
      account_name: newAccName,
      role_arn: newAccRole,
      region: newAccRegion,
    });
    if (!validation.success) {
      setEnrollErrors(validation.errors);
      return;
    }
    setEnrolling(true);
    try {
      const payload: any = {
        account_id: newAccId.trim(),
        account_name: newAccName.trim() || `Account-${newAccId.trim()}`,
        region: newAccRegion.trim(),
        is_management_account: isMgmtAcc,
      };
      if (newAccRole.trim()) {
        payload.role_arn = newAccRole.trim();
        payload.external_id = 'CloudPulseEnterpriseSecurityId';
      }
      const res = await fetch(apiUrl('/api/v2/fleet/accounts'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setEnrollOpen(false);
        setNewAccId('');
        setNewAccName('');
        setNewAccRole('');
        await fetchFleet();
      } else {
        const d = await res.json();
        setEnrollErrors({ account_id: d.detail || 'Enrollment rejected by API' });
      }
    } catch (err: any) {
      setEnrollErrors({ account_id: `Network error: ${err.message}` });
    } finally {
      setEnrolling(false);
    }
  };

  const deferredSearch = useDeferredValue(search);
  const filteredAccounts = useMemo(() => {
    if (!deferredSearch) return accounts;
    const lower = deferredSearch.toLowerCase();
    return accounts.filter(
      (a: any) =>
        a.account_id?.toLowerCase().includes(lower) ||
        a.account_name?.toLowerCase().includes(lower) ||
        a.region?.toLowerCase().includes(lower)
    );
  }, [accounts, deferredSearch]);

  const totalMonthlySpend = summary?.total_fleet_monthly_spend ?? 0;
  const totalNodes = summary?.total_fleet_nodes ?? 0;
  const totalVolumes = summary?.total_fleet_volumes ?? 0;
  const totalEips = summary?.total_fleet_eips ?? 0;

  return (
    <>
      <SectionTitle
        title="Enterprise Fleet & Hyperscale Workload Manager"
        description="Unified management plane for 50,000+ servers, AWS Organizations, Tag Workload Hierarchies, and Automated FinOps Policy Guardrails."
        action={<Badge variant="outline" className="text-xs">{accounts.length} Accounts Enrolled</Badge>}
      />

      {/* Navigation Tabs */}
      <div className="flex border-b border-border mb-6 gap-2">
        <button
          onClick={() => setActiveTab('accounts')}
          className={`flex items-center gap-2 pb-2.5 px-3 text-xs font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'accounts'
              ? 'border-foreground text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Server className="size-3.5" />
          <span>AWS Accounts Directory</span>
          <Badge variant="outline" className="text-[10px] py-0 px-1 border-border">{accounts.length}</Badge>
        </button>

        <button
          onClick={() => setActiveTab('workloads')}
          className={`flex items-center gap-2 pb-2.5 px-3 text-xs font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'workloads'
              ? 'border-foreground text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Layers className="size-3.5" />
          <span>Workload & Team Hierarchy (50k Scale)</span>
          <Badge variant="outline" className="text-[10px] py-0 px-1 border-border">CUR 2.0</Badge>
        </button>

        <button
          onClick={() => setActiveTab('guardrails')}
          className={`flex items-center gap-2 pb-2.5 px-3 text-xs font-medium transition-colors border-b-2 -mb-px whitespace-nowrap ${
            activeTab === 'guardrails'
              ? 'border-foreground text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <ShieldCheck className="size-3.5" />
          <span>Automated Policy Guardrails</span>
          <Badge variant="outline" className="text-[10px] py-0 px-1 border-border">{policies.length}</Badge>
        </button>

        <button
          onClick={() => setActiveTab('commitments')}
          className={`flex items-center gap-2 pb-2.5 px-3 text-xs font-medium transition-colors border-b-2 -mb-px whitespace-nowrap ${
            activeTab === 'commitments'
              ? 'border-foreground text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <TrendingUp className="size-3.5" />
          <span>Commitment Portfolio & Arbitrage</span>
          <Badge variant="outline" className="text-[10px] py-0 px-1 border-border">Savings Plans</Badge>
        </button>
      </div>

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <Card className="border-border bg-card">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Connected Accounts</span>
              <Network className="size-4 text-foreground" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">
              {formatInteger(accounts.length || 1)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">AWS Organizations auto-synced</div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Fleet-Wide Run Rate</span>
              <CircleDollarSign className="size-4 text-foreground" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">
              {formatCurrency(totalMonthlySpend || workloadTree?.total_monthly_spend || 0, currency)}
              <span className="text-xs font-normal text-muted-foreground ml-1">/mo</span>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Across all member accounts</div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Managed Cloud Footprint</span>
              <Server className="size-4 text-foreground" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">
              {formatInteger(totalNodes + totalVolumes + totalEips || workloadTree?.total_nodes_managed || 0)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {totalNodes || workloadTree?.total_nodes_managed || 0} EC2 · {totalVolumes} EBS · {totalEips} EIPs
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Recoverable Fleet Waste</span>
              <Activity className="size-4 text-foreground" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">
              {formatCurrency(workloadTree?.total_potential_savings || summary?.total_wasted_monthly_spend || 0, currency)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              Identified via automated FinOps policies
            </div>
          </CardContent>
        </Card>
      </div>

      {/* TAB 1: ACCOUNTS DIRECTORY */}
      {activeTab === 'accounts' && (
        <>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                className="border-border text-foreground hover:bg-muted font-medium text-xs"
                onClick={() => handleScanFleet()}
                disabled={scanning}
              >
                {scanning ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Play className="mr-1.5 size-3.5" />}
                {scanning ? 'Sweeping Fleet...' : 'Run Parallel Fleet Scan'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-border text-foreground hover:bg-muted font-medium text-xs"
                onClick={handleDiscover}
                disabled={discovering}
              >
                {discovering ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Network className="mr-1.5 size-3.5" />}
                Auto-Discover Org Accounts
              </Button>
            </div>
            <Button
              size="sm"
              className="bg-primary text-primary-foreground hover:opacity-90 font-medium text-xs"
              onClick={() => setEnrollOpen(true)}
            >
              <Plus className="mr-1.5 size-3.5" /> Enroll Account
            </Button>
          </div>

          {discoverResult && (
            <div className="mb-4 rounded-lg border border-border bg-muted p-3 text-xs text-foreground">
              {discoverResult}
            </div>
          )}

          {scanFeedback && (
            <div className="mb-4 rounded-lg border border-border bg-muted p-3 text-xs text-foreground flex items-center justify-between">
              <span>
                Parallel scan completed across {scanFeedback.scanned_accounts_count || scanFeedback.accounts_scanned} accounts! Total monthly spend analyzed: {formatCurrency(scanFeedback.total_fleet_monthly_spend || 0, currency)}.
              </span>
              <Button variant="ghost" size="sm" className="h-6 text-[11px]" onClick={() => setScanFeedback(null)}>
                Dismiss
              </Button>
            </div>
          )}

          <Card className="border-border bg-card">
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between pb-3">
              <div>
                <CardTitle className="text-sm font-semibold">AWS Member Accounts Directory</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Multi-account inventory with cross-account IAM role assumption and FOCUS 1.0 billing mapping.
                </p>
              </div>
              <div className="w-full sm:w-64">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
                  <Input
                    placeholder="Search account ID or name..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="pl-8 h-8 border-border bg-background text-xs text-foreground"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <TableSkeleton rows={4} cols={6} />
              ) : filteredAccounts.length === 0 ? (
                <EmptyState
                  icon={Server}
                  title={search ? `No accounts matching "${search}"` : "No Fleet Accounts Enrolled"}
                  description={search ? "Try adjusting your search query." : "Click 'Auto-Discover Org Accounts' or 'Enroll Account' to start multi-account management."}
                  action={
                    <Button size="sm" className="bg-primary text-primary-foreground hover:opacity-90" onClick={handleDiscover}>
                      Auto-Discover Org Accounts
                    </Button>
                  }
                  className="my-4 border-0"
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-border hover:bg-transparent">
                        <TableHead className="text-xs">Account ID</TableHead>
                        <TableHead className="text-xs">Account Name</TableHead>
                        <TableHead className="text-xs">Region</TableHead>
                        <TableHead className="text-xs">Auth Type</TableHead>
                        <TableHead className="text-xs">Status</TableHead>
                        <TableHead className="text-xs text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredAccounts.map((acc: any) => (
                        <TableRow key={acc.account_id} className="border-border hover:bg-muted/40 text-xs">
                          <TableCell className="font-mono font-medium">{acc.account_id}</TableCell>
                          <TableCell className="font-medium">
                            {acc.account_name}
                            {acc.is_management_account && (
                              <Badge variant="outline" className="ml-2 text-[10px] border-border py-0">Payer</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-muted-foreground">{acc.region || 'us-east-1'}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="font-mono text-[10px] border-border">
                              {acc.auth_type || 'assume_role'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <span className="inline-flex items-center gap-1.5 text-foreground font-medium">
                              <span className="size-1.5 rounded-full bg-foreground" />
                              Active
                            </span>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs border border-border hover:bg-muted"
                              onClick={() => handleScanFleet([acc.account_id])}
                              disabled={scanningAccId === acc.account_id}
                            >
                              {scanningAccId === acc.account_id ? (
                                <Loader2 className="size-3 animate-spin mr-1" />
                              ) : (
                                <Play className="size-3 mr-1" />
                              )}
                              Scan
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* TAB 2: HYPERSCALE WORKLOAD & TEAM HIERARCHY */}
      {activeTab === 'workloads' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-border bg-card">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Zero-API AWS CUR 2.0 Parquet Lakehouse</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Ingest 50,000+ instances directly from S3 billing exports via DuckDB in &lt;15ms with 0 AWS rate-limits.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="border-border text-foreground hover:bg-muted text-xs font-medium"
              onClick={handleSyncCUR}
              disabled={curSyncing}
            >
              {curSyncing ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <RefreshCw className="size-3.5 mr-1.5" />}
              {curSyncing ? 'Ingesting Parquet...' : 'Sync AWS CUR 2.0 Parquet'}
            </Button>
          </div>

          {curSyncResult && (
            <div className="rounded-lg border border-border bg-muted p-3 text-xs text-foreground flex items-center justify-between">
              <span>
                ⚡ DuckDB Lakehouse ingested <b>{curSyncResult.records_ingested}</b> FOCUS billing records in <b>{curSyncResult.ingestion_latency_ms}ms</b> with zero AWS API calls!
              </span>
              <Button variant="ghost" size="sm" className="h-6 text-[11px]" onClick={() => setCurSyncResult(null)}>
                Dismiss
              </Button>
            </div>
          )}

          {/* Workload Tree Structure */}
          <div className="space-y-3">
            {workloadTree?.accounts?.map((acc: any) => (
              <Card key={acc.account_id} className="border-border bg-card">
                <CardHeader className="p-4 pb-2 border-b border-border/40">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Server className="size-4 text-foreground" />
                      <span className="font-semibold text-sm text-foreground">{acc.account_name}</span>
                      <span className="font-mono text-xs text-muted-foreground">({acc.account_id})</span>
                    </div>
                    <div className="flex items-center gap-4 text-xs">
                      <span>Total Spend: <b>{formatCurrency(acc.total_spend, currency)}/mo</b></span>
                      <span className="text-muted-foreground">Potential Waste: <b>{formatCurrency(acc.potential_savings, currency)}/mo</b></span>
                      <Badge variant="outline" className="text-[11px] border-border">{acc.node_count} Instances</Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-4 pt-3 space-y-3">
                  {acc.teams?.map((tm: any) => {
                    const isExpanded = !!expandedTeams[`${acc.account_id}-${tm.team_name}`];
                    return (
                      <div key={tm.team_name} className="border border-border/60 rounded-md p-3 bg-background">
                        <div
                          className="flex items-center justify-between cursor-pointer select-none"
                          onClick={() => setExpandedTeams(prev => ({
                            ...prev,
                            [`${acc.account_id}-${tm.team_name}`]: !prev[`${acc.account_id}-${tm.team_name}`]
                          }))}
                        >
                          <div className="flex items-center gap-2">
                            {isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                            <span className="font-semibold text-xs text-foreground">Team: {tm.team_name}</span>
                            <Badge variant="outline" className="text-[10px] border-border py-0">{tm.node_count} nodes</Badge>
                          </div>
                          <div className="flex items-center gap-4 text-xs">
                            <span>Monthly: <b>{formatCurrency(tm.total_spend, currency)}</b></span>
                            <span className="text-muted-foreground">Recoverable: <b>+{formatCurrency(tm.potential_savings, currency)}</b></span>
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="mt-3 pl-4 border-l-2 border-border space-y-2">
                            {tm.workloads?.map((wl: any) => (
                              <div key={wl.workload_name} className="p-2.5 rounded bg-muted/40 text-xs flex items-center justify-between">
                                <div>
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium text-foreground">{wl.workload_name}</span>
                                    <Badge variant="outline" className="text-[10px] py-0 border-border uppercase">
                                      {wl.environment}
                                    </Badge>
                                    {wl.idle_nodes_count > 0 && (
                                      <Badge variant="outline" className="text-[10px] py-0 border-border text-foreground">
                                        ⚠️ {wl.idle_nodes_count} Idle Nodes
                                      </Badge>
                                    )}
                                  </div>
                                  <p className="text-[11px] text-muted-foreground mt-0.5">
                                    Avg CPU: {wl.avg_cpu_utilization}% · {wl.node_count} instances in workload fleet
                                  </p>
                                </div>
                                <div className="text-right">
                                  <div><b>{formatCurrency(wl.total_spend, currency)}/mo</b></div>
                                  <div className="text-[11px] text-muted-foreground">Save +{formatCurrency(wl.potential_savings, currency)}</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: AUTOMATED POLICY GUARDRAILS */}
      {activeTab === 'guardrails' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-border bg-card">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Automated FinOps Policy Guardrails</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Continuously evaluates 50,000+ resources against idle CPU, detached storage, and scheduling rules.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={simulateHyperscale}
                  onChange={e => setSimulateHyperscale(e.target.checked)}
                  className="rounded border-border accent-foreground size-3.5"
                />
                <span>Simulate 50k Fleet</span>
              </label>
              <Button
                size="sm"
                className="bg-primary text-primary-foreground hover:opacity-90 text-xs font-medium"
                onClick={handleEvaluatePolicies}
                disabled={evaluatingPolicies}
              >
                {evaluatingPolicies ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <Play className="size-3.5 mr-1.5" />}
                {evaluatingPolicies ? 'Evaluating Fleet...' : 'Run Guardrails Fleet Sweep'}
              </Button>
            </div>
          </div>

          {policyEval && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
              <div className="p-4 border border-border rounded-lg bg-card">
                <span className="text-xs text-muted-foreground">Violations Detected</span>
                <div className="text-2xl font-bold mt-1 text-foreground">{policyEval.total_violations_detected}</div>
                <span className="text-[11px] text-muted-foreground">Across {policyEval.total_active_policies} active policies</span>
              </div>
              <div className="p-4 border border-border rounded-lg bg-card">
                <span className="text-xs text-muted-foreground">Total Recoverable Waste</span>
                <div className="text-2xl font-bold mt-1 text-foreground">
                  {formatCurrency(policyEval.total_recoverable_monthly_savings, currency)}/mo
                </div>
                <span className="text-[11px] text-muted-foreground">Available for instant 1-click remediation</span>
              </div>
              <div className="p-4 border border-border rounded-lg bg-card">
                <span className="text-xs text-muted-foreground">Evaluation Latency</span>
                <div className="text-2xl font-bold mt-1 text-foreground">{policyEval.execution_time_ms}ms</div>
                <span className="text-[11px] text-muted-foreground">Sub-millisecond policy engine</span>
              </div>
            </div>
          )}

          <div className="space-y-3">
            {policies.map(pol => {
              const evalItem = policyEval?.policy_evaluations?.find((e: any) => e.policy?.id === pol.id);
              const violationCount = evalItem?.violation_count || 0;
              const potSavings = evalItem?.potential_monthly_savings || 0;

              return (
                <Card key={pol.id} className="border-border bg-card">
                  <CardContent className="p-4 space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-sm text-foreground">{pol.name}</span>
                          <Badge variant="outline" className="text-[10px] py-0 border-border uppercase">
                            {pol.severity}
                          </Badge>
                          <Badge variant="outline" className="text-[10px] py-0 border-border">
                            {pol.category}
                          </Badge>
                          {violationCount > 0 && (
                            <Badge variant="outline" className="text-[10px] py-0 border-border text-foreground font-semibold">
                              {violationCount} Violations
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">{pol.description}</p>
                        <p className="text-[11px] font-mono text-muted-foreground">Condition: {pol.condition} &rarr; Action: {pol.action}</p>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        {violationCount > 0 && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs border-border flex items-center gap-1.5"
                            onClick={() => handleRemediatePolicy(pol.id)}
                            disabled={remediatingPolicyId === pol.id}
                          >
                            {remediatingPolicyId === pol.id ? (
                              <Loader2 className="size-3 animate-spin" />
                            ) : (
                              <GitPullRequest className="size-3" />
                            )}
                            <span>1-Click Remediate PR ({formatCurrency(potSavings, currency)}/mo)</span>
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          className={`h-7 text-xs border-border font-medium ${pol.is_enabled ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'}`}
                          onClick={() => handleTogglePolicy(pol.id, pol.is_enabled)}
                        >
                          {pol.is_enabled ? 'Enabled' : 'Disabled'}
                        </Button>
                      </div>
                    </div>

                    {evalItem?.matched_resources && evalItem.matched_resources.length > 0 && (
                      <div className="pt-2 border-t border-border/60">
                        <span className="text-[11px] font-medium text-muted-foreground block mb-1.5">Sample Non-Compliant Resources:</span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                          {evalItem.matched_resources.slice(0, 3).map((r: any, idx: number) => (
                            <div key={idx} className="p-2 rounded border border-border/60 bg-muted/20 text-xs">
                              <div className="font-mono text-[11px] font-semibold text-foreground truncate">{r.resource_id}</div>
                              <div className="text-[11px] text-muted-foreground truncate">{r.name} &bull; {r.metric}</div>
                              <div className="text-[11px] text-foreground font-medium mt-0.5">Recover +{formatCurrency(r.recoverable_savings, currency)}/mo</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 4: COMMITMENT PORTFOLIO & ARBITRAGE */}
      {activeTab === 'commitments' && (
        <div className="space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-border bg-card">
            <div>
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <TrendingUp className="size-4" /> Enterprise Savings Plans & RI Commitment Portfolio
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Automated rate arbitrage for steady-state compute floor across AWS Organizations with zero downtime risk.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-xs">
                <Sliders className="size-3.5 text-muted-foreground" />
                <span className="text-muted-foreground">Target Coverage:</span>
                <span className="font-bold text-foreground">{Math.round(coverageTarget * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.50"
                max="0.95"
                step="0.05"
                value={coverageTarget}
                onChange={e => setCoverageTarget(parseFloat(e.target.value))}
                className="w-32 accent-foreground cursor-pointer"
              />
            </div>
          </div>

          {loadingPortfolio ? (
            <div className="p-12 text-center">
              <Loader2 className="size-6 animate-spin mx-auto text-muted-foreground" />
              <p className="text-xs text-muted-foreground mt-2">Modeling commitment scenarios...</p>
            </div>
          ) : portfolio ? (
            <>
              {/* Financial KPI Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="border-border bg-card">
                  <CardContent className="p-4">
                    <span className="text-xs text-muted-foreground">Steady-State Baseline</span>
                    <div className="text-2xl font-bold mt-1 text-foreground">
                      {formatCurrency(portfolio.steady_state_monthly_compute, currency)}/mo
                    </div>
                    <span className="text-[11px] text-muted-foreground">24/7 minimum compute floor</span>
                  </CardContent>
                </Card>

                <Card className="border-border bg-card">
                  <CardContent className="p-4">
                    <span className="text-xs text-muted-foreground">Hourly Commitment Target</span>
                    <div className="text-2xl font-bold mt-1 text-foreground">
                      ${portfolio.recommended_hourly_commitment}/hr
                    </div>
                    <span className="text-[11px] text-muted-foreground">
                      At {Math.round(portfolio.coverage_target_ratio * 100)}% coverage
                    </span>
                  </CardContent>
                </Card>

                <Card className="border-border bg-card">
                  <CardContent className="p-4">
                    <span className="text-xs text-muted-foreground">Discounted Spend Share</span>
                    <div className="text-2xl font-bold mt-1 text-foreground">
                      {formatCurrency(portfolio.covered_monthly_spend, currency)}/mo
                    </div>
                    <span className="text-[11px] text-muted-foreground">Protected against on-demand pricing</span>
                  </CardContent>
                </Card>

                <Card className="border-border bg-card">
                  <CardContent className="p-4">
                    <span className="text-xs text-muted-foreground">On-Demand Risk Exposure</span>
                    <div className="text-2xl font-bold mt-1 text-foreground">
                      {formatCurrency(portfolio.on_demand_exposed_monthly_spend, currency)}/mo
                    </div>
                    <span className="text-[11px] text-muted-foreground">Buffer for elasticity & scaling</span>
                  </CardContent>
                </Card>
              </div>

              {/* Plan Options Comparison */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {portfolio.plans?.map((p: any) => (
                  <Card key={p.plan_id} className={`border-border bg-card flex flex-col justify-between ${p.recommended ? 'ring-1 ring-foreground' : ''}`}>
                    <CardHeader className="p-4 pb-2">
                      <div className="flex items-center justify-between mb-1">
                        <Badge variant="outline" className="text-[10px] py-0 border-border uppercase">
                          {p.term}
                        </Badge>
                        {p.recommended && (
                          <Badge className="bg-foreground text-background text-[10px] py-0 font-medium">
                            Recommended
                          </Badge>
                        )}
                      </div>
                      <CardTitle className="text-sm font-semibold text-foreground">{p.name}</CardTitle>
                      <p className="text-xs text-muted-foreground mt-1">
                        Locks in a {Math.round(p.discount_rate * 100)}% effective discount rate.
                      </p>
                    </CardHeader>
                    <CardContent className="p-4 pt-2 space-y-3">
                      <div className="p-3 rounded border border-border bg-muted/20">
                        <div className="text-xs text-muted-foreground">Projected Annual Savings</div>
                        <div className="text-xl font-bold text-foreground mt-0.5">
                          {formatCurrency(p.annual_savings, currency)}/yr
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {formatCurrency(p.monthly_savings, currency)}/mo net savings
                        </div>
                      </div>

                      <div className="space-y-1.5 text-xs">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Upfront Cost:</span>
                          <span className="font-semibold text-foreground">$0.00 (No Upfront)</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Break-Even Period:</span>
                          <span className="font-semibold text-foreground">Day 1 (Immediate ROI)</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Risk Classification:</span>
                          <span className="font-semibold text-foreground">{p.risk_level}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* IaC Automation Block */}
              <Card className="border-border bg-card">
                <CardHeader className="p-4 pb-2">
                  <CardTitle className="text-sm font-semibold text-foreground">Infrastructure as Code (IaC) Execution Template</CardTitle>
                  <p className="text-xs text-muted-foreground mt-0.5">Deploy via GitOps pipeline or execute via AWS CLI to activate savings.</p>
                </CardHeader>
                <CardContent className="p-4 pt-2 space-y-3">
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono font-medium text-foreground">terraform/commitments.tf</span>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 text-[11px] border-border"
                        onClick={() => {
                          navigator.clipboard.writeText(portfolio.iac_templates.terraform);
                          setCopiedTf(true);
                          setTimeout(() => setCopiedTf(false), 2000);
                        }}
                      >
                        {copiedTf ? <Check className="size-3 mr-1" /> : <Copy className="size-3 mr-1" />}
                        {copiedTf ? 'Copied' : 'Copy HCL'}
                      </Button>
                    </div>
                    <pre className="p-3 rounded bg-muted/40 border border-border text-[11px] font-mono text-foreground overflow-x-auto whitespace-pre">
                      {portfolio.iac_templates.terraform}
                    </pre>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono font-medium text-foreground">AWS CLI Command</span>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 text-[11px] border-border"
                        onClick={() => {
                          navigator.clipboard.writeText(portfolio.iac_templates.aws_cli);
                          setCopiedCli(true);
                          setTimeout(() => setCopiedCli(false), 2000);
                        }}
                      >
                        {copiedCli ? <Check className="size-3 mr-1" /> : <Copy className="size-3 mr-1" />}
                        {copiedCli ? 'Copied' : 'Copy CLI'}
                      </Button>
                    </div>
                    <pre className="p-3 rounded bg-muted/40 border border-border text-[11px] font-mono text-foreground overflow-x-auto whitespace-pre">
                      {portfolio.iac_templates.aws_cli}
                    </pre>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : null}
        </div>
      )}


      {/* Enroll Account Modal */}
      <Dialog open={enrollOpen} onOpenChange={setEnrollOpen}>
        <DialogContent className="border-border bg-background sm:max-w-lg w-[95vw] max-h-[90vh] overflow-y-auto p-6 text-foreground shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-sm font-semibold">Enroll AWS Account in Fleet</DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Register an AWS member account for multi-account parallel FinOps auditing and FOCUS lakehouse ingestion.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEnrollSubmit} className="space-y-3 pt-2 text-xs">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">AWS Account ID (12 digits) *</label>
              <Input
                placeholder="123456789012"
                value={newAccId}
                onChange={e => setNewAccId(e.target.value)}
                className="font-mono border-border bg-background text-xs text-foreground"
              />
              {enrollErrors.account_id && (
                <p className="mt-1 text-[11px] text-muted-foreground underline">{enrollErrors.account_id}</p>
              )}
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Account Display Name</label>
              <Input
                placeholder="Production-Workloads-EKS"
                value={newAccName}
                onChange={e => setNewAccName(e.target.value)}
                className="border-border bg-background text-xs text-foreground"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Cross-Account IAM Role ARN</label>
              <Input
                placeholder="arn:aws:iam::123456789012:role/CloudPulseReadOnlyRole"
                value={newAccRole}
                onChange={e => setNewAccRole(e.target.value)}
                className="font-mono border-border bg-background text-xs text-foreground"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Primary Region</label>
              <Input
                placeholder="us-east-1"
                value={newAccRegion}
                onChange={e => setNewAccRegion(e.target.value)}
                className="border-border bg-background text-xs text-foreground"
              />
            </div>
            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="isMgmtAcc"
                checked={isMgmtAcc}
                onChange={e => setIsMgmtAcc(e.target.checked)}
                className="rounded border-border accent-primary"
              />
              <label htmlFor="isMgmtAcc" className="text-xs text-muted-foreground cursor-pointer">
                Mark as AWS Organizations Management (Payer) Account
              </label>
            </div>
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-3">
              <Button type="button" variant="ghost" size="sm" onClick={() => setEnrollOpen(false)}>Cancel</Button>
              <Button type="submit" size="sm" className="bg-primary text-primary-foreground hover:opacity-90 font-medium" disabled={enrolling}>
                {enrolling ? <Loader2 className="mr-1 size-3 animate-spin" /> : null} Enroll Account
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* 1-Click Remediation PR Modal */}
      <Dialog open={remediateModalOpen} onOpenChange={setRemediateModalOpen}>
        <DialogContent className="border-border bg-background sm:max-w-2xl lg:max-w-3xl w-[95vw] max-h-[88vh] flex flex-col p-0 gap-0 text-foreground shadow-2xl overflow-hidden">
          <DialogHeader className="p-6 pb-4 border-b border-border shrink-0">
            <DialogTitle className="text-sm font-semibold flex items-center gap-2">
              <GitPullRequest className="size-4" /> Autonomous FinOps GitOps PR Generated
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Production Terraform PR constructed with closed-loop SLA watchdog canary monitoring.
            </DialogDescription>
          </DialogHeader>

          {remediationData && (
            <>
              <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1 text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 p-3 rounded-xl border border-border bg-muted/20">
                  <div>
                    <span className="text-muted-foreground block text-[11px]">GitOps Target Branch</span>
                    <span className="font-mono font-semibold text-foreground truncate block">{remediationData.branch_name}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[11px]">Estimated Monthly Recovery</span>
                    <span className="font-semibold text-foreground">{formatCurrency(remediationData.estimated_monthly_savings, currency)}/mo</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[11px]">SLA Canary Watchdog</span>
                    <span className="font-mono text-foreground">{remediationData.canary_watchdog_id} (60m Window)</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[11px]">Policy Rule</span>
                    <span className="font-semibold text-foreground">{remediationData.policy_name}</span>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-semibold text-xs text-foreground">Generated Terraform / OpenTofu HCL</span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-6 text-[11px] border-border"
                      onClick={() => {
                        navigator.clipboard.writeText(remediationData.terraform_hcl);
                        setCopiedTf(true);
                        setTimeout(() => setCopiedTf(false), 2000);
                      }}
                    >
                      {copiedTf ? <Check className="size-3 mr-1" /> : <Copy className="size-3 mr-1" />}
                      {copiedTf ? 'Copied HCL' : 'Copy HCL'}
                    </Button>
                  </div>
                  <pre className="p-3.5 rounded-xl bg-muted/40 border border-border font-mono text-[11px] text-foreground max-h-64 overflow-y-auto whitespace-pre">
                    {remediationData.terraform_hcl}
                  </pre>
                </div>
              </div>

              <div className="px-6 py-3.5 border-t border-border bg-muted/20 shrink-0 flex items-center justify-end gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs border-border"
                  onClick={() => setRemediateModalOpen(false)}
                >
                  Close
                </Button>
                <Button
                  size="sm"
                  className="bg-primary text-primary-foreground text-xs font-medium"
                  onClick={() => setRemediateModalOpen(false)}
                >
                  Merge via CI/CD GitOps
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

export default FleetView
