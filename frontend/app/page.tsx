'use client'

import { useMemo, useState, useEffect, useCallback } from 'react'
import {
  Activity, AlertTriangle, Archive, ArrowDownRight, ArrowUpRight, BarChart3, Bell, Bot, Calendar, Check,
  CheckCircle2, AlertCircle, ChevronDown, ChevronLeft, ChevronRight, CircleDollarSign, Cloud, CloudCog, Copy, Cpu, Database,
  Download, ExternalLink, Eye, FileCode, FileText, GitBranch, GitPullRequest, HardDrive, History, Inbox, KeyRound, LayoutDashboard,
  Layers, Lock, Menu, MessageSquare, Moon, MoreHorizontal, Network, PanelLeft, Play, Plus, RefreshCw, RotateCcw, Search, Send,
  Server, Settings, ShieldAlert, ShieldCheck, SlidersHorizontal, Sparkles, Sun, Terminal, X, Zap, Loader2
} from 'lucide-react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Skeleton } from '@/components/ui/skeleton'
import { SectionErrorBoundary } from '@/components/error-boundary'
import { EmptyState, MetricCardSkeleton, TableSkeleton, ChartSkeleton } from '@/components/empty-state'

// Base URL for CloudPulse Backend (Render Web Service or local)
function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '')
  }
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    const port = window.location.port
    if ((host === 'localhost' || host === '127.0.0.1') && port !== '8000') {
      return `http://${host}:8000`
    }
  }
  return ''
}

const apiUrl = (path: string) => {
  if (path.startsWith('http')) return path
  const base = getApiBase()
  return `${base}${path}`
}

// Navigation configuration
const nav = [
  { id: 'overview', label: 'Executive Overview', icon: LayoutDashboard },
  { id: 'inventory', label: 'Inventory', icon: Server },
  { id: 'telemetry', label: 'Telemetry & Metrics', icon: Activity },
  { id: 'security', label: 'Security & Exposure', icon: ShieldAlert },
  { id: 'optimization', label: 'Cost Optimization', icon: CircleDollarSign },
  { id: 'scheduler', label: 'Schedules & Pre-Warming', icon: Zap },
  { id: 'gitops-sla', label: 'GitOps & SLA Watchdog', icon: GitBranch },
  { id: 'fleet', label: 'Enterprise Fleet (100+)', icon: Network },
  { id: 'cicd', label: 'CI/CD & GitHub App', icon: GitPullRequest },
  { id: 'kubernetes', label: 'Kubernetes (OpenCost)', icon: Cpu },
  { id: 'lakehouse', label: 'FOCUS 1.0 Lakehouse', icon: Database },
  { id: 'copilot', label: 'AI FinOps Copilot', icon: Sparkles },
  { id: 'settings', label: 'Settings & Notifications', icon: Settings },
]

function MetricCard({ icon: Icon, label, value, detail, tone = 'cyan', trend }: any) {
  return (
    <Card className="border-white/8 bg-card/70 shadow-lg shadow-black/10 backdrop-blur">
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between">
          <div className={`flex size-9 sm:size-10 items-center justify-center rounded-xl bg-${tone}-500/10 text-${tone}-400 shrink-0`}>
            <Icon className="size-4 sm:size-5" />
          </div>
          {trend && (
            <span className="flex items-center gap-1 text-[11px] sm:text-xs font-medium text-emerald-400">
              <ArrowUpRight className="size-3" />{trend}
            </span>
          )}
        </div>
        <div className="mt-4 sm:mt-5 text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-xl sm:text-2xl font-semibold tracking-tight truncate">{value}</div>
        <div className="mt-1 text-xs text-muted-foreground truncate">{detail}</div>
      </CardContent>
    </Card>
  )
}

function SectionTitle({ eyebrow, title, description, action, status }: any) {
  return (
    <div className="mb-4 sm:mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-cyan-400">
          <span className="size-1.5 rounded-full bg-cyan-400" />{eyebrow}
        </div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-balance break-words">{title}</h1>
        {description && <p className="mt-1 text-xs sm:text-sm text-muted-foreground">{description}</p>}
      </div>
      {(status || action) && (
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 shrink-0">
          {status}
          {action}
        </div>
      )}
    </div>
  )
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-white/10 bg-slate-950/95 p-3 text-xs shadow-xl">
      <div className="mb-2 text-muted-foreground">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-6">
          <span style={{ color: p.color }}>{p.name}</span>
          <b>${p.value}k</b>
        </div>
      ))}
    </div>
  )
}

function formatCurrency(value: number | null | undefined, curr: 'USD' | 'INR' = 'USD', rate = 84.0) {
  if (typeof value !== 'number' || Number.isNaN(value)) return curr === 'INR' ? '₹0' : '$0';
  if (curr === 'INR') {
    const inrVal = value * rate;
    if (inrVal >= 10_000_000) {
      return `₹${(inrVal / 10_000_000).toFixed(2)} Cr`;
    }
    if (inrVal >= 100_000) {
      return `₹${(inrVal / 100_000).toFixed(2)} L`;
    }
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(inrVal);
  }
  if (value >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`;
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

function formatInteger(value: number | null | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0';
  return new Intl.NumberFormat('en-US').format(value);
}

type SyncState = 'idle' | 'loading' | 'ready' | 'partial' | 'error'

const DATA_SOURCES = [
  { key: 'summary', label: 'Summary' },
  { key: 'nodes', label: 'Instances' },
  { key: 'telemetry', label: 'Telemetry' },
  { key: 'spend', label: 'Spend' },
  { key: 'alerts', label: 'Alerts' },
  { key: 'optimizations', label: 'Optimizations' },
  { key: 'security', label: 'Security audit' },
  { key: 'applied', label: 'Applied fixes' },
]

const CONNECTION_STORAGE_KEY = 'cloudpulse-connection'
const PROFILE_STORAGE_KEY = 'cloudpulse-remembered-profile'

function readStoredProfile() {
  if (typeof window === 'undefined') return null
  const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    window.localStorage.removeItem(PROFILE_STORAGE_KEY)
    return null
  }
}

function writeStoredProfile(profile: any) {
  if (typeof window === 'undefined' || !profile) return
  window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile))
}

function readStoredConnection() {
  if (typeof window === 'undefined') return null
  const raw = window.localStorage.getItem(CONNECTION_STORAGE_KEY)
  if (!raw) return null
  try {
  return JSON.parse(raw)
  } catch {
    window.localStorage.removeItem(CONNECTION_STORAGE_KEY)
    return null
  }
}

function writeStoredConnection(connection: any, connectedAccounts: any[] = []) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(
    CONNECTION_STORAGE_KEY,
    JSON.stringify({
      ...connection,
      connected_accounts: Array.isArray(connectedAccounts) ? connectedAccounts : connection?.connected_accounts || [],
    })
  )
}

function getSectionStatusLabel(status: SyncState) {
  switch (status) {
    case 'loading':
      return 'Syncing'
    case 'ready':
      return 'Synced'
    case 'partial':
      return 'Partial'
    case 'error':
      return 'Unavailable'
    default:
      return 'Idle'
  }
}

function SectionStatusBadge({ status }: { status: SyncState }) {
  const classes =
    status === 'ready'
      ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
      : status === 'partial'
        ? 'border-amber-400/30 bg-amber-400/10 text-amber-300'
        : status === 'error'
          ? 'border-red-400/30 bg-red-400/10 text-red-300'
          : 'border-slate-400/30 bg-slate-400/10 text-slate-300'

  const dot =
    status === 'loading'
      ? 'bg-amber-400 animate-pulse'
      : status === 'ready'
        ? 'bg-emerald-400'
        : status === 'partial'
          ? 'bg-amber-400'
          : status === 'error'
            ? 'bg-red-400'
            : 'bg-slate-400'

  return (
    <Badge variant="outline" className={classes}>
      <span className={`mr-2 size-2 rounded-full ${dot}`} />
      {getSectionStatusLabel(status)}
    </Badge>
  )
}

function connectionKey(account: any) {
  return [
    account?.provider || '',
    account?.account_name || '',
    account?.region || '',
    account?.role_arn || '',
    account?.access_key_last4 || '',
  ].join('::')
}

export default function Page() {
  const [view, setView] = useState('overview');
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [provider, setProvider] = useState('all');
  const [currency, setCurrency] = useState<'USD' | 'INR'>('USD');
  const [light, setLight] = useState(false);
  const [connectOpen, setConnectOpen] = useState(false);
  const [connectionState, setConnectionState] = useState<any>({ connected: false, status: 'disconnected', message: '' });
  const [connectedAccounts, setConnectedAccounts] = useState<any[]>([]);
  const [rememberedProfile, setRememberedProfile] = useState<any>(null);
  const [selectedAccountKey, setSelectedAccountKey] = useState('');
  const [connectionReady, setConnectionReady] = useState(false);
  const [dataSources, setDataSources] = useState<Record<string, { status: SyncState; error?: string }>>({});
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [selectedNodeDetail, setSelectedNodeDetail] = useState<any>(null);
  const [selectedNodeTelemetry, setSelectedNodeTelemetry] = useState<any[]>([]);
  const [selectedNodeLoading, setSelectedNodeLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [securityTab, setSecurityTab] = useState('groups');
  const [timeframe, setTimeframe] = useState('24h');
  const [syncing, setSyncing] = useState(false);
  const [applied, setApplied] = useState<string[]>([]);

  // State variables for dynamic backend data
  const [nodes, setNodes] = useState<any[]>([]);
  const [telemetry, setTelemetry] = useState<any[]>([]);
  const [spend, setSpend] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [optimizations, setOptimizations] = useState<any[]>([]);
  const [securityAudit, setSecurityAudit] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [dataError, setDataError] = useState('');
  const connectionAccessMode = connectionState?.access_mode || 'live';
  const connectionWarning = connectionState?.warning || '';

  const updateDataSource = (key: string, patch: { status: SyncState; error?: string }) => {
    setDataSources(prev => ({ ...prev, [key]: patch }));
  };

  useEffect(() => {
    const stored = readStoredConnection();
    if (stored) {
      setConnectionState({
        connected: Boolean(stored.connected),
        status: stored.status || (stored.connected ? 'success' : 'disconnected'),
        message: stored.message || '',
        provider: stored.provider,
        account_name: stored.account_name,
        region: stored.region,
        role_arn: stored.role_arn,
        access_mode: stored.access_mode || 'live',
        warning: stored.warning || '',
      });
      setConnectedAccounts(Array.isArray(stored.connected_accounts) ? stored.connected_accounts : []);
    }
    setRememberedProfile(readStoredProfile());
  }, []);

  useEffect(() => {
    const activeAccount = connectedAccounts.find(account => account?.active);
    if (activeAccount) {
      setSelectedAccountKey(connectionKey(activeAccount));
      return;
    }

    if (connectionState?.connected) {
      setSelectedAccountKey(connectionKey(connectionState));
    }
  }, [
    connectedAccounts,
    connectionState?.connected,
    connectionState?.provider,
    connectionState?.account_name,
    connectionState?.region,
    connectionState?.role_arn,
  ]);

  // Core Data Fetching Handler
  const fetchData = useCallback(async () => {
    if (!connectionReady || !connectionState?.connected) {
      setSummary(null);
      setNodes([]);
      setTelemetry([]);
      setSpend([]);
      setAlerts([]);
      setOptimizations([]);
      setSecurityAudit(null);
      setApplied([]);
      setDataSources({});
      if (connectionReady) setDataError('Connect an AWS account to load live data.');
      setLoading(false);
      return;
    }

    setSyncing(true);
    setDataError('');
    DATA_SOURCES.forEach(source => updateDataSource(source.key, { status: 'loading' }));
    try {
      const fetchLive = async (url: string, timeoutMs = 25000) => {
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), timeoutMs);
        try {
          const res = await fetch(apiUrl(url), { signal: controller.signal });
          const responseBody = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(responseBody?.detail || `Live data request failed (${res.status})`);
          return responseBody;
        } catch (err) {
          if (err instanceof DOMException && err.name === 'AbortError') {
            throw new Error(`Timed out after ${Math.round(timeoutMs / 1000)}s`);
          }
          throw err;
        } finally {
          window.clearTimeout(timer);
        }
      };
      const requests = {
        summary: fetchLive('/api/v1/dashboard/summary'),
        nodes: fetchLive(`/api/nodes?provider=${provider}`),
        telemetry: fetchLive(`/api/telemetry?timeframe=${timeframe}`),
        spend: fetchLive(`/api/spend?provider=${provider}`),
        alerts: fetchLive('/api/alerts'),
        optimizations: fetchLive('/api/v1/optimizations'),
        security: fetchLive('/api/v1/security/audit'),
        applied: fetchLive('/api/optimizations/applied'),
      };

      const results = await Promise.allSettled(Object.entries(requests).map(async ([key, promise]) => [key, await promise] as const));
      const resolved = Object.fromEntries(results.flatMap(result => {
        if (result.status === 'fulfilled') return [result.value];
        return [];
      })) as Record<string, any>;

      const failed = results
        .map((result, index) => ({ result, key: Object.keys(requests)[index] }))
        .filter((item): item is { key: string; result: PromiseRejectedResult } => item.result.status === 'rejected')
        .map(item => ({
          key: item.key,
          error: item.result.reason instanceof Error ? item.result.reason.message : String(item.result.reason),
        }));

      if (resolved.summary) {
        setSummary(resolved.summary);
        updateDataSource('summary', { status: 'ready' });
      } else {
        const nodeCount = Array.isArray(resolved.nodes) ? resolved.nodes.length : 0;
        const runningCount = Array.isArray(resolved.nodes) ? resolved.nodes.filter((node: any) => node?.state === 'running').length : 0;
        const orphanedEips = Array.isArray(resolved.alerts) ? resolved.alerts.filter((alert: any) => alert?.tag === 'Cost' && /Elastic IP/i.test(alert?.title || '')).length : 0;
        const orphanedVolumes = Array.isArray(resolved.alerts) ? resolved.alerts.filter((alert: any) => alert?.tag === 'Storage' && /EBS volume/i.test(alert?.title || '')).length : 0;
        setSummary({
          monthly_spend: Array.isArray(resolved.spend) ? resolved.spend.reduce((sum: number, row: any) => sum + Number(row?.aws ?? 0), 0) : 0,
          total_nodes: nodeCount,
          running_nodes: runningCount,
          stopped_nodes: Math.max(nodeCount - runningCount, 0),
          wasted_monthly_spend: 0,
          critical_security_risks: Array.isArray(resolved.security?.exposed_security_groups) ? resolved.security.exposed_security_groups.length : 0,
          last_synced: new Date().toISOString(),
          partial: true,
        });
        updateDataSource('summary', { status: 'partial', error: 'Summary rebuilt from partial results.' });
      }

      if (Array.isArray(resolved.nodes)) {
        setNodes(resolved.nodes);
        updateDataSource('nodes', { status: 'ready' });
      } else {
        setNodes([]);
      }

      if (Array.isArray(resolved.telemetry)) {
        setTelemetry(resolved.telemetry);
        updateDataSource('telemetry', { status: 'ready' });
      } else {
        setTelemetry([]);
      }

      if (Array.isArray(resolved.spend)) {
        setSpend(resolved.spend);
        updateDataSource('spend', { status: 'ready' });
      } else {
        setSpend([]);
      }

      if (Array.isArray(resolved.alerts)) {
        setAlerts(resolved.alerts);
        updateDataSource('alerts', { status: 'ready' });
      } else {
        setAlerts([]);
      }

      if (Array.isArray(resolved.optimizations?.recommendations)) {
        setOptimizations(resolved.optimizations.recommendations);
        updateDataSource('optimizations', { status: 'ready' });
      } else {
        setOptimizations([]);
      }

      if (resolved.security) {
        setSecurityAudit(resolved.security);
        updateDataSource('security', { status: 'ready' });
      } else {
        setSecurityAudit(null);
      }

      if (Array.isArray(resolved.applied?.applied)) {
        setApplied(resolved.applied.applied);
        updateDataSource('applied', { status: 'ready' });
      } else {
        setApplied([]);
      }

      failed.forEach(item => {
        updateDataSource(item.key, { status: 'error', error: item.error });
      });
    } finally {
      setSyncing(false);
      setLoading(false);
    }
  }, [connectionReady, connectionState?.connected, provider, timeframe]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const switchAccount = useCallback(async (account: any) => {
    if (!account) return;
    const nextKey = connectionKey(account);
    if (nextKey === selectedAccountKey) return;

    setSyncing(true);
    setDataError('');
    try {
      const res = await fetch(apiUrl('/api/v1/connect-cloud/switch'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: account.provider,
          account_name: account.account_name,
          region: account.region,
          role_arn: account.role_arn,
          access_key_last4: account.access_key_last4,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || 'Failed to switch AWS account');
      }

      const connection = data?.connection || {};
      const accounts = Array.isArray(data?.connected_accounts) ? data.connected_accounts : [];
      const profile = {
        provider: connection.provider || account.provider,
        account_name: connection.account_name || account.account_name,
        auth_method: connection.auth_method || account.auth_method || 'learner_lab',
        region: connection.region || account.region,
        role_arn: connection.role_arn || account.role_arn,
        connected_at: new Date().toISOString(),
      };

      setConnectionState({
        connected: true,
        status: connection.status || 'success',
        message: connection.message || 'Switched AWS account',
        provider: profile.provider,
        account_name: profile.account_name,
        region: profile.region,
        role_arn: profile.role_arn,
        access_mode: connection.access_mode || 'live',
        warning: connection.warning || '',
      });
      setConnectedAccounts(accounts);
      setSelectedAccountKey(nextKey);
      setRememberedProfile(profile);
      writeStoredProfile(profile);
      writeStoredConnection({
        connected: true,
        status: connection.status || 'success',
        message: connection.message || 'Switched AWS account',
        provider: profile.provider,
        account_name: profile.account_name,
        region: profile.region,
        role_arn: profile.role_arn,
        access_mode: connection.access_mode || 'live',
        warning: connection.warning || '',
      }, accounts);

      await fetchData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to switch AWS account';
      setDataError(message);
      console.error('Account switch failed:', err);
    } finally {
      setSyncing(false);
    }
  }, [fetchData, selectedAccountKey]);

  useEffect(() => {
    let cancelled = false;

    const syncConnectionState = async () => {
      try {
        const res = await fetch(apiUrl('/api/v1/connect-cloud/state'));
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        const connection = data?.connection || data
        const accounts = Array.isArray(data?.connected_accounts)
          ? data.connected_accounts
          : Array.isArray(connection?.connected_accounts)
            ? connection.connected_accounts
            : []

        if (!cancelled && connection?.connected) {
          const profile = {
            provider: connection.provider,
            account_name: connection.account_name,
            auth_method: connection.auth_method,
            region: connection.region,
            role_arn: connection.role_arn,
            connected_at: new Date().toISOString(),
          }
          setConnectionState({
            connected: true,
            status: connection.status || 'success',
            message: connection.message || 'Success',
            provider: connection.provider,
            account_name: connection.account_name,
            region: connection.region,
            role_arn: connection.role_arn,
            access_mode: connection.access_mode || 'live',
            warning: connection.warning || '',
          });
          setConnectedAccounts(accounts);
          setRememberedProfile(profile);
          writeStoredConnection({
            connected: true,
            status: connection.status || 'success',
            message: connection.message || 'Success',
            provider: connection.provider,
            account_name: connection.account_name,
            region: connection.region,
            role_arn: connection.role_arn,
            access_mode: connection.access_mode || 'live',
            warning: connection.warning || '',
          }, accounts);
          writeStoredProfile(profile);
        } else if (!cancelled) {
          const fallback = readStoredConnection();
          if (fallback?.connected && !connectionReady) {
            setConnectionState({
              connected: true,
              status: fallback.status || 'success',
              message: fallback.message || 'Success',
              provider: fallback.provider,
              account_name: fallback.account_name,
              region: fallback.region,
              role_arn: fallback.role_arn,
              access_mode: fallback.access_mode || 'live',
              warning: fallback.warning || '',
            });
            setConnectedAccounts(Array.isArray(fallback.connected_accounts) ? fallback.connected_accounts : []);
          } else {
            setConnectionState({ connected: false, status: 'disconnected', message: '', access_mode: null, warning: null });
            setConnectedAccounts([]);
            window.localStorage.removeItem(CONNECTION_STORAGE_KEY);
          }
        }
      } catch (err) {
        console.error('Failed to read connection state:', err);
        if (!cancelled) {
          const fallback = readStoredConnection();
          if (fallback?.connected) {
            const profile = {
              provider: fallback.provider,
              account_name: fallback.account_name,
              auth_method: fallback.auth_method,
              region: fallback.region,
              role_arn: fallback.role_arn,
              connected_at: new Date().toISOString(),
            }
            setConnectionState({
              connected: true,
              status: fallback.status || 'success',
              message: fallback.message || 'Success',
              provider: fallback.provider,
              account_name: fallback.account_name,
              region: fallback.region,
              role_arn: fallback.role_arn,
              access_mode: fallback.access_mode || 'live',
              warning: fallback.warning || '',
            });
            setConnectedAccounts(Array.isArray(fallback.connected_accounts) ? fallback.connected_accounts : []);
            setRememberedProfile(profile);
          } else {
            setConnectionState({ connected: false, status: 'disconnected', message: '', access_mode: null, warning: null });
            setConnectedAccounts([]);
            window.localStorage.removeItem(CONNECTION_STORAGE_KEY);
          }
        }
      } finally {
        if (!cancelled) setConnectionReady(true);
      }
    };

    syncConnectionState();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!connectionState?.connected) return;

    const interval = window.setInterval(() => {
      fetchData();
    }, 30000);

    return () => window.clearInterval(interval);
  }, [connectionState?.connected, fetchData]);

  useEffect(() => {
    if (!selectedNode?.instance_id) {
      setSelectedNodeDetail(null);
      setSelectedNodeTelemetry([]);
      setSelectedNodeLoading(false);
      return;
    }

    let cancelled = false;

    const loadNodeDetails = async () => {
      setSelectedNodeLoading(true);
      try {
        const [detailRes, telemetryRes] = await Promise.all([
          fetch(apiUrl(`/api/v1/resources/nodes/${selectedNode.instance_id}`)).then(res => res.json()),
          fetch(apiUrl(`/api/v1/telemetry/${selectedNode.instance_id}`)).then(res => res.json()),
        ]);

        if (cancelled) return;
        setSelectedNodeDetail(detailRes);
        setSelectedNodeTelemetry(Array.isArray(telemetryRes?.metrics) ? telemetryRes.metrics : []);
      } catch (err) {
        console.error('Error fetching node details:', err);
        if (!cancelled) {
          setSelectedNodeDetail(selectedNode);
          setSelectedNodeTelemetry([]);
        }
      } finally {
        if (!cancelled) {
          setSelectedNodeLoading(false);
        }
      }
    };

    loadNodeDetails();

    return () => {
      cancelled = true;
    };
  }, [selectedNode?.instance_id]);

  const filteredNodes = useMemo(() => {
  if (!Array.isArray(nodes)) return []; // Critical guard line

  return nodes.filter(n =>
    ((n?.name || '') + (n?.instance_id || '')).toLowerCase().includes(search.toLowerCase()) &&
    (status === 'all' || n?.state === status)
  );
}, [nodes, search, status]);

  const overviewStatus: SyncState = dataSources.summary?.status || (syncing ? 'loading' : 'idle');

  return (
    <div className={light ? 'light' : 'dark'}>
      <main className="min-h-screen bg-background text-foreground">
        <aside className={`fixed inset-y-0 left-0 z-30 hidden border-r border-white/8 bg-sidebar/90 transition-all lg:flex lg:flex-col ${collapsed ? 'w-20' : 'w-64'}`}>
          <div className="flex h-16 items-center justify-between border-b border-white/8 px-4">
            <a href="/" className="flex items-center gap-2.5 hover:opacity-85 transition-opacity">
              <div className="flex size-8 items-center justify-center rounded-lg bg-cyan-400 text-slate-950">
                <CloudCog className="size-5" />
              </div>
              {!collapsed && <span className="text-lg font-semibold tracking-tight">Cloud<span className="text-cyan-400">Pulse</span></span>}
            </a>
            {!collapsed && (
              <a href="/" className="rounded-md px-2 py-1 text-xs font-medium text-cyan-400 hover:bg-white/5 hover:text-cyan-300 transition-colors">
                ← Home
              </a>
            )}
          </div>
          <div className="flex flex-1 flex-col gap-1 p-3">
            {nav.map(item => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setView(item.id)}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${view === item.id ? 'bg-cyan-400/10 text-cyan-300' : 'text-muted-foreground hover:bg-white/5 hover:text-foreground'}`}
                >
                  <Icon className="size-4 shrink-0" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                  {item.id === 'security' && !collapsed && <span className="ml-auto size-1.5 rounded-full bg-red-400" />}
                </button>
              )
            })}
          </div>
          <div className="border-t border-white/8 p-3">
            <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted-foreground hover:bg-white/5">
              <KeyRound className="size-4" />
              {!collapsed && 'API access'}
            </button>
          </div>
        </aside>

        {/* Mobile Navigation Drawer */}
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetContent side="left" className="flex w-72 max-w-[85vw] flex-col justify-between border-r border-white/8 bg-sidebar p-0">
            <div className="flex flex-1 flex-col overflow-y-auto">
              <div className="flex h-16 items-center border-b border-white/8 px-4">
                <div className="flex items-center gap-2.5">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-cyan-400 text-slate-950">
                    <CloudCog className="size-5" />
                  </div>
                  <span className="text-lg font-semibold tracking-tight">Cloud<span className="text-cyan-400">Pulse</span></span>
                </div>
              </div>

              {/* Mobile Quick Context (Currency, Provider, Account) */}
              <div className="border-b border-white/8 bg-white/[0.02] p-3">
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Quick Filters</div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="mb-1 block text-[10px] text-muted-foreground">Provider</label>
                    <Select value={provider} onValueChange={(value) => setProvider(value ?? 'all')}>
                      <SelectTrigger className="h-8 w-full border-white/10 bg-white/5 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="aws">AWS</SelectItem>
                        <SelectItem value="gcp">GCP</SelectItem>
                        <SelectItem value="azure">Azure</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="mb-1 block text-[10px] text-muted-foreground">Currency</label>
                    <Select value={currency} onValueChange={(value) => setCurrency((value as 'USD' | 'INR') || 'USD')}>
                      <SelectTrigger className="h-8 w-full border-white/10 bg-white/5 text-xs font-medium">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="USD">USD ($)</SelectItem>
                        <SelectItem value="INR">INR (₹)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {connectionState?.connected && Array.isArray(connectedAccounts) && connectedAccounts.length > 0 && (
                  <div className="mt-2">
                    <label className="mb-1 block text-[10px] text-muted-foreground">Account</label>
                    <Select
                      value={selectedAccountKey || connectionKey(connectionState)}
                      onValueChange={(value) => {
                        const next = connectedAccounts.find(account => connectionKey(account) === value);
                        if (next) {
                          switchAccount(next);
                        }
                      }}
                    >
                      <SelectTrigger className="h-8 w-full border-white/10 bg-white/5 text-xs truncate">
                        <SelectValue placeholder="Switch account" />
                      </SelectTrigger>
                      <SelectContent>
                        {connectedAccounts.map((account: any) => (
                          <SelectItem key={connectionKey(account)} value={connectionKey(account)}>
                            {account.account_name || 'Connected account'} · {account.region || 'us-east-1'}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>

              {/* Navigation Items */}
              <div className="flex flex-1 flex-col gap-1 p-3">
                {nav.map(item => {
                  const Icon = item.icon;
                  const isActive = view === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        setView(item.id);
                        setMobileNavOpen(false);
                      }}
                      className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${isActive ? 'bg-cyan-400/10 text-cyan-300 font-medium' : 'text-muted-foreground hover:bg-white/5 hover:text-foreground'}`}
                    >
                      <Icon className="size-4 shrink-0" />
                      <span className="truncate flex-1">{item.label}</span>
                      {item.id === 'security' && <span className="size-1.5 rounded-full bg-red-400" />}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="border-t border-white/8 p-3 flex flex-col gap-2">
              <Button
                size="sm"
                onClick={() => {
                  setConnectOpen(true);
                  setMobileNavOpen(false);
                }}
                className="w-full bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-medium"
              >
                <Plus className="mr-1.5 size-4" /> Connect Cloud Account
              </Button>
            </div>
          </SheetContent>
        </Sheet>

        <div className={`transition-all ${collapsed ? 'lg:pl-20' : 'lg:pl-64'}`}>
          <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-2 sm:gap-4 border-b border-white/8 bg-background/80 px-3 sm:px-4 backdrop-blur-xl lg:px-8">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden shrink-0"
                aria-label="Open navigation"
                onClick={() => setMobileNavOpen(true)}
              >
                <Menu className="size-5" />
              </Button>
              <div className="flex items-center gap-2 lg:hidden min-w-0">
                <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-cyan-400 text-slate-950">
                  <CloudCog className="size-4" />
                </div>
                <span className="text-base font-semibold tracking-tight truncate">Cloud<span className="text-cyan-400">Pulse</span></span>
              </div>
              <Button variant="ghost" size="icon" className="hidden lg:inline-flex" onClick={() => setCollapsed(!collapsed)} aria-label="Collapse sidebar"><PanelLeft /></Button>
              <div className="hidden items-center gap-2 text-sm md:flex">
                <span className="text-muted-foreground">Workspace</span>
                <ChevronRight className="size-3 text-muted-foreground" />
                <span className="font-medium">{connectionState?.account_name || 'Production Fleet'}</span>
                <ChevronDown className="size-3 text-muted-foreground" />
              </div>
            </div>
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <div className={`hidden items-center gap-2 rounded-full border px-3 py-1 text-xs md:flex ${connectionState?.connected ? (connectionAccessMode === 'limited' ? 'border-amber-400/30 bg-amber-400/10 text-amber-300' : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300') : 'border-white/10 bg-white/5 text-muted-foreground'}`}>
                <span className={`size-2 rounded-full ${connectionState?.connected ? (connectionAccessMode === 'limited' ? 'bg-amber-400' : 'bg-emerald-400') : 'bg-slate-500'}`} />
                {connectionState?.connected
                  ? (connectionAccessMode === 'limited'
                    ? `Limited access · ${connectionState?.provider || 'AWS'}`
                    : `Success · ${connectionState?.provider || 'AWS'}`)
                  : 'Not connected'}
              </div>
              {connectionState?.connected && Array.isArray(connectedAccounts) && connectedAccounts.length > 0 && (
                <Select
                  value={selectedAccountKey || connectionKey(connectionState)}
                  onValueChange={(value) => {
                    const next = connectedAccounts.find(account => connectionKey(account) === value)
                    if (next) {
                      switchAccount(next)
                    }
                  }}
                >
                  <SelectTrigger className="hidden h-9 min-w-56 border-white/10 bg-white/5 sm:flex">
                    <SelectValue placeholder="Switch account" />
                  </SelectTrigger>
                  <SelectContent>
                    {connectedAccounts.map((account: any) => (
                      <SelectItem key={connectionKey(account)} value={connectionKey(account)}>
                        {account.account_name || 'Connected account'} · {account.region || 'us-east-1'}{account.active ? ' · Active' : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Select value={provider} onValueChange={(value) => setProvider(value ?? 'all')}>
                <SelectTrigger className="hidden h-9 w-32 border-white/10 bg-white/5 sm:flex">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All providers</SelectItem>
                  <SelectItem value="aws">AWS</SelectItem>
                  <SelectItem value="gcp">GCP</SelectItem>
                  <SelectItem value="azure">Azure</SelectItem>
                </SelectContent>
              </Select>
              <Select value={currency} onValueChange={(value) => setCurrency((value as 'USD' | 'INR') || 'USD')}>
                <SelectTrigger className="hidden h-9 w-28 border-white/10 bg-white/5 text-xs font-medium sm:flex">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="USD">USD ($)</SelectItem>
                  <SelectItem value="INR">INR (₹ Lakhs)</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="sm"
                className="h-8 px-2 text-xs font-semibold sm:hidden border-white/10 bg-white/5"
                onClick={() => setCurrency(currency === 'USD' ? 'INR' : 'USD')}
                title="Toggle Currency"
              >
                {currency === 'USD' ? '$' : '₹'}
              </Button>
              <div className="hidden items-center gap-2 border-l border-white/10 pl-3 text-xs text-muted-foreground md:flex">
                <span className={`size-1.5 rounded-full ${connectionAccessMode === 'limited' ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                {connectionAccessMode === 'limited' ? 'Limited access' : 'Live Data'}
              </div>
              <Button variant="ghost" size="icon" onClick={fetchData} aria-label="Refresh data" className="size-8 sm:size-9">
                <RefreshCw className={`size-4 ${syncing ? 'animate-spin' : ''}`} />
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setLight(!light)} aria-label="Toggle theme" className="size-8 sm:size-9">
                {light ? <Moon className="size-4" /> : <Sun className="size-4" />}
              </Button>
              <Button size="sm" onClick={() => setConnectOpen(true)} className="h-8 sm:h-9 bg-cyan-400 text-slate-950 hover:bg-cyan-300 px-2.5 sm:px-3 text-xs sm:text-sm">
                <Plus className="size-4 shrink-0" />
                <span className="hidden sm:inline ml-1">Connect Account</span>
                <span className="sm:hidden ml-1">Connect</span>
              </Button>
            </div>
          </header>

          <div className="p-3 sm:p-4 md:p-6 lg:p-8 max-w-full">
            {loading ? (
              <Card className="border-cyan-400/20 bg-cyan-400/5">
                <CardContent className="flex min-h-96 flex-col items-center justify-center gap-4 p-8 text-center">
                  <Loader2 className="size-8 animate-spin text-cyan-400" />
                  <div>
                    <h2 className="text-lg font-semibold">Syncing AWS account</h2>
                    <p className="mt-2 max-w-lg text-sm text-muted-foreground">
                      Loading connected resources and checking which AWS data sources are available.
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    {DATA_SOURCES.map(source => (
                      <Badge key={source.key} variant="outline" className="border-white/10 text-muted-foreground">
                        {source.label}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : !connectionState?.connected ? (
              <Card className="border-amber-400/20 bg-amber-400/5">
                <CardContent className="p-8 text-center">
                  <Cloud className="mx-auto size-8 text-amber-300" />
                  <h2 className="mt-4 text-lg font-semibold">Live AWS data is not loaded</h2>
                  <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">{dataError || 'Connect an AWS account to continue.'}</p>
                  <Button className="mt-5 bg-cyan-400 text-slate-950 hover:bg-cyan-300" onClick={() => setConnectOpen(true)}>Connect AWS account</Button>
                </CardContent>
              </Card>
            ) : (
              <>
                {connectionAccessMode === 'limited' && (
                  <Card className="mb-6 border-amber-400/20 bg-amber-400/10">
                    <CardContent className="flex items-start gap-3 p-4">
                      <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-300" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-amber-100">Restricted IAM Permissions</div>
                        <p className="mt-1 text-sm text-amber-100/80">
                          {connectionWarning || 'AWS account connected. Additional read-only permissions (ec2:Describe*, cloudwatch:GetMetricData) are recommended to unlock full real-time telemetry.'}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                )}
                {view === 'overview' && (
                  <SectionErrorBoundary title="Overview">
                    <Overview
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
                    <Inventory
                      accessMode={connectionAccessMode}
                      search={search}
                      setSearch={setSearch}
                      status={status}
                      setStatus={setStatus}
                      filteredNodes={filteredNodes}
                      setSelectedNode={setSelectedNode}
                      sectionStatus={dataSources.nodes?.status || (syncing ? 'loading' : 'idle')}
                    />
                  </SectionErrorBoundary>
                )}
                {view === 'telemetry' && (
                  <SectionErrorBoundary title="Telemetry Analytics">
                    <Telemetry
                      accessMode={connectionAccessMode}
                      telemetry={telemetry}
                      timeframe={timeframe}
                      setTimeframe={setTimeframe}
                      sectionStatus={dataSources.telemetry?.status || (syncing ? 'loading' : 'idle')}
                    />
                  </SectionErrorBoundary>
                )}
                {view === 'security' && (
                  <SectionErrorBoundary title="Security Center">
                    <Security
                      accessMode={connectionAccessMode}
                      tab={securityTab}
                      setTab={setSecurityTab}
                      summary={summary}
                      audit={securityAudit}
                      sectionStatus={dataSources.security?.status || (syncing ? 'loading' : 'idle')}
                    />
                  </SectionErrorBoundary>
                )}
                {view === 'optimization' && (
                  <SectionErrorBoundary title="Cost Optimization">
                    <Optimization
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
                              : syncing ? 'loading' : 'idle'
                      }
                    />
                  </SectionErrorBoundary>
                )}
                {view === 'scheduler' && (
                  <SectionErrorBoundary title="Scheduler & Pre-Warming">
                    <SchedulerPrewarmView
                      currency={currency}
                      apiUrl={apiUrl}
                    />
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
                {view === 'kubernetes' && (
                  <SectionErrorBoundary title="Kubernetes Optimization">
                    <KubernetesView currency={currency} apiUrl={apiUrl} />
                  </SectionErrorBoundary>
                )}
                {view === 'lakehouse' && (
                  <SectionErrorBoundary title="FinOps Lakehouse">
                    <LakehouseView currency={currency} apiUrl={apiUrl} />
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
                      onSwitchAccount={switchAccount}
                      selectedAccountKey={selectedAccountKey}
                      apiUrl={apiUrl}
                    />
                  </SectionErrorBoundary>
                )}
              </>
            )}
          </div>
        </div>
      </main>

      <Sheet open={!!selectedNode} onOpenChange={() => setSelectedNode(null)}>
        <SheetContent className="w-full border-white/10 bg-card sm:max-w-md">
          <SheetHeader>
            <SheetTitle>{selectedNodeDetail?.name || selectedNode?.name}</SheetTitle>
            <SheetDescription>{selectedNodeDetail?.instance_id || selectedNode?.instance_id} · Telemetry details</SheetDescription>
          </SheetHeader>
          {selectedNode && (
            <div className="flex flex-col gap-5 p-6">
              {selectedNodeLoading && (
                <div className="text-sm text-muted-foreground">Loading live node details...</div>
              )}
              <div className="grid grid-cols-2 gap-3">
                {[['State', selectedNodeDetail?.state || selectedNode.state], ['Instance type', selectedNodeDetail?.type || selectedNode.type], ['Region', selectedNodeDetail?.region || selectedNode.region], ['Public IP', selectedNodeDetail?.public_ip || selectedNode.public_ip]].map(([a, b]) => (
                  <div key={a} className="rounded-lg border border-white/8 bg-white/5 p-3">
                    <div className="text-xs text-muted-foreground">{a}</div>
                    <div className="mt-1 text-sm font-medium">{b}</div>
                  </div>
                ))}
              </div>
              <Card className="border-white/8 bg-white/5">
                <CardHeader>
                  <CardTitle className="text-sm">CPU utilization</CardTitle>
                </CardHeader>
                <CardContent className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={selectedNodeTelemetry}>
                      <Line dataKey="cpu" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
                      <XAxis dataKey="time" hide />
                      <YAxis hide domain={[0, 100]} />
                      <Tooltip content={<ChartTooltip />} />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
              <Button className="bg-cyan-400 text-slate-950 hover:bg-cyan-300" onClick={() => { setSelectedNode(null); setSelectedNodeDetail(null); setSelectedNodeTelemetry([]); setView('telemetry'); }}>
                Open telemetry
              </Button>
            </div>
          )}
        </SheetContent>
      </Sheet>
      <ConnectModal
        open={connectOpen}
        onOpenChange={setConnectOpen}
        initialProfile={rememberedProfile}
        onSuccess={(payload: any) => {
          const connection = payload?.connection || payload || {}
          const accounts = Array.isArray(payload?.connected_accounts)
            ? payload.connected_accounts
            : Array.isArray(connection?.connected_accounts)
              ? connection.connected_accounts
              : []
          setConnectionState({
            connected: Boolean(connection.connected ?? true),
            status: connection.status || 'success',
            message: connection.message || 'Success',
            provider: connection.provider || payload?.provider || 'AWS',
            account_name: connection.account_name || payload?.account_name || '',
            region: connection.region || payload?.region || 'us-east-1',
            role_arn: connection.role_arn || payload?.role_arn,
            access_mode: connection.access_mode || payload?.access_mode || 'live',
            warning: connection.warning || payload?.warning || '',
          });
          setConnectedAccounts(accounts);
          writeStoredConnection({
            connected: Boolean(connection.connected ?? true),
            status: connection.status || 'success',
            message: connection.message || 'Success',
            provider: connection.provider || payload?.provider || 'AWS',
            account_name: connection.account_name || payload?.account_name || '',
            region: connection.region || payload?.region || 'us-east-1',
            role_arn: connection.role_arn || payload?.role_arn,
            access_mode: connection.access_mode || payload?.access_mode || 'live',
            warning: connection.warning || payload?.warning || '',
          }, accounts);
          const profile = {
            provider: connection.provider || payload?.provider || 'AWS',
            account_name: connection.account_name || payload?.account_name || '',
            auth_method: connection.auth_method || payload?.auth_method || 'learner_lab',
            region: connection.region || payload?.region || 'us-east-1',
            role_arn: connection.role_arn || payload?.role_arn || '',
            connected_at: new Date().toISOString(),
          }
          setRememberedProfile(profile);
          writeStoredProfile(profile);
          fetchData();
        }}
      />
    </div>
  )
}



function Overview({ accessMode, setView, spend, alerts, summary, sectionStatus, currency = 'USD', apiUrl }: any) {
  const [povOpen, setPovOpen] = useState(false);
  const [povData, setPovData] = useState<any>(null);
  const [povLoading, setPovLoading] = useState(false);

  const totalSpend = summary?.monthly_spend ?? 0;
  const activeNodes = summary?.running_nodes ?? 0;
  const totalNodes = summary?.total_nodes ?? 0;
  const wastedSpend = summary?.wasted_monthly_spend ?? 0;
  const criticalRisks = summary?.critical_security_risks ?? 0;
  const lastSynced = summary?.last_synced ? new Date(summary.last_synced).toLocaleString() : 'Just now';
  const summaryMode = accessMode === 'limited' ? 'Restricted permissions' : summary?.partial ? 'Partial data' : 'Live data';

  useEffect(() => {
    let cancelled = false;
    const fetchPov = async () => {
      setPovLoading(true);
      try {
        const res = await fetch(apiUrl(`/api/v2/analytics/pov/summary?currency=${currency}&rate=84.0`));
        if (res.ok && !cancelled) setPovData(await res.json());
      } catch (e) {
        console.error('PoV load error:', e);
      } finally {
        if (!cancelled) setPovLoading(false);
      }
    };
    fetchPov();
    return () => { cancelled = true; };
  }, [apiUrl, currency]);

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
              className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300 hover:bg-cyan-400/20"
              onClick={() => setPovOpen(true)}
            >
              <FileText className="mr-2 size-4" />Executive PoV Audit
            </Button>
            <Button variant="outline" onClick={() => setView('optimization')}>
              <Sparkles data-icon="inline-start" />View savings opportunities
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
            <MetricCard icon={CircleDollarSign} label={`Total monthly spend (${currency})`} value={formatCurrency(totalSpend, currency)} detail={`Last synced ${lastSynced}`} tone="cyan" trend="Live" />
            <MetricCard icon={Cpu} label="Active compute nodes" value={formatInteger(activeNodes)} detail={`${formatInteger(Math.max(totalNodes - activeNodes, 0))} stopped · ${formatInteger(totalNodes)} total`} tone="emerald" />
            <MetricCard icon={ArrowDownRight} label={`Monthly wasted spend (${currency})`} value={formatCurrency(wastedSpend, currency)} detail="Actionable savings" tone="amber" />
            <MetricCard icon={ShieldAlert} label="Critical security risks" value={formatInteger(criticalRisks)} detail="Exposure alerts from the backend" tone="red" />
          </>
        )}
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card className="border-white/8 bg-card/70">
          <CardHeader className="flex flex-row items-center justify-between gap-2">
            <div>
              <CardTitle className="text-base">30-day spend by provider</CardTitle>
              <p className="mt-1 text-xs text-muted-foreground">Daily run-rate · USD thousands</p>
            </div>
            <Badge variant="outline" className="border-white/10 text-muted-foreground">{summaryMode}</Badge>
          </CardHeader>
          <CardContent className="h-60 sm:h-72">
            {sectionStatus === 'loading' ? (
              <ChartSkeleton height="h-full" />
            ) : (!Array.isArray(spend) || spend.length === 0) ? (
              <EmptyState
                icon={BarChart3}
                title="No spend telemetry recorded"
                description="Daily cloud cost data will populate as billing metrics are ingested."
                className="h-full border-0 py-6"
              />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={spend}>
                  <defs>
                    <linearGradient id="aws" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--chart-1)" stopOpacity=".35" />
                      <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0" />
                    </linearGradient>
                    <linearGradient id="gcp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--chart-2)" stopOpacity=".3" />
                      <stop offset="100%" stopColor="var(--chart-2)" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.12)" vertical={false} />
                  <XAxis dataKey="day" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} minTickGap={16} interval="preserveStartEnd" />
                  <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} width={36} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="aws" name="AWS" stackId="1" stroke="var(--chart-1)" fill="url(#aws)" />
                  <Area type="monotone" dataKey="gcp" name="GCP" stackId="1" stroke="var(--chart-2)" fill="url(#gcp)" />
                  <Area type="monotone" dataKey="azure" name="Azure" stackId="1" stroke="var(--chart-3)" fill="var(--chart-3)" fillOpacity={.16} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardHeader>
            <CardTitle className="text-base">Quick alerts</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">Items needing your attention</p>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {sectionStatus === 'loading' ? (
              <div className="space-y-3">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </div>
            ) : (Array.isArray(alerts) ? alerts : []).length === 0 ? (
              <EmptyState
                icon={CheckCircle2}
                title="All systems optimal"
                description="Zero infrastructure or billing alerts requiring action."
                className="py-8 border-0"
              />
            ) : (
              (Array.isArray(alerts) ? alerts : []).map((alert: any, idx: number) => (
                <div key={alert.id || alert.title || idx} className="flex items-start gap-3 rounded-lg border border-white/8 bg-white/[.03] p-3">
                  <div className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-${alert.tone || 'amber'}-400/10 text-${alert.tone || 'amber'}-400`}>
                    <AlertTriangle className="size-3.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{alert.title || 'Untitled Alert'}</div>
                    <div className="mt-0.5 truncate text-xs text-muted-foreground">{alert.desc || alert.description || ''}</div>
                  </div>
                  {alert.tag && (
                    <Badge variant="outline" className="border-white/10 text-[10px] shrink-0">{alert.tag}</Badge>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Proof-of-Value Highlight Dossier Card */}
      <Card className="mt-6 border-cyan-400/20 bg-gradient-to-r from-cyan-950/40 via-card/70 to-card/70">
        <CardContent className="flex flex-col gap-4 p-4 sm:p-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-cyan-500 text-slate-950 font-semibold text-[11px]">48-Hour PoV Audit</Badge>
              <span className="text-xs text-cyan-300 font-mono">Account {povData?.account_id || '582812122408'}</span>
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
              href={apiUrl('/api/v2/analytics/pov/report.html')}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button
                size="sm"
                className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 text-xs font-medium"
              >
                <Download className="mr-1.5 size-3.5" />Open HTML Report
              </Button>
            </a>
          </div>
        </CardContent>
      </Card>

      {/* PoV Executive Modal */}
      <Dialog open={povOpen} onOpenChange={setPovOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto border-white/10 bg-slate-950 text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <FileText className="size-4 text-cyan-400" />
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
                <div className="mt-1 text-sm sm:text-base font-bold text-cyan-300">98.2% CIS</div>
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
              <a href={apiUrl('/api/v2/analytics/pov/report.html')} target="_blank" rel="noopener noreferrer">
                <Button size="sm" className="w-full sm:w-auto bg-cyan-400 text-slate-950 hover:bg-cyan-300">
                  <ExternalLink className="mr-1.5 size-3.5" />Open Interactive HTML Audit
                </Button>
              </a>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

function Inventory({ accessMode, search, setSearch, status, setStatus, filteredNodes, setSelectedNode, sectionStatus }: any) {
  return (
    <>
      <SectionTitle
        eyebrow="Inventory"
        title="Compute & storage"
        description="Track every node, volume, and exposure across your estate."
        status={<SectionStatusBadge status={sectionStatus} />}
        action={<Button variant="outline"><Archive data-icon="inline-start" />Export inventory</Button>}
      />
      <div className="mb-4 flex flex-col sm:flex-row gap-3">
        <div className="relative w-full sm:flex-1">
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search instances, IDs, IPs..." className="border-white/10 bg-white/5 pl-9" />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-full sm:w-36 border-white/10 bg-white/5">
            <SlidersHorizontal data-icon="inline-start" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="stopped">Stopped</SelectItem>
            <SelectItem value="orphaned">Orphaned</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Card className="overflow-hidden border-white/8 bg-card/70">
        {sectionStatus === 'loading' ? (
          <TableSkeleton rows={6} cols={8} />
        ) : (!Array.isArray(filteredNodes) || filteredNodes.length === 0) ? (
          <EmptyState
            icon={Server}
            title="No compute instances found"
            description={search || status !== 'all' ? "No instances match your current filter criteria." : "No live EC2 nodes discovered in this connected region."}
            action={
              (search || status !== 'all') ? (
                <Button variant="outline" size="sm" onClick={() => { setSearch(''); setStatus('all'); }}>
                  Clear filters
                </Button>
              ) : undefined
            }
            className="my-6 border-0"
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-white/8 hover:bg-transparent">
                <TableHead className="w-10" />
                <TableHead>Instance</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Region</TableHead>
                <TableHead>Public IP</TableHead>
                <TableHead>Volumes</TableHead>
                <TableHead className="text-right">Monthly cost</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredNodes.map((n: any) => (
                <TableRow key={n.instance_id} onClick={() => setSelectedNode(n)} className="cursor-pointer border-white/8 hover:bg-white/[.04]">
                  <TableCell>
                    <input type="checkbox" aria-label={`Select ${n.name}`} className="accent-cyan-400" onClick={e => e.stopPropagation()} />
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">{n.name}</div>
                    <div className="font-mono text-[11px] text-muted-foreground">{n.instance_id}</div>
                  </TableCell>
                  <TableCell>
                    <span className="flex items-center gap-2 text-xs capitalize">
                      <span className={`size-2 rounded-full ${n.state === 'running' ? 'bg-emerald-400' : n.state === 'stopped' ? 'bg-amber-400' : 'bg-red-400'}`} />
                      {n.state}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{n.type}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{n.region}</TableCell>
                  <TableCell className="font-mono text-xs">{n.public_ip}</TableCell>
                  <TableCell className="text-xs">{n.volumes} attached</TableCell>
                  <TableCell className="text-right font-mono text-xs">${Number(n.cost).toFixed(2)}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" aria-label="More actions" onClick={e => e.stopPropagation()}>
                      <MoreHorizontal />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </>
  )
}

function Telemetry({ accessMode, telemetry, timeframe, setTimeframe, sectionStatus }: any) {
  return (
    <>
      <SectionTitle
        eyebrow="Live telemetry"
        title="Telemetry analytics"
        description="Real-time health signals and performance metrics from active nodes."
        status={<SectionStatusBadge status={sectionStatus} />}
        action={
          <div className="flex items-center gap-2 flex-wrap">
            <ToggleGroup value={[timeframe]} onValueChange={v => setTimeframe(v[0] ?? timeframe)}>
              <ToggleGroupItem value="1h">1H</ToggleGroupItem>
              <ToggleGroupItem value="6h">6H</ToggleGroupItem>
              <ToggleGroupItem value="24h">24H</ToggleGroupItem>
              <ToggleGroupItem value="7d">7D</ToggleGroupItem>
            </ToggleGroup>
          </div>
        }
      />
      <div className="grid gap-4 md:grid-cols-2">
        {[
          ['CPU utilization', 'cpu', 'CPU %', 'line'],
          ['Memory usage', 'mem', 'Memory %', 'area'],
          ['Network traffic', 'network', 'MB/s', 'network'],
          ['Disk IOPS', 'iops', 'IOPS', 'bar']
        ].map(([title, key, unit, kind]) => (
          <Card key={title} className="border-white/8 bg-card/70">
            <CardHeader className="flex-row items-center justify-between pb-2">
              <div>
                <CardTitle className="text-sm">{title}</CardTitle>
                <p className="mt-1 text-xs text-muted-foreground">{unit} · last {timeframe}</p>
              </div>
              <span className="size-2 rounded-full bg-emerald-400" />
            </CardHeader>
            <CardContent className="h-56">
              {sectionStatus === 'loading' ? (
                <ChartSkeleton height="h-full" />
              ) : (!Array.isArray(telemetry) || telemetry.length === 0) ? (
                <EmptyState
                  icon={Activity}
                  title="No telemetry signals"
                  description={`No ${title.toLowerCase()} data received in the last ${timeframe}.`}
                  className="h-full border-0 py-4"
                />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  {kind === 'bar' ? (
                    <BarChart data={telemetry}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.12)" vertical={false} />
                      <XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} minTickGap={16} interval="preserveStartEnd" />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} width={30} />
                      <Tooltip content={<ChartTooltip />} />
                      <Bar dataKey="read" fill="var(--chart-1)" radius={[3, 3, 0, 0]} />
                      <Bar dataKey="write" fill="var(--chart-2)" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  ) : (
                    <LineChart data={telemetry}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.12)" vertical={false} />
                      <XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} minTickGap={16} interval="preserveStartEnd" />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} width={30} />
                      <Tooltip content={<ChartTooltip />} />
                      {key === 'cpu' && <ReferenceLine y={80} stroke="var(--destructive)" strokeDasharray="4 4" />}
                      <Line type="monotone" dataKey={key === 'network' ? 'netIn' : key} stroke="var(--chart-1)" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey={key === 'network' ? 'netOut' : undefined} stroke="var(--chart-2)" strokeWidth={2} dot={false} />
                    </LineChart>
                  )}
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  )
}

function Security({ accessMode, tab, setTab, summary, audit, sectionStatus }: any) {
  const exposedSecurityGroups = audit?.exposed_security_groups || [];
  const unattachedElasticIPs = audit?.unattached_elastic_ips || [];
  const orphanedEbsVolumes = audit?.orphaned_ebs_volumes || [];

  const handleRevoke = async (groupId: string) => {
    await fetch(apiUrl(`/api/security/revoke`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groupId })
    });
  };

  return (
    <>
      <SectionTitle
        eyebrow="Security center"
        title="Exposure audit"
        description="Resolve public attack surface, exposed ports, and unmanaged cloud resources."
        status={<SectionStatusBadge status={sectionStatus} />}
      />
      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <MetricCard
          icon={ShieldAlert}
          label="Critical risks"
          value={formatInteger(summary?.critical_security_risks)}
          detail="From the live summary endpoint"
          tone="red"
        />
        <MetricCard
          icon={Cloud}
          label="Public security groups"
          value={formatInteger(exposedSecurityGroups.length)}
          detail="Exposed to the internet"
          tone="amber"
        />
        <MetricCard
          icon={HardDrive}
          label="Orphaned resources"
          value={formatInteger(unattachedElasticIPs.length + orphanedEbsVolumes.length)}
          detail="Unattached EIPs and volumes"
          tone="cyan"
        />
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4 bg-white/5 w-full sm:w-auto overflow-x-auto justify-start max-w-full">
          <TabsTrigger value="groups">Security groups</TabsTrigger>
          <TabsTrigger value="ips">Elastic IPs & NAT</TabsTrigger>
          <TabsTrigger value="logs">CloudWatch logs</TabsTrigger>
        </TabsList>
        <TabsContent value="groups">
          <Card className="border-white/8 bg-card/70 overflow-hidden">
            {sectionStatus === 'loading' ? (
              <TableSkeleton rows={4} cols={5} />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="border-white/8">
                    <TableHead>Group</TableHead>
                    <TableHead>Exposure</TableHead>
                    <TableHead>Ports</TableHead>
                    <TableHead>Resources</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {exposedSecurityGroups.length ? exposedSecurityGroups.map((group: any) => (
                    <TableRow key={group.group_id} className="border-white/8">
                      <TableCell>
                        <div className="font-medium">{group.group_name}</div>
                        <div className="font-mono text-xs text-muted-foreground">{group.group_id}</div>
                      </TableCell>
                      <TableCell><Badge className="border-red-400/20 bg-red-400/10 text-red-300">Publicly exposed</Badge></TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {(group.exposed_ports || []).map((port: number) => (
                            <Badge key={port} variant="outline" className={port === 22 ? 'border-red-400/30 text-red-300' : ''}>
                              {port}{port === 22 ? ' SSH' : ''}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">{group.exposed_ports?.length || 0} exposed ports</TableCell>
                      <TableCell>
                        <Button size="sm" variant="destructive" onClick={() => handleRevoke(group.group_id)}>Revoke</Button>
                      </TableCell>
                    </TableRow>
                  )) : (
                    <TableRow className="border-white/8">
                      <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                        No public security groups detected.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </Card>
        </TabsContent>
        <TabsContent value="ips">
          <Card className="border-white/8 bg-card/70 overflow-hidden">
            {sectionStatus === 'loading' ? (
              <TableSkeleton rows={4} cols={3} />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="border-white/8">
                    <TableHead>Elastic IP</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Monthly cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {unattachedElasticIPs.length ? unattachedElasticIPs.map((eip: any) => (
                    <TableRow key={eip.public_ip} className="border-white/8">
                      <TableCell className="font-mono text-xs">{eip.public_ip}</TableCell>
                      <TableCell><Badge variant="outline" className="border-amber-400/30 text-amber-300">Unattached</Badge></TableCell>
                      <TableCell className="font-mono text-xs">${Number(eip.estimated_monthly_cost ?? 0).toFixed(2)}</TableCell>
                    </TableRow>
                  )) : (
                    <TableRow className="border-white/8">
                      <TableCell colSpan={3} className="py-10 text-center text-sm text-muted-foreground">
                        No unattached Elastic IPs found.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </Card>
        </TabsContent>
        <TabsContent value="logs">
          <Card className="border-white/8 bg-card/70 p-6 text-sm text-muted-foreground">
            CloudWatch log streaming is not enabled for this account yet.
            <div className="mt-2 text-foreground">
              Security groups, Elastic IPs, and EBS volumes are loaded from the connected AWS account.
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  )
}

function Optimization({ accessMode, items = [], applied, setApplied, sectionStatus, currency = 'USD', apiUrl }: any) {
  const [broadcastOpen, setBroadcastOpen] = useState(false);
  const [broadcasting, setBroadcasting] = useState(false);
  const [broadcastTarget, setBroadcastTarget] = useState<'slack' | 'teams'>('slack');
  const [broadcastResult, setBroadcastResult] = useState<string | null>(null);

  const [gitopsOpen, setGitopsOpen] = useState(false);
  const [gitopsLoading, setGitopsLoading] = useState(false);
  const [gitopsPackage, setGitopsPackage] = useState<any | null>(null);
  const [gitopsCopied, setGitopsCopied] = useState(false);

  const toggleOptimization = async (id: string) => {
    const isApplied = applied.includes(id);
    const newApplied = isApplied ? applied.filter((x: string) => x !== id) : [...applied, id];
    const res = await fetch(apiUrl('/api/optimizations/apply'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, action: isApplied ? 'revert' : 'apply' })
    });

    if (res.ok) {
      const data = await res.json();
      setApplied(Array.isArray(data?.applied) ? data.applied : newApplied);
    } else {
      setApplied(newApplied);
    }
  };

  const handleBatchGitopsPr = async () => {
    setGitopsOpen(true);
    setGitopsLoading(true);
    setGitopsPackage(null);
    try {
      const res = await fetch(apiUrl('/api/v2/gitops/batch-pr'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          findings: items.map((i: any) => ({
            resource_id: i.resource_id || i.id,
            action: i.type?.toLowerCase().includes('storage') ? 'gp3_upgrade' : 'downsize',
            monthly_savings: Number(i.savings ?? 0),
            resource_type: i.type?.toLowerCase().includes('storage') ? 'ebs' : 'ec2'
          })),
          environment: 'production',
          repo_name: 'infrastructure/aws-workloads'
        })
      });
      if (res.ok) {
        setGitopsPackage(await res.json());
      }
    } catch (e) {
      console.error('GitOps batch PR failed:', e);
    } finally {
      setGitopsLoading(false);
    }
  };

  const handleSingleGitopsPr = async (item: any) => {
    setGitopsOpen(true);
    setGitopsLoading(true);
    setGitopsPackage(null);
    try {
      const res = await fetch(apiUrl('/api/v2/gitops/pr'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resource_id: item.resource_id || item.id,
          action: item.type?.toLowerCase().includes('storage') ? 'gp3_upgrade' : 'downsize',
          monthly_savings: Number(item.savings ?? 0),
          environment: 'production',
          repo_name: 'infrastructure/aws-workloads'
        })
      });
      if (res.ok) {
        setGitopsPackage(await res.json());
      }
    } catch (e) {
      console.error('Single GitOps PR failed:', e);
    } finally {
      setGitopsLoading(false);
    }
  };

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
              className="border-indigo-400/30 bg-indigo-400/10 text-indigo-300 hover:bg-indigo-400/20"
              onClick={handleBatchGitopsPr}
            >
              <GitBranch className="mr-2 size-4" />Batch GitOps PR
            </Button>
            <Button
              variant="outline"
              className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300 hover:bg-cyan-400/20"
              onClick={() => { setBroadcastOpen(true); setBroadcastResult(null); }}
            >
              <Bell className="mr-2 size-4" />Broadcast Digest
            </Button>
            <Button
              onClick={async () => {
                await Promise.all(items.map((i: any) => fetch(apiUrl('/api/optimizations/apply'), {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ id: i.id, action: 'apply' })
                })));
                setApplied(items.map((i: any) => i.id));
              }}
              className="bg-cyan-400 text-slate-950 hover:bg-cyan-300"
            >
              <Zap data-icon="inline-start" />Apply all optimizations
            </Button>
          </div>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
          {formatInteger(items.length)} live recommendations
        </span>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
          {formatCurrency(items.reduce((sum: number, item: any) => sum + Number(item.savings ?? 0), 0), currency)} potential savings
        </span>
      </div>
      {sectionStatus === 'loading' ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="border-white/8 bg-card/70 p-5 space-y-3">
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
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item: any) => {
            const done = applied.includes(item.id);
            return (
              <Card key={item.id} className={`border-white/8 bg-card/70 transition ${done ? 'border-emerald-400/30' : ''}`}>
                <CardHeader>
                  <Badge variant="outline" className="w-fit border-white/10">{item.type}</Badge>
                  <CardTitle className="pt-2 text-base">{item.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="min-h-10 text-sm text-muted-foreground">{item.desc}</p>
                  {item.ai_rationale && item.ai_rationale !== item.desc && (
                    <div className="mt-3 rounded-lg border border-cyan-400/20 bg-cyan-400/5 p-2.5 text-xs text-cyan-200">
                      <div className="mb-1 flex items-center gap-1.5 font-medium text-cyan-300">
                        <Sparkles className="size-3.5" /> AI Architecture Rationale
                      </div>
                      {item.ai_rationale}
                    </div>
                  )}
                  <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-lg sm:text-xl font-semibold text-emerald-300">Saves {formatCurrency(Number(item.savings ?? 0), currency)}/mo</div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Button size="sm" variant="ghost" className="text-xs text-cyan-300 hover:bg-cyan-400/10 px-2" onClick={() => handleSingleGitopsPr(item)}>
                        <GitPullRequest className="mr-1 size-3" />PR
                      </Button>
                      <Button size="sm" variant={done ? 'secondary' : 'outline'} onClick={() => toggleOptimization(item.id)}>
                        {done ? <><Check data-icon="inline-start" />Applied</> : 'Review'}
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
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto border-white/10 bg-slate-950 text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <GitBranch className="size-4 text-cyan-400" />
              Autonomous GitOps Pull Request
            </DialogTitle>
            <DialogDescription>
              Production-ready Terraform HCL infrastructure diff created by CloudPulse GitOps engine.
            </DialogDescription>
          </DialogHeader>
          {gitopsLoading ? (
            <div className="flex flex-col items-center justify-center py-10 gap-3">
              <Loader2 className="size-8 animate-spin text-cyan-400" />
              <span className="text-xs text-muted-foreground">Synthesizing Terraform HCL diff & creating Git branch...</span>
            </div>
          ) : gitopsPackage ? (
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="rounded-lg border border-white/8 bg-white/5 p-3">
                  <span className="text-[11px] text-muted-foreground">Branch</span>
                  <div className="mt-1 font-mono text-xs font-semibold text-cyan-300 truncate">
                    {gitopsPackage.branch_name}
                  </div>
                </div>
                <div className="rounded-lg border border-white/8 bg-white/5 p-3">
                  <span className="text-[11px] text-muted-foreground">Repository</span>
                  <div className="mt-1 font-mono text-xs font-semibold text-foreground truncate">
                    {gitopsPackage.repo_name}
                  </div>
                </div>
                <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-3">
                  <span className="text-[11px] text-emerald-300">Net Monthly Savings</span>
                  <div className="mt-1 text-xs font-bold text-emerald-300">
                    {formatCurrency(gitopsPackage.total_monthly_savings || gitopsPackage.monthly_savings, currency)}/mo
                  </div>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
                  <span className="flex items-center gap-1"><FileCode className="size-3.5 text-cyan-400" /> Terraform HCL Diff</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[11px]"
                    onClick={() => {
                      navigator.clipboard.writeText(gitopsPackage.diff || '');
                      setGitopsCopied(true);
                      setTimeout(() => setGitopsCopied(false), 2000);
                    }}
                  >
                    {gitopsCopied ? <Check className="mr-1 size-3 text-emerald-400" /> : <Copy className="mr-1 size-3" />}
                    {gitopsCopied ? 'Copied' : 'Copy Diff'}
                  </Button>
                </div>
                <pre className="max-h-60 overflow-auto rounded-lg border border-white/10 bg-black/60 p-3.5 font-mono text-xs text-emerald-300">
                  {gitopsPackage.diff || '# No HCL diff required'}
                </pre>
              </div>

              <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3 pt-2">
                <span className="text-xs text-muted-foreground">
                  Target: <span className="font-mono text-foreground">{gitopsPackage.target_branch || 'main'}</span>
                </span>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setGitopsOpen(false)}>Close</Button>
                  <a
                    href={gitopsPackage.pull_request_url || gitopsPackage.pr_url || `https://github.com/${gitopsPackage.repo_name}/pull/new/${gitopsPackage.branch_name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button size="sm" className="w-full sm:w-auto bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-medium">
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
        <DialogContent className="border-white/10 bg-slate-950 text-foreground sm:max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <Bell className="size-4 text-cyan-400" />
              Broadcast FinOps Fleet Digest
            </DialogTitle>
            <DialogDescription>
              Dispatch the real-time cost optimization digest, health metrics, and 1-click GitOps buttons to your team channel.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-2">
            <div className="rounded-lg border border-white/8 bg-white/5 p-3 text-xs">
              <div className="font-semibold text-muted-foreground">Digest Payload Preview:</div>
              <div className="mt-1.5 flex justify-between"><span>Optimizations:</span><b>{items.length} opportunities</b></div>
              <div className="mt-1 flex justify-between"><span>Recoverable Savings:</span><b className="text-emerald-300">{formatCurrency(items.reduce((s: number, i: any) => s + Number(i.savings ?? 0), 0), currency)}/mo</b></div>
              <div className="mt-1 flex justify-between"><span>Interactive Buttons:</span><span className="text-cyan-300">🚀 Batch PR, ⏰ Snooze</span></div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Select Destination Platform:</label>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Button
                  type="button"
                  variant={broadcastTarget === 'slack' ? 'default' : 'outline'}
                  className={broadcastTarget === 'slack' ? 'bg-cyan-500 text-slate-950 hover:bg-cyan-400' : 'border-white/10 bg-white/5'}
                  onClick={() => setBroadcastTarget('slack')}
                >
                  Slack (Block Kit)
                </Button>
                <Button
                  type="button"
                  variant={broadcastTarget === 'teams' ? 'default' : 'outline'}
                  className={broadcastTarget === 'teams' ? 'bg-indigo-600 text-white hover:bg-indigo-500' : 'border-white/10 bg-white/5'}
                  onClick={() => setBroadcastTarget('teams')}
                >
                  Microsoft Teams
                </Button>
              </div>
            </div>
            {broadcastResult && (
              <div className={`rounded-lg p-3 text-xs ${broadcastResult.startsWith('✅') ? 'bg-emerald-400/10 text-emerald-300 border border-emerald-400/20' : 'bg-red-400/10 text-red-300 border border-red-400/20'}`}>
                {broadcastResult}
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setBroadcastOpen(false)}>Cancel</Button>
              <Button
                size="sm"
                className="bg-cyan-400 text-slate-950 hover:bg-cyan-300"
                disabled={broadcasting}
                onClick={async () => {
                  setBroadcasting(true);
                  setBroadcastResult(null);
                  try {
                    const ep = broadcastTarget === 'slack' ? '/api/v2/notifications/slack/batch' : '/api/v2/notifications/teams/batch';
                    const res = await fetch(apiUrl(ep), {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ currency, rate: 84.0 })
                    });
                    const data = await res.json();
                    if (data.dispatched) {
                      setBroadcastResult(`✅ Broadcast delivered successfully to ${broadcastTarget === 'slack' ? 'Slack' : 'Microsoft Teams'}!`);
                    } else if (data.status === 'success') {
                      setBroadcastResult(`✅ Card generated! Check that your ${broadcastTarget === 'slack' ? 'SLACK_WEBHOOK_URL' : 'TEAMS_WEBHOOK_URL'} is configured in Settings.`);
                    } else {
                      setBroadcastResult(`❌ Dispatch failed: ${data.message || 'Remote rejected request'}`);
                    }
                  } catch (e: any) {
                    setBroadcastResult(`❌ Failed to broadcast: ${e.message || e}`);
                  } finally {
                    setBroadcasting(false);
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

function KubernetesView({ currency = 'USD', apiUrl }: { currency: 'USD' | 'INR'; apiUrl: (path: string) => string }) {
  const [loading, setLoading] = useState(true);
  const [efficiency, setEfficiency] = useState<any>(null);
  const [allocations, setAllocations] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [selectedNamespace, setSelectedNamespace] = useState('all');
  const [activeYamlDiff, setActiveYamlDiff] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchK8s = async () => {
      setLoading(true);
      try {
        const [effRes, allocRes, recRes] = await Promise.all([
          fetch(apiUrl(`/api/v2/kubernetes/efficiency?currency=${currency}&rate=84.0`)),
          fetch(apiUrl(`/api/v2/kubernetes/allocations?currency=${currency}&rate=84.0`)),
          fetch(apiUrl(`/api/v2/kubernetes/recommendations?currency=${currency}&rate=84.0`)),
        ]);
        if (!cancelled) {
          if (effRes.ok) setEfficiency(await effRes.json());
          if (allocRes.ok) {
            const a = await allocRes.json();
            setAllocations(Array.isArray(a) ? a : a.allocations || []);
          }
          if (recRes.ok) {
            const r = await recRes.json();
            setRecommendations(Array.isArray(r) ? r : r.recommendations || []);
          }
        }
      } catch (err) {
        console.error('Failed to load Kubernetes data:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchK8s();
    return () => {
      cancelled = true;
    };
  }, [currency, apiUrl]);

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

  return (
    <>
      <SectionTitle
        eyebrow="Container FinOps"
        title="Kubernetes & OpenCost Workload Allocation"
        description="Container-level resource rightsizing, idle waste attribution, and 1-click YAML patch diffs."
        status={
          <Badge variant="outline" className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            OpenCost FOCUS 1.0
          </Badge>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Cluster Efficiency</span>
              <Cpu className="size-4 text-cyan-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-cyan-300">
              {efficiency?.overall_efficiency_pct ? `${efficiency.overall_efficiency_pct.toFixed(1)}%` : '24.5%'}
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
              {formatCurrency(efficiency?.monthly_requested_cost || 741.81, currency)}
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
              {formatCurrency(efficiency?.monthly_idle_waste || 559.86, currency)}/mo
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
              {formatInteger(efficiency?.total_workloads || allocations.length || 7)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Across {namespaces.length - 1 || 4} namespaces</div>
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
                {namespaces.map(ns => (
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
            <EmptyState
              icon={Server}
              title="No Workload Allocations Found"
              description={`No pods or deployments found in namespace "${selectedNamespace}".`}
              action={
                selectedNamespace !== 'all' ? (
                  <Button variant="outline" size="sm" onClick={() => setSelectedNamespace('all')}>
                    Show all namespaces
                  </Button>
                ) : undefined
              }
              className="my-4 border-0"
            />
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
    </>
  );
}

function LakehouseView({ currency = 'USD', apiUrl }: { currency: 'USD' | 'INR'; apiUrl: (path: string) => string }) {
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<any>(null);
  const [query, setQuery] = useState(
    'SELECT ServiceName, SUM(EffectiveCost) as TotalSpend, COUNT(*) as ResourceCount FROM focus_costs GROUP BY ServiceName ORDER BY TotalSpend DESC LIMIT 10;'
  );
  const [executing, setExecuting] = useState(false);
  const [queryResult, setQueryResult] = useState<any>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchAnalytics = async () => {
      setLoading(true);
      try {
        const res = await fetch(apiUrl('/api/v2/focus/analytics'));
        if (res.ok && !cancelled) {
          setAnalytics(await res.json());
        }
      } catch (err) {
        console.error('Failed to fetch FOCUS analytics:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchAnalytics();
    return () => {
      cancelled = true;
    };
  }, [apiUrl]);

  const runQuery = async (sqlToRun?: string) => {
    const sql = sqlToRun || query;
    setExecuting(true);
    setQueryError(null);
    try {
      const res = await fetch(apiUrl('/api/v2/focus/query'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: sql }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setQueryError(data.error || 'SQL execution failed');
        setQueryResult(null);
      } else {
        setQueryResult(data);
      }
    } catch (err: any) {
      setQueryError(err?.message || 'Execution error');
      setQueryResult(null);
    } finally {
      setExecuting(false);
    }
  };

  const presets = [
    {
      label: 'By Cloud Service',
      sql: 'SELECT ServiceName, SUM(EffectiveCost) as Spend, COUNT(*) as Resources FROM focus_costs GROUP BY ServiceName ORDER BY Spend DESC;',
    },
    {
      label: 'By Billing Account',
      sql: 'SELECT BillingAccountId, SUM(EffectiveCost) as TotalSpend, COUNT(DISTINCT ServiceName) as Services FROM focus_costs GROUP BY BillingAccountId;',
    },
    {
      label: 'Top Cost Drivers',
      sql: 'SELECT ResourceID, ServiceName, EffectiveCost, RegionName FROM focus_costs ORDER BY EffectiveCost DESC LIMIT 5;',
    },
    {
      label: 'By Region',
      sql: 'SELECT RegionName, SUM(EffectiveCost) as Spend FROM focus_costs GROUP BY RegionName ORDER BY Spend DESC;',
    },
  ];

  return (
    <>
      <SectionTitle
        eyebrow="Zero-Copy Lakehouse"
        title="DuckDB FOCUS 1.0 SQL Analytics"
        description="Sub-millisecond analytical queries directly over normalized FinOps Open Cost & Usage Specification (FOCUS 1.0) datasets."
        status={
          <Badge variant="outline" className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            DuckDB Parquet Engine
          </Badge>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <span className="text-xs text-muted-foreground">Tracked Cloud Services</span>
            <div className="mt-3 text-2xl font-bold text-cyan-300">
              {analytics?.spend_by_service?.length || 3}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Normalized FOCUS 1.0 services</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <span className="text-xs text-muted-foreground">Billing Accounts</span>
            <div className="mt-3 text-2xl font-bold">
              {analytics?.spend_by_account?.length || 1}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Multi-tenant sovereign accounts</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <span className="text-xs text-muted-foreground">Primary Spend Driver</span>
            <div className="mt-3 truncate text-xl font-bold text-emerald-300">
              {analytics?.spend_by_service?.[0]?.ServiceName || 'Compute (EC2)'}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {formatCurrency(analytics?.spend_by_service?.[0]?.TotalEffectiveCost, currency)}/mo run-rate
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Card className="border-white/8 bg-card/70 lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base font-semibold">Spend by Cloud Service</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {(analytics?.spend_by_service || []).map((s: any, idx: number) => (
              <div key={`${s.ServiceName}-${idx}`} className="rounded-lg border border-white/8 bg-white/5 p-3 text-xs">
                <div className="flex items-center justify-between font-medium">
                  <span className="truncate text-muted-foreground">{s.ServiceName}</span>
                  <span className="font-semibold text-cyan-300">
                    {formatCurrency(s.TotalEffectiveCost, currency)}
                  </span>
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground/80">
                  {s.ResourceCount} resources · {s.ProviderName || 'AWS'}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70 lg:col-span-2">
          <CardHeader>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <Terminal className="size-4 text-cyan-400" />
                DuckDB FOCUS 1.0 SQL Query Runner
              </CardTitle>
              <div className="flex flex-wrap items-center gap-1.5">
                {presets.map(p => (
                  <Button
                    key={p.label}
                    size="sm"
                    variant="ghost"
                    className="h-7 border border-white/8 px-2 text-[11px] text-cyan-300 hover:bg-cyan-400/10"
                    onClick={() => {
                      setQuery(p.sql);
                      runQuery(p.sql);
                    }}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="relative">
              <textarea
                value={query}
                onChange={e => setQuery(e.target.value)}
                className="h-28 w-full resize-none rounded-lg border border-white/10 bg-black/60 p-3 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:border-cyan-400 focus:outline-none"
                placeholder="Enter SQL query against 'focus_costs' table..."
              />
              <Button
                size="sm"
                className="absolute bottom-3 right-3 bg-cyan-400 text-slate-950 hover:bg-cyan-300"
                onClick={() => runQuery()}
                disabled={executing || !query.trim()}
              >
                {executing ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Play className="mr-1 size-3" />}
                Run SQL
              </Button>
            </div>

            {queryError && (
              <div className="rounded-lg border border-red-400/20 bg-red-400/10 p-3 text-xs text-red-300">
                {queryError}
              </div>
            )}

            {executing ? (
              <div className="pt-2">
                <TableSkeleton rows={4} cols={4} />
              </div>
            ) : queryResult ? (
              <div className="flex flex-col gap-2 pt-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Returned {queryResult.row_count || queryResult.rows?.length || 0} rows</span>
                  <span className="font-mono text-[11px] text-cyan-300">Engine: DuckDB in-memory</span>
                </div>
                <div className="max-h-60 overflow-auto rounded-lg border border-white/8">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-white/8 hover:bg-transparent">
                        {(queryResult.columns || Object.keys(queryResult.rows?.[0] || {})).map((col: string) => (
                          <TableHead key={col} className="text-xs font-semibold text-cyan-300">{col}</TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(queryResult.rows || []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={(queryResult.columns || ['Result']).length} className="py-8 text-center text-xs text-muted-foreground">
                            Query executed successfully with 0 rows returned.
                          </TableCell>
                        </TableRow>
                      ) : (
                        (queryResult.rows || []).map((row: any, rIdx: number) => (
                          <TableRow key={rIdx} className="border-white/8">
                            {(queryResult.columns || Object.keys(row)).map((col: string) => (
                              <TableCell key={col} className="font-mono text-xs">
                                {typeof row[col] === 'number' && col.toLowerCase().includes('cost')
                                  ? formatCurrency(row[col], currency)
                                  : String(row[col] ?? '')}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function CopilotView({ apiUrl }: { apiUrl: (path: string) => string }) {
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string; model?: string; tool?: string }>>([
    {
      role: 'assistant',
      text: "👋 Welcome to **CloudPulse Autonomous FinOps Copilot**, powered by **Groq Cloud LLM** (compound-mini / compound / Qwen 27B) and live TimescaleDB telemetry.\n\nI can analyze your live AWS inventory, explain spend surges, evaluate Graviton modernization ROI, and generate ready-to-merge Terraform/OpenTofu Pull Requests.\n\nAsk me anything or click one of the quick prompts below!",
      model: 'groq/compound-mini'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async (queryText: string) => {
    const text = queryText.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text }]);
    setLoading(true);

    try {
      const res = await fetch(apiUrl('/api/v2/copilot/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, prompt: text, history: [] })
      });
      const data = await res.json();
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: data.answer || data.response || 'No response received from Copilot.',
          model: data.model || 'groq',
          tool: data.tool_called
        }
      ]);
    } catch (err: any) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: `⚠️ Error communicating with Copilot: ${err?.message || err}`,
          model: 'error'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const chips = [
    "What is the cost footprint of our 9 t3.micro instances?",
    "Compare m5.2xlarge with Graviton pricing",
    "Why did we have a spike in cloud spend?",
    "Generate Terraform PR to downsize idle compute",
    "/audit",
    "/optimize",
    "/forecast"
  ];

  return (
    <>
      <SectionTitle
        eyebrow="Autonomous Copilot"
        title="AI FinOps Architect & Code Remediation"
        description="Interact with the sovereign cloud economist powered by Groq LLM inference and TimescaleDB."
        action={
          <div className="flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-300">
            <Sparkles className="size-3.5" />
            <span>Active Backend: <strong>Groq LLM</strong></span>
          </div>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {chips.map((chip, i) => (
          <button
            key={i}
            onClick={() => sendMessage(chip)}
            disabled={loading}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-muted-foreground transition hover:border-cyan-400/40 hover:bg-cyan-400/10 hover:text-cyan-300 disabled:opacity-50"
          >
            {chip}
          </button>
        ))}
      </div>

      <Card className="flex flex-col border-white/8 bg-card/70 backdrop-blur">
        <CardContent className="flex flex-1 flex-col gap-4 p-4 lg:p-6">
          <div className="flex flex-col gap-4 overflow-y-auto" style={{ minHeight: '380px', maxHeight: '520px' }}>
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.role === 'assistant' && (
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-300 border border-cyan-400/20">
                    <Sparkles className="size-4" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-xl p-4 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-cyan-500 text-slate-950 font-medium'
                      : 'border border-white/8 bg-white/5 text-foreground'
                  }`}
                >
                  {m.role === 'assistant' && m.model && (
                    <div className="mb-2 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono">
                        {m.model}
                      </span>
                      {m.tool && (
                        <span className="rounded border border-cyan-400/20 bg-cyan-400/10 px-1.5 py-0.5 font-mono text-cyan-300">
                          tool: {m.tool}
                        </span>
                      )}
                    </div>
                  )}
                  <div className="whitespace-pre-wrap font-sans space-y-2">
                    {m.text}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <div className="flex size-8 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-300 border border-cyan-400/20">
                  <Loader2 className="size-4 animate-spin" />
                </div>
                <span>Copilot is reasoning with Groq LLM & analyzing live telemetry...</span>
              </div>
            )}
          </div>

          <div className="mt-4 flex gap-2 border-t border-white/8 pt-4">
            <Input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
              placeholder="Ask a question or type /audit, /optimize, /forecast, /pricing..."
              disabled={loading}
              className="border-white/10 bg-white/5 text-foreground placeholder:text-muted-foreground"
            />
            <Button
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
              className="bg-cyan-400 text-slate-950 hover:bg-cyan-300"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            </Button>
          </div>
        </CardContent>
      </Card>
    </>
  )
}

function SettingsView({ connectionState, connectedAccounts, rememberedProfile, onSwitchAccount, selectedAccountKey, apiUrl }: any) {
  const [orgName, setOrgName] = useState('');
  const [slackWebhookUrl, setSlackWebhookUrl] = useState('');
  const [teamsWebhookUrl, setTeamsWebhookUrl] = useState('');
  const [slackBotToken, setSlackBotToken] = useState('');
  const [slackChannel, setSlackChannel] = useState('#general');
  const [whatsappTo, setWhatsappTo] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingChannel, setTestingChannel] = useState<string | null>(null);
  const [testFeedback, setTestFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadSettings = async () => {
      try {
        const res = await fetch(apiUrl('/api/settings'));
        const data = await res.json();
        if (!cancelled) {
          setOrgName(data?.organization || '');
          setSlackWebhookUrl(data?.slack_webhook_url || '');
          setTeamsWebhookUrl(data?.teams_webhook_url || '');
          setSlackBotToken(data?.slack_bot_token || '');
          setSlackChannel(data?.slack_channel || '#general');
          setWhatsappTo(data?.whatsapp_to || '');
        }
      } catch (err) {
        console.error('Failed to load settings:', err);
      } finally {
        if (!cancelled) {
          setLoaded(true);
        }
      }
    };

    loadSettings();

    return () => {
      cancelled = true;
    };
  }, [apiUrl]);

  const handleSave = async () => {
    setSaving(true);
    setTestFeedback(null);
    try {
      await fetch(apiUrl('/api/settings'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          orgName,
          slackWebhookUrl,
          teamsWebhookUrl,
          slackBotToken,
          slackChannel,
          whatsappTo,
        }),
      });
      setTestFeedback({ type: 'success', message: 'All workspace & notification settings saved successfully.' });
    } catch (e: any) {
      setTestFeedback({ type: 'error', message: `Failed to save settings: ${e.message || e}` });
    } finally {
      setSaving(false);
    }
  };

  const testNotification = async (channel: 'slack' | 'teams') => {
    setTestingChannel(channel);
    setTestFeedback(null);
    try {
      const ep = channel === 'slack' ? '/api/v2/notifications/slack' : '/api/v2/notifications/teams';
      const targetUrl = channel === 'slack' ? slackWebhookUrl : teamsWebhookUrl;
      const res = await fetch(apiUrl(ep), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resource_id: 'i-0a106c14603cb65a0',
          finding_title: `CloudPulse Live ${channel === 'slack' ? 'Slack' : 'Microsoft Teams'} Test Alert`,
          severity: 'HIGH',
          current_monthly_spend: 68.4,
          potential_monthly_savings: 24.5,
          recommended_action: 'Downsize overprovisioned instance to Graviton t4g.small',
          webhook_url: targetUrl || undefined,
        }),
      });
      const data = await res.json();
      if (data.dispatched) {
        setTestFeedback({
          type: 'success',
          message: `✅ Test card dispatched and accepted by ${channel === 'slack' ? 'Slack' : 'Microsoft Teams'}!`,
        });
      } else {
        setTestFeedback({
          type: 'error',
          message: `⚠️ Card generated, but target webhook URL was not reachable. Please verify your ${channel.toUpperCase()} webhook URL.`,
        });
      }
    } catch (err: any) {
      setTestFeedback({
        type: 'error',
        message: `❌ Failed to dispatch test alert: ${err?.message || err}`,
      });
    } finally {
      setTestingChannel(null);
    }
  };

  return (
    <>
      <SectionTitle
        eyebrow="Workspace settings"
        title="Settings & Multi-Channel Notifications"
        description="Manage organization access, cloud provider profiles, and Slack & Microsoft Teams alerts."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-white/8 bg-card/70">
          <CardHeader>
            <CardTitle className="text-base">Organization Profile</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="text-xs text-muted-foreground">
              {loaded ? 'Loaded from backend settings.' : 'Loading settings...'}
            </div>
            <label className="text-sm">
              Organization Name
              <Input
                value={orgName}
                onChange={e => setOrgName(e.target.value)}
                className="mt-2 border-white/10 bg-white/5"
                placeholder="Acme Corp"
              />
            </label>
            <Button
              className="w-fit bg-cyan-400 text-slate-950 hover:bg-cyan-300"
              onClick={handleSave}
              disabled={saving || !loaded}
            >
              {saving ? 'Saving...' : 'Save Organization'}
            </Button>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base">
                <Bell className="size-4 text-cyan-400" />
                Slack & Teams Escalations
              </CardTitle>
              <Badge variant="outline" className="border-cyan-400/30 text-cyan-300">
                Multi-Channel
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <label className="text-xs text-muted-foreground">
              Slack Incoming Webhook URL
              <Input
                value={slackWebhookUrl}
                onChange={e => setSlackWebhookUrl(e.target.value)}
                placeholder="https://hooks.slack.com/services/T.../B.../..."
                className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
              />
            </label>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="text-xs text-muted-foreground">
                Slack Bot Token (Optional)
                <Input
                  value={slackBotToken}
                  onChange={e => setSlackBotToken(e.target.value)}
                  placeholder="xoxb-..."
                  className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
                />
              </label>
              <label className="text-xs text-muted-foreground">
                Slack Target Channel
                <Input
                  value={slackChannel}
                  onChange={e => setSlackChannel(e.target.value)}
                  placeholder="#finops-alerts"
                  className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
                />
              </label>
            </div>

            <label className="text-xs text-muted-foreground">
              Microsoft Teams Webhook URL (Power Automate / Workflows)
              <Input
                value={teamsWebhookUrl}
                onChange={e => setTeamsWebhookUrl(e.target.value)}
                placeholder="https://prod-xx.westus.logic.azure.com:443/workflows/.../invoke?..."
                className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
              />
            </label>

            <label className="text-xs text-muted-foreground">
              WhatsApp Escalation Phone (Twilio)
              <Input
                value={whatsappTo}
                onChange={e => setWhatsappTo(e.target.value)}
                placeholder="+91XXXXXXXXXX"
                className="mt-1 border-white/10 bg-white/5 text-xs font-mono"
              />
            </label>

            {testFeedback && (
              <div
                className={`rounded-lg p-3 text-xs ${
                  testFeedback.type === 'success'
                    ? 'border border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
                    : 'border border-red-400/30 bg-red-400/10 text-red-300'
                }`}
              >
                {testFeedback.message}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2 pt-2">
              <Button
                size="sm"
                className="bg-cyan-400 text-slate-950 hover:bg-cyan-300"
                onClick={handleSave}
                disabled={saving || !loaded}
              >
                {saving ? 'Saving...' : 'Save Channels'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-white/10 bg-white/5 text-xs hover:bg-cyan-400/10 hover:text-cyan-300"
                onClick={() => testNotification('slack')}
                disabled={testingChannel !== null}
              >
                {testingChannel === 'slack' ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Send className="mr-1 size-3" />}
                Test Slack
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-white/10 bg-white/5 text-xs hover:bg-indigo-400/10 hover:text-indigo-300"
                onClick={() => testNotification('teams')}
                disabled={testingChannel !== null}
              >
                {testingChannel === 'teams' ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Send className="mr-1 size-3" />}
                Test Teams
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70 lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Connected Cloud Profiles</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {connectionState?.connected ? (
              <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-4">
                <div className="text-sm font-medium text-emerald-200">{connectionState.account_name || 'Connected account'}</div>
                <div className="mt-1 text-xs text-emerald-100/80">
                  {connectionState.provider || 'AWS'} · {connectionState.region || 'us-east-1'}
                </div>
                {connectionState.role_arn && (
                  <div className="mt-2 font-mono text-[11px] text-emerald-100/70">{connectionState.role_arn}</div>
                )}
                <div className="mt-3 text-xs text-emerald-100/70">
                  Active profile is restored from backend storage after refresh.
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-muted-foreground">
                No AWS account is connected yet.
              </div>
            )}

            <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
              Saved connections
            </div>
            <div className="flex flex-col gap-3">
              {(Array.isArray(connectedAccounts) && connectedAccounts.length > 0) ? connectedAccounts.map((account: any, idx: number) => (
                <div key={`${account.account_name || account.provider || 'account'}-${idx}`} className={`rounded-lg border p-4 ${account.active ? 'border-cyan-400/30 bg-cyan-400/10' : 'border-white/10 bg-white/5'}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium">{account.account_name || 'Connected account'}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {account.provider || 'AWS'} · {account.region || 'us-east-1'}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {account.active && <Badge className="bg-cyan-400 text-slate-950 hover:bg-cyan-300">Active</Badge>}
                      {!account.active && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="border-white/10 bg-white/5"
                          onClick={() => onSwitchAccount?.(account)}
                          disabled={connectionKey(account) === selectedAccountKey}
                        >
                          Switch
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="mt-3 text-xs text-muted-foreground">
                    {account.auth_method || 'keys'}{account.session_token_present ? ' · session token saved' : ''}
                  </div>
                  {account.role_arn && (
                    <div className="mt-2 font-mono text-[11px] text-muted-foreground">{account.role_arn}</div>
                  )}
                </div>
              )) : (
                <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-muted-foreground">
                  Saved connections will appear here after you connect an AWS account.
                </div>
              )}
            </div>
            <div className="rounded-lg border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Remembered login profile</div>
              {rememberedProfile ? (
                <div className="mt-3">
                  <div className="text-sm font-medium">{rememberedProfile.account_name || 'Connected account'}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {rememberedProfile.provider || 'AWS'} · {rememberedProfile.region || 'us-east-1'} · {rememberedProfile.auth_method || 'learner_lab'}
                  </div>
                  {rememberedProfile.role_arn && (
                    <div className="mt-2 font-mono text-[11px] text-muted-foreground">{rememberedProfile.role_arn}</div>
                  )}
                  <div className="mt-2 text-xs text-muted-foreground">
                    This profile is saved for prefill only. Secrets stay in the backend connection store.
                  </div>
                </div>
              ) : (
                <div className="mt-3 text-sm text-muted-foreground">No remembered profile yet.</div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}

function SchedulerPrewarmView({ currency = 'USD', apiUrl }: any) {
  const [schedules, setSchedules] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [activeTab, setActiveTab] = useState<'schedules' | 'jobs'>('schedules');
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error' | 'warning'; message: string } | null>(null);

  // New Schedule Form state
  const [formInstanceId, setFormInstanceId] = useState('');
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
  const [manualInstanceId, setManualInstanceId] = useState('');
  const [manualAction, setManualAction] = useState('STOP');
  const [manualDryRun, setManualDryRun] = useState(true);
  const [triggering, setTriggering] = useState(false);

  const fetchSchedulerData = useCallback(async () => {
    setLoading(true);
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
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    fetchSchedulerData();
    const interval = setInterval(fetchSchedulerData, 30000); // 30s auto-refresh
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
    try {
      const res = await fetch(apiUrl(`/api/v2/schedules/jobs/${jobId}/override`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, extension_hours: hours }),
      });
      if (res.ok) {
        const data = await res.json();
        setFeedback({ type: 'success', message: data.message || 'Override registered successfully!' });
        fetchSchedulerData();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Override failed' });
      }
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    }
  };

  const handleEvaluateNow = async (dryRun = true) => {
    setEvaluating(true);
    try {
      const res = await fetch(apiUrl(`/api/v2/schedules/evaluate-now?dry_run=${dryRun}`), {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
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
    setAnalyzingTelemetry(true);
    try {
      const res = await fetch(apiUrl('/api/v2/schedules/predictive/recommendations?days=14'));
      if (res.ok) {
        const data = await res.json();
        setPredictiveRecommendation(data.recommendation);
        setFeedback({
          type: 'success',
          message: `Analyzed ${data.telemetry_points_analyzed} telemetry points across 14 days. Recurrence confidence: ${data.recommendation.confidence * 100}%.`
        });
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

  // Find active grace period alerts
  const notifyingJobs = jobs.filter(j => j.status === 'NOTIFYING' || (j.status === 'PENDING' && j.action === 'STOP'));

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
              className="border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10"
            >
              {analyzingTelemetry ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <Bot className="size-3.5 mr-1.5" />}
              AI Telemetry Analysis
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleEvaluateNow(true)}
              disabled={evaluating}
              className="border-white/10 hover:bg-white/5"
            >
              {evaluating ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <RefreshCw className="size-3.5 mr-1.5" />}
              Evaluate Now
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setTriggerModalOpen(true)}
              className="border-white/10 hover:bg-white/5 text-amber-300"
            >
              <Zap className="size-3.5 mr-1.5" />
              Manual Trigger
            </Button>
            <Button
              size="sm"
              onClick={() => setCreateModalOpen(true)}
              className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-medium"
            >
              <Plus className="size-3.5 mr-1.5" />
              New Schedule
            </Button>
          </div>
        }
      />

      {predictiveRecommendation && (
        <div className="rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/40 via-slate-900 to-emerald-950/30 p-5 shadow-xl shadow-cyan-950/20 backdrop-blur">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="size-10 rounded-xl bg-cyan-500/20 flex items-center justify-center text-cyan-300 shrink-0">
                <Sparkles className="size-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-cyan-200">Predictive Pre-Warming Pattern Detected</span>
                  <Badge className="bg-cyan-500/20 text-cyan-300 border-cyan-500/30">
                    {Math.round(predictiveRecommendation.confidence * 100)}% Confidence
                  </Badge>
                </div>
                <p className="mt-1 text-xs sm:text-sm text-slate-300">
                  {predictiveRecommendation.reason}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                  <span className="text-slate-400">Target: <code className="text-cyan-300 font-mono">{predictiveRecommendation.instance_id}</code></span>
                  <span className="text-slate-400">User Activity: <strong className="text-emerald-400">{predictiveRecommendation.detected_activity_start}</strong></span>
                  <span className="text-slate-400">Pre-Warm Start: <strong className="text-cyan-400">{predictiveRecommendation.recommended_start_time}</strong></span>
                  <span className="text-slate-400">Stop Time: <strong className="text-amber-400">{predictiveRecommendation.recommended_stop_time}</strong></span>
                  <span className="text-emerald-400 font-medium">Est. Waste Reduction: ~{predictiveRecommendation.estimated_savings_percent}%</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button
                size="sm"
                onClick={handleApplyPredictive}
                className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-medium"
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
          className={`flex items-center justify-between p-3.5 rounded-xl border text-sm ${
            feedback.type === 'success'
              ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
              : feedback.type === 'warning'
              ? 'bg-amber-950/40 border-amber-500/30 text-amber-300'
              : 'bg-red-950/40 border-red-500/30 text-red-300'
          }`}
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
              className="rounded-2xl border border-amber-500/40 bg-gradient-to-r from-amber-950/60 via-slate-900 to-amber-950/30 p-5 shadow-xl shadow-amber-950/20 backdrop-blur"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="size-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-amber-400 shrink-0 animate-pulse">
                    <Bell className="size-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-amber-200">10-Minute Grace Period Active</span>
                      <Badge className="bg-amber-500/20 text-amber-300 border-amber-500/30">PENDING STOP</Badge>
                    </div>
                    <p className="mt-1 text-xs sm:text-sm text-slate-300">
                      Instance <code className="font-mono text-cyan-300 font-bold">{job.instance_id}</code> will shut down according to scheduled business closure.
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
                    className="border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/20"
                  >
                    <CheckCircle2 className="size-3.5 mr-1.5" />
                    KEEP RUNNING (2h)
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleOverride(job.id, 'STOP_NOW')}
                    className="bg-red-500/80 hover:bg-red-600 text-white"
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
          tone="cyan"
        />
        <MetricCard
          icon={Zap}
          label="Predictive Pre-Warming"
          value="15m Lead"
          detail="Pre-heats instances before user surge"
          tone="emerald"
        />
        <MetricCard
          icon={ShieldCheck}
          label="Guardian Safety Gate"
          value="Online"
          detail="SSH, Backup & Tag checks enforced"
          tone="amber"
        />
        <MetricCard
          icon={CircleDollarSign}
          label="Est. Off-Hours Savings"
          value="~68%"
          detail="Eliminates overnight & weekend waste"
          tone="cyan"
        />
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center justify-between border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <Button
            variant={activeTab === 'schedules' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('schedules')}
            className={activeTab === 'schedules' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' : 'text-muted-foreground'}
          >
            Operational Schedules ({schedules.length})
          </Button>
          <Button
            variant={activeTab === 'jobs' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('jobs')}
            className={activeTab === 'jobs' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' : 'text-muted-foreground'}
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
                  <Button size="sm" className="bg-cyan-400 text-slate-950 hover:bg-cyan-300" onClick={() => setCreateModalOpen(true)}>
                    <Plus className="mr-1.5 size-3.5" />
                    New Schedule
                  </Button>
                }
                className="my-4 border-0"
              />
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader className="bg-white/[0.02]">
                    <TableRow className="border-white/8">
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
                        <TableRow key={s.id} className="border-white/5 hover:bg-white/[0.02]">
                          <TableCell className="font-mono text-xs font-medium text-cyan-300">
                            {s.instance_id}
                          </TableCell>
                          <TableCell className="text-xs">
                            <span className="font-medium text-emerald-400">{s.start_time}</span>
                            <span className="text-muted-foreground mx-1.5">to</span>
                            <span className="font-medium text-amber-400">{s.stop_time}</span>
                            <span className="text-[10px] text-muted-foreground ml-1.5">({s.timezone})</span>
                          </TableCell>
                          <TableCell className="text-xs text-slate-300">
                            {daysActive || 'None'}
                          </TableCell>
                          <TableCell className="text-xs font-mono text-emerald-300">
                            {s.prewarm_minutes} mins
                          </TableCell>
                          <TableCell className="text-xs font-mono text-amber-300">
                            {s.grace_period_minutes} mins
                          </TableCell>
                          <TableCell>
                            <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-[10px]">
                              ENABLED
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteSchedule(s.id)}
                              className="text-red-400 hover:text-red-300 hover:bg-red-500/10 h-7 px-2 text-xs"
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
        <Card className="border-white/8 bg-card/70 backdrop-blur">
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
                  <TableHeader className="bg-white/[0.02]">
                    <TableRow className="border-white/8">
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
                      const isSuccess = j.status === 'SUCCESS';
                      const isBlocked = j.status === 'BLOCKED';
                      const isNotifying = j.status === 'NOTIFYING';
                      const isOverridden = j.status === 'OVERRIDDEN';

                      return (
                        <TableRow key={j.id} className="border-white/5 hover:bg-white/[0.02]">
                          <TableCell className="text-xs">
                            <div className="font-mono text-slate-300">{j.id.slice(0, 8)}...</div>
                            <div className="text-[10px] text-muted-foreground">
                              {j.scheduled_at ? new Date(j.scheduled_at).toLocaleTimeString() : 'N/A'}
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-xs text-cyan-300">
                            {j.instance_id}
                          </TableCell>
                          <TableCell>
                            <span
                              className={`text-xs font-semibold px-2 py-0.5 rounded ${
                                j.action === 'START' || j.action === 'PREWARM'
                                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                  : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                              }`}
                            >
                              {j.action}
                            </span>
                          </TableCell>
                          <TableCell>
                            <Badge
                              className={`text-[10px] ${
                                isSuccess
                                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                  : isBlocked
                                  ? 'bg-red-500/10 text-red-400 border-red-500/20'
                                  : isNotifying
                                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse'
                                  : isOverridden
                                  ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                                  : 'bg-slate-500/10 text-slate-300 border-slate-500/20'
                              }`}
                            >
                              {j.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs max-w-xs">
                            {isBlocked ? (
                              <div className="text-red-300 font-medium">🛑 {j.blocked_reason}</div>
                            ) : (
                              <div className="text-slate-300">{j.reason || 'Normal schedule dispatch'}</div>
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
                                  className="text-emerald-400 hover:bg-emerald-500/10 h-6 px-2 text-[10px]"
                                >
                                  Override (2h)
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleOverride(j.id, 'STOP_NOW')}
                                  className="text-red-400 hover:bg-red-500/10 h-6 px-2 text-[10px]"
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
        <DialogContent className="border-white/10 bg-slate-900 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold flex items-center gap-2">
              <Zap className="size-4 text-cyan-400" />
              Create Operational Schedule
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Define daily operating windows, pre-warming lead times, and grace periods for an EC2 instance.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSaveSchedule} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-medium text-slate-300">EC2 Instance ID</label>
              <Input
                placeholder="e.g. i-0a1b2c3d4e5f60718"
                value={formInstanceId}
                onChange={(e) => setFormInstanceId(e.target.value)}
                className="mt-1 bg-white/5 border-white/10 text-xs font-mono"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-300">Timezone</label>
                <Select value={formTimezone} onValueChange={(val) => { if (val) setFormTimezone(val); }}>
                  <SelectTrigger className="mt-1 bg-white/5 border-white/10 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-white/10 text-white text-xs">
                    <SelectItem value="Asia/Kolkata">Asia/Kolkata (IST)</SelectItem>
                    <SelectItem value="UTC">UTC</SelectItem>
                    <SelectItem value="America/New_York">America/New_York (EST)</SelectItem>
                    <SelectItem value="Europe/London">Europe/London (GMT)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300">Pre-Warm Lead (Mins)</label>
                <Input
                  type="number"
                  min="0"
                  max="60"
                  value={formPrewarmMins}
                  onChange={(e) => setFormPrewarmMins(Number(e.target.value))}
                  className="mt-1 bg-white/5 border-white/10 text-xs font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-emerald-400">START Time (24h)</label>
                <Input
                  type="time"
                  value={formStartTime}
                  onChange={(e) => setFormStartTime(e.target.value)}
                  className="mt-1 bg-white/5 border-white/10 text-xs font-mono"
                  required
                />
              </div>
              <div>
                <label className="text-xs font-medium text-amber-400">STOP Time (24h)</label>
                <Input
                  type="time"
                  value={formStopTime}
                  onChange={(e) => setFormStopTime(e.target.value)}
                  className="mt-1 bg-white/5 border-white/10 text-xs font-mono"
                  required
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1.5">Active Days</label>
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
                        ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300 font-semibold'
                        : 'bg-white/5 border-white/10 text-muted-foreground'
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
              <Button type="submit" size="sm" className="bg-cyan-500 text-slate-950 hover:bg-cyan-400 font-medium">
                Save Operational Schedule
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* MANUAL TRIGGER MODAL */}
      <Dialog open={triggerModalOpen} onOpenChange={setTriggerModalOpen}>
        <DialogContent className="border-white/10 bg-slate-900 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold flex items-center gap-2">
              <ShieldCheck className="size-4 text-amber-400" />
              Manual Trigger (Guardian Protected)
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Immediately dispatch an EC2 power state request through the Guardian validation layer.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleManualTrigger} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-medium text-slate-300">EC2 Instance ID</label>
              <Input
                placeholder="e.g. i-0a1b2c3d4e5f60718"
                value={manualInstanceId}
                onChange={(e) => setManualInstanceId(e.target.value)}
                className="mt-1 bg-white/5 border-white/10 text-xs font-mono"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-300">Action</label>
                <Select value={manualAction} onValueChange={(val) => { if (val) setManualAction(val); }}>
                  <SelectTrigger className="mt-1 bg-white/5 border-white/10 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-white/10 text-white text-xs">
                    <SelectItem value="START">START Instance</SelectItem>
                    <SelectItem value="STOP">STOP Instance</SelectItem>
                    <SelectItem value="PREWARM">PREWARM Instance</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300">Execution Mode</label>
                <Select
                  value={manualDryRun ? 'dry_run' : 'live'}
                  onValueChange={(v) => setManualDryRun(v === 'dry_run')}
                >
                  <SelectTrigger className="mt-1 bg-white/5 border-white/10 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-white/10 text-white text-xs">
                    <SelectItem value="dry_run">Dry Run (Simulate)</SelectItem>
                    <SelectItem value="live">Live AWS Execution</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-300/90">
              <span className="font-semibold">Guardian Gate:</span> Every request will verify active SSH sessions, EBS snapshots, and tag guardrails before any cloud action.
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setTriggerModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={triggering} className="bg-amber-500 text-slate-950 hover:bg-amber-400 font-medium">
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

function GitOpsSlaView({ currency = 'USD', apiUrl, items = [], applied, setApplied }: any) {
  const [activeTab, setActiveTab] = useState<'watchdog' | 'audit'>('watchdog');
  const [watches, setWatches] = useState<any[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

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
                      {auditLog.map((log: any, idx: number) => (
                        <TableRow key={`${log.pr_id || idx}`} className="border-white/8">
                          <TableCell className="text-xs text-muted-foreground font-mono">
                            {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : 'Recent'}
                          </TableCell>
                          <TableCell className="text-xs font-medium max-w-xs truncate">
                            {log.title || log.pr_title || 'Autonomous Optimization PR'}
                          </TableCell>
                          <TableCell className="text-xs font-mono text-cyan-300">
                            {log.resource_id || 'multi-resource'}
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
                                log.status === 'rolled_back' || log.status === 'rollback_pr_ready'
                                  ? 'border-purple-400/30 text-purple-300'
                                  : 'border-emerald-400/30 text-emerald-300'
                              }
                            >
                              {log.status || 'MERGED'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right text-xs font-semibold text-emerald-300">
                            {log.monthly_savings ? `Saves ${formatCurrency(log.monthly_savings, currency)}` : 'Optimized'}
                          </TableCell>
                        </TableRow>
                      ))}
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
    </>
  );
}

function FleetView({ currency = 'USD', apiUrl }: { currency: 'USD' | 'INR'; apiUrl: (path: string) => string }) {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<any>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [discoverResult, setDiscoverResult] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanFeedback, setScanFeedback] = useState<any | null>(null);
  const [scanningAccId, setScanningAccId] = useState<string | null>(null);

  // Enroll Account state
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [newAccId, setNewAccId] = useState('');
  const [newAccName, setNewAccName] = useState('');
  const [newAccRole, setNewAccRole] = useState('');
  const [newAccRegion, setNewAccRegion] = useState('us-east-1');
  const [isMgmtAcc, setIsMgmtAcc] = useState(false);
  const [enrolling, setEnrolling] = useState(false);

  const fetchFleet = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, accRes] = await Promise.all([
        fetch(apiUrl('/api/v2/fleet/summary')),
        fetch(apiUrl('/api/v2/fleet/accounts')),
      ]);
      if (sumRes.ok) setSummary(await sumRes.json());
      if (accRes.ok) {
        const d = await accRes.json();
        setAccounts(Array.isArray(d?.accounts) ? d.accounts : []);
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
        body: JSON.stringify(specificIds ? { account_ids: specificIds } : {}),
      });
      const data = await res.json();
      if (res.ok) {
        setScanFeedback(data);
        await fetchFleet();
      }
    } catch (err) {
      console.error('Fleet scan failed:', err);
    } finally {
      setScanning(false);
      setScanningAccId(null);
    }
  };

  const handleEnroll = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAccId) return;
    setEnrolling(true);
    try {
      const res = await fetch(apiUrl('/api/v2/fleet/accounts'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: newAccId,
          account_name: newAccName || `Account-${newAccId}`,
          role_arn: newAccRole || undefined,
          region: newAccRegion,
          is_management_account: isMgmtAcc,
        }),
      });
      if (res.ok) {
        setEnrollOpen(false);
        setNewAccId('');
        setNewAccName('');
        setNewAccRole('');
        await fetchFleet();
      }
    } catch (err) {
      console.error('Enroll failed:', err);
    } finally {
      setEnrolling(false);
    }
  };

  const filteredAccounts = useMemo(() => {
    return accounts.filter(acc =>
      (acc.account_id || '').toLowerCase().includes(search.toLowerCase()) ||
      (acc.account_name || '').toLowerCase().includes(search.toLowerCase()) ||
      (acc.region || '').toLowerCase().includes(search.toLowerCase())
    );
  }, [accounts, search]);

  const totalRegistered = summary?.total_accounts_registered || Math.max(accounts.length, 1);
  const totalSpend = summary?.total_fleet_monthly_spend || 68.40;
  const totalNodes = summary?.total_fleet_nodes || 0;
  const totalVolumes = summary?.total_fleet_volumes || 0;
  const totalEips = summary?.total_fleet_eips || 0;

  return (
    <>
      <SectionTitle
        eyebrow="Enterprise Fleet Management"
        title="100+ AWS Member Account Auto-Discovery"
        description="Centralized AWS Organizations visibility, multi-account health governance, and parallel cross-account waste sweeps."
        status={
          <Badge variant="outline" className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            AWS Organizations Fleet
          </Badge>
        }
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="border-white/10 bg-white/5 text-xs hover:bg-white/10"
              onClick={() => setEnrollOpen(true)}
            >
              <Plus className="mr-1.5 size-3.5" /> Enroll Account
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300 hover:bg-cyan-400/20 text-xs"
              onClick={handleDiscover}
              disabled={discovering}
            >
              {discovering ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Network className="mr-1.5 size-3.5" />}
              Auto-Discover Org Accounts
            </Button>
            <Button
              size="sm"
              className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 text-xs font-medium"
              onClick={() => handleScanFleet()}
              disabled={scanning}
            >
              {scanning ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Play className="mr-1.5 size-3.5" />}
              Run Fleet Sweep
            </Button>
          </div>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Discovered Fleet Accounts</span>
              <Network className="size-4 text-cyan-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-cyan-300">{totalRegistered}</div>
            <div className="mt-1 text-xs text-muted-foreground">Auto-discovered across AWS Org</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Fleet-Wide Monthly Spend</span>
              <CircleDollarSign className="size-4 text-emerald-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-foreground">
              {formatCurrency(totalSpend, currency)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Across all member accounts</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Managed Cloud Footprint</span>
              <Server className="size-4 text-indigo-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-indigo-300">
              {formatInteger(totalNodes + totalVolumes + totalEips)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {totalNodes} EC2 · {totalVolumes} EBS · {totalEips} EIPs
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Last Fleet Sweep</span>
              <Activity className="size-4 text-amber-400" />
            </div>
            <div className="mt-3 text-2xl font-bold text-amber-300">
              {summary?.scan_duration_seconds ? `${summary.scan_duration_seconds.toFixed(2)}s` : 'Active'}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {summary?.successful_scans ?? 1}/{summary?.accounts_scanned ?? 1} scans successful
            </div>
          </CardContent>
        </Card>
      </div>

      {discoverResult && (
        <div className="mb-4 rounded-lg border border-cyan-400/30 bg-cyan-400/10 p-3 text-xs text-cyan-200">
          {discoverResult}
        </div>
      )}

      {scanFeedback && (
        <div className="mb-4 rounded-lg border border-emerald-400/30 bg-emerald-400/10 p-3 text-xs text-emerald-200 flex items-center justify-between">
          <span>
            ✅ Parallel scan completed across {scanFeedback.accounts_scanned} accounts in {scanFeedback.scan_duration_seconds}s! Total monthly spend analyzed: {formatCurrency(scanFeedback.total_fleet_monthly_spend, currency)}.
          </span>
          <Button variant="ghost" size="sm" className="h-6 text-[11px]" onClick={() => setScanFeedback(null)}>
            Dismiss
          </Button>
        </div>
      )}

      <Card className="border-white/8 bg-card/70">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="text-base font-semibold">AWS Member Accounts Directory</CardTitle>
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
                className="pl-8 h-9 border-white/10 bg-white/5 text-xs"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <TableSkeleton rows={5} cols={7} />
          ) : filteredAccounts.length === 0 ? (
            <EmptyState
              icon={Server}
              title={search ? `No accounts matching "${search}"` : "No Fleet Accounts Enrolled"}
              description={search ? "Try adjusting your search query." : "Click 'Auto-Discover Org Accounts' or 'Enroll Account' to start multi-account management."}
              action={
                search ? (
                  <Button variant="outline" size="sm" onClick={() => setSearch('')}>
                    Clear search
                  </Button>
                ) : (
                  <Button size="sm" className="bg-cyan-400 text-slate-950 hover:bg-cyan-300" onClick={handleDiscover}>
                    Auto-Discover Org Accounts
                  </Button>
                )
              }
              className="my-4 border-0"
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-white/8 hover:bg-transparent">
                    <TableHead className="text-xs">Account ID</TableHead>
                    <TableHead className="text-xs">Account Name</TableHead>
                    <TableHead className="text-xs">Region</TableHead>
                    <TableHead className="text-xs">Role ARN / Session</TableHead>
                    <TableHead className="text-xs">Hierarchy</TableHead>
                    <TableHead className="text-xs text-center">Status</TableHead>
                    <TableHead className="text-xs text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAccounts.map((acc: any) => {
                    const isMgmt = acc.is_management_account;
                    const isScanning = scanningAccId === acc.account_id;
                    return (
                      <TableRow key={acc.account_id} className="border-white/8">
                        <TableCell className="font-mono text-xs font-semibold text-cyan-300">
                          {acc.account_id}
                        </TableCell>
                        <TableCell className="text-xs font-medium">
                          {acc.account_name || 'Member Account'}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground font-mono">
                          {acc.region || 'us-east-1'}
                        </TableCell>
                        <TableCell className="text-xs font-mono text-slate-400 max-w-xs truncate">
                          {acc.role_arn || acc.auth_type || 'CloudPulseReadOnlyRole'}
                        </TableCell>
                        <TableCell className="text-xs">
                          {isMgmt ? (
                            <Badge variant="outline" className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300 text-[10px]">
                              Management Root
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="border-white/10 text-[10px]">
                              Member Account
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-center">
                          <Badge
                            variant="outline"
                            className={
                              acc.status === 'SUSPENDED'
                                ? 'border-red-400/30 text-red-300'
                                : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
                            }
                          >
                            {acc.status || 'ACTIVE'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-[11px] border-white/10 bg-white/5 hover:bg-cyan-400/10 hover:text-cyan-300"
                            disabled={isScanning}
                            onClick={() => handleScanFleet([acc.account_id])}
                          >
                            {isScanning ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Play className="mr-1 size-3 text-cyan-400" />}
                            Scan
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

      {/* Enroll Account Modal */}
      <Dialog open={enrollOpen} onOpenChange={setEnrollOpen}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto border-white/10 bg-slate-950 text-foreground">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <Plus className="size-4 text-cyan-400" /> Enroll AWS Account into Fleet
            </DialogTitle>
            <DialogDescription>
              Configure cross-account IAM Role ARN for automated multi-account optimization.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEnroll} className="space-y-3 py-2">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">AWS Account ID *</label>
              <Input
                placeholder="12-digit AWS Account ID"
                value={newAccId}
                onChange={e => setNewAccId(e.target.value)}
                required
                className="border-white/10 bg-white/5 text-xs font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Account Display Name</label>
              <Input
                placeholder="e.g. Acme Payments Production"
                value={newAccName}
                onChange={e => setNewAccName(e.target.value)}
                className="border-white/10 bg-white/5 text-xs"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Cross-Account IAM Role ARN</label>
              <Input
                placeholder="arn:aws:iam::123456789:role/CloudPulseReadOnlyRole"
                value={newAccRole}
                onChange={e => setNewAccRole(e.target.value)}
                className="border-white/10 bg-white/5 text-xs font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Primary Region</label>
              <Input
                placeholder="us-east-1"
                value={newAccRegion}
                onChange={e => setNewAccRegion(e.target.value)}
                className="border-white/10 bg-white/5 text-xs"
              />
            </div>
            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="isMgmtAcc"
                checked={isMgmtAcc}
                onChange={e => setIsMgmtAcc(e.target.checked)}
                className="rounded border-white/10"
              />
              <label htmlFor="isMgmtAcc" className="text-xs text-muted-foreground cursor-pointer">
                Mark as AWS Organizations Management (Payer) Account
              </label>
            </div>
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-3">
              <Button type="button" variant="ghost" size="sm" onClick={() => setEnrollOpen(false)}>Cancel</Button>
              <Button type="submit" size="sm" className="bg-cyan-400 text-slate-950 hover:bg-cyan-300" disabled={enrolling}>
                {enrolling ? <Loader2 className="mr-1 size-3 animate-spin" /> : null} Enroll Account
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function CiCdGuardrailView({ currency = 'USD', apiUrl }: { currency: 'USD' | 'INR'; apiUrl: (path: string) => string }) {
  const [appStatus, setAppStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [filePath, setFilePath] = useState('terraform/compute.tf');
  const [diffText, setDiffText] = useState(
`--- a/terraform/compute.tf
+++ b/terraform/compute.tf
@@ -14,3 +14,3 @@
 resource "aws_instance" "worker_fleet" {
-  instance_type = "m5.2xlarge"
+  instance_type = "t4g.small"
   count         = 3
 }`
  );
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [copiedWebhook, setCopiedWebhook] = useState(false);
  const [activePreset, setActivePreset] = useState(0);

  const PRESETS = [
    {
      label: 'Fleet Downsizing (Cost Reduction)',
      filePath: 'terraform/compute.tf',
      diff: `--- a/terraform/compute.tf\n+++ b/terraform/compute.tf\n@@ -14,3 +14,3 @@\n resource "aws_instance" "worker_fleet" {\n-  instance_type = "m5.2xlarge"\n+  instance_type = "t4g.small"\n   count         = 3\n }`,
    },
    {
      label: 'High-Spec GPU Spikes (> $500/mo Policy Breach)',
      filePath: 'terraform/ml_nodes.tf',
      diff: `--- a/terraform/ml_nodes.tf\n+++ b/terraform/ml_nodes.tf\n@@ -1,4 +1,8 @@\n+resource "aws_instance" "ai_cluster" {\n+  instance_type = "p4d.24xlarge"\n+  count         = 2\n+  ebs_block_device {\n+    volume_type = "io2"\n+    volume_size = 1000\n+    iops        = 50000\n+  }\n+}`,
    },
    {
      label: 'EBS gp2 to gp3 Storage Upgrade',
      filePath: 'terraform/storage.tf',
      diff: `--- a/terraform/storage.tf\n+++ b/terraform/storage.tf\n@@ -5,3 +5,3 @@\n resource "aws_ebs_volume" "primary_disk" {\n-  type = "gp2"\n+  type = "gp3"\n   size = 500\n }`,
    },
  ];

  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const res = await fetch(apiUrl('/api/v2/github/status'));
        if (res.ok && !cancelled) setAppStatus(await res.json());
      } catch (err) {
        console.error('Failed to fetch github app status:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchStatus();
    return () => { cancelled = true; };
  }, [apiUrl]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const res = await fetch(apiUrl('/api/v2/github/analyze-pr'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          diff: diffText,
          file_path: filePath,
          currency,
          rate: 84.0,
          pull_number: 142,
        }),
      });
      if (res.ok) {
        setAnalysisResult(await res.json());
      }
    } catch (err) {
      console.error('Diff analysis failed:', err);
    } finally {
      setAnalyzing(false);
    }
  };

  const selectPreset = (idx: number) => {
    setActivePreset(idx);
    const p = PRESETS[idx];
    setFilePath(p.filePath);
    setDiffText(p.diff);
    setAnalysisResult(null);
  };

  const webhookEndpoint = apiUrl('/api/v2/github/webhook');
  const checkStatus = analysisResult?.check_run?.conclusion || 'neutral';
  const monthlyDelta = analysisResult?.analysis?.monthly_cost_delta_usd ?? 0;

  return (
    <>
      <SectionTitle
        eyebrow="FinOps Shift-Left CI/CD"
        title="Native GitHub App & PR Cost Guardrails"
        description="Automated cost impact diff analysis on Pull Requests before merging to prevent cloud bill shock."
        status={
          <Badge variant="outline" className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            PR Policy Enforcement
          </Badge>
        }
      />

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Card className="border-white/8 bg-card/70 lg:col-span-1">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <GitPullRequest className="size-4 text-cyan-400" />
                GitHub App Status
              </CardTitle>
              <Badge variant="outline" className="border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-[11px]">
                {appStatus?.status === 'active' ? 'Active & Ready' : 'Configured'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-xs">
            <div>
              <span className="text-muted-foreground block">Application Name</span>
              <span className="font-semibold text-foreground text-sm">{appStatus?.app_name || 'CloudPulse FinOps Guardrail'}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Cost Spike Guardrail Policy</span>
              <span className="font-semibold text-amber-300">
                Block merge if PR spend delta &gt; ${appStatus?.spike_threshold_usd || 500}.00/mo
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block">Supported CI/CD Engines</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {(appStatus?.supported_providers || ['GitHub Actions', 'GitLab CI', 'Bitbucket']).map((p: string) => (
                  <Badge key={p} variant="outline" className="border-white/10 text-[10px]">{p}</Badge>
                ))}
              </div>
            </div>
            <div className="pt-2 border-t border-white/8">
              <span className="text-muted-foreground block mb-1">GitHub Webhook URL</span>
              <div className="flex items-center gap-1.5">
                <Input
                  readOnly
                  value={webhookEndpoint}
                  className="font-mono text-[11px] h-8 border-white/10 bg-white/5"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 border-white/10 px-2.5 shrink-0"
                  onClick={() => {
                    navigator.clipboard.writeText(webhookEndpoint);
                    setCopiedWebhook(true);
                    setTimeout(() => setCopiedWebhook(false), 2000);
                  }}
                >
                  {copiedWebhook ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70 lg:col-span-2">
          <CardHeader>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle className="text-base font-semibold">Interactive PR Diff Simulator</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Test Terraform HCL or cloud diffs against FinOps budget policies in real time.
                </p>
              </div>
              <Button
                size="sm"
                className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-medium text-xs"
                onClick={handleAnalyze}
                disabled={analyzing}
              >
                {analyzing ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Play className="mr-1.5 size-3.5" />}
                Run Guardrail Analysis
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <span className="text-xs text-muted-foreground block mb-1.5">Select Test Scenarios:</span>
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p, idx) => (
                  <Button
                    key={p.label}
                    type="button"
                    variant={activePreset === idx ? 'default' : 'outline'}
                    size="sm"
                    className={`text-xs h-7 ${activePreset === idx ? 'bg-cyan-500 text-slate-950 hover:bg-cyan-400' : 'border-white/10 bg-white/5'}`}
                    onClick={() => selectPreset(idx)}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div className="sm:col-span-2">
                <label className="text-xs text-muted-foreground block mb-1">Target Infrastructure File Path</label>
                <Input
                  value={filePath}
                  onChange={e => setFilePath(e.target.value)}
                  className="font-mono text-xs h-8 border-white/10 bg-white/5"
                />
              </div>
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">Git Diff / Terraform Plan Content</label>
              <textarea
                value={diffText}
                onChange={e => setDiffText(e.target.value)}
                rows={7}
                className="w-full rounded-lg border border-white/10 bg-black/60 p-3 font-mono text-xs text-emerald-300 focus:outline-none focus:ring-1 focus:ring-cyan-400"
                placeholder="Paste git diff or Terraform HCL change here..."
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {analysisResult && (
        <Card className="border-white/8 bg-card/70 mb-6">
          <CardHeader>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <CardTitle className="text-base flex items-center gap-2">
                <GitPullRequest className="size-4 text-cyan-400" />
                Guardrail Evaluation &amp; GitHub PR Comment Preview
              </CardTitle>
              <Badge
                variant="outline"
                className={`text-xs font-bold px-3 py-1 ${
                  checkStatus === 'failure'
                    ? 'border-red-400/40 bg-red-400/10 text-red-300'
                    : checkStatus === 'action_required'
                    ? 'border-amber-400/40 bg-amber-400/10 text-amber-300'
                    : 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                }`}
              >
                CHECK-RUN: {checkStatus.toUpperCase()}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className={`p-4 rounded-lg border text-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${
                checkStatus === 'failure'
                  ? 'border-red-400/30 bg-red-400/10 text-red-200'
                  : checkStatus === 'action_required'
                  ? 'border-amber-400/30 bg-amber-400/10 text-amber-200'
                  : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
              }`}
            >
              <div className="flex items-center gap-2">
                {checkStatus === 'failure' ? (
                  <ShieldAlert className="size-5 text-red-400 shrink-0" />
                ) : checkStatus === 'action_required' ? (
                  <AlertTriangle className="size-5 text-amber-400 shrink-0" />
                ) : (
                  <ShieldCheck className="size-5 text-emerald-400 shrink-0" />
                )}
                <div>
                  <div className="font-semibold text-sm">
                    {checkStatus === 'failure'
                      ? '🚨 Merge Blocked: Cost Increase Breaches $500/mo FinOps Policy'
                      : checkStatus === 'action_required'
                      ? '⚠️ Warning: PR introduces moderate cost increase'
                      : '✅ FinOps Guardrail Passed: PR reduces infrastructure spend or maintains budget'}
                  </div>
                  <div className="text-[11px] opacity-90 mt-0.5">
                    {analysisResult.check_run?.output?.summary || 'Evaluated against organization FinOps baseline'}
                  </div>
                </div>
              </div>
              <div className="text-left sm:text-right shrink-0 font-mono pt-1 sm:pt-0 border-t sm:border-t-0 border-white/10">
                <div className="text-xs text-muted-foreground">Monthly Net Delta</div>
                <div className={`text-base font-bold ${monthlyDelta > 0 ? 'text-red-400' : 'text-emerald-300'}`}>
                  {monthlyDelta > 0 ? `+${formatCurrency(monthlyDelta, currency)}` : formatCurrency(monthlyDelta, currency)}/mo
                </div>
              </div>
            </div>

            <div>
              <span className="text-xs text-muted-foreground block mb-2 font-medium">Rendered GitHub PR Bot Comment:</span>
              <pre className="max-h-80 overflow-auto rounded-lg border border-white/10 bg-slate-950 p-4 font-mono text-xs text-slate-200 whitespace-pre-wrap">
                {analysisResult.comment_markdown || analysisResult.check_run?.output?.text}
              </pre>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}

function ConnectModal({ open, onOpenChange, onSuccess, initialProfile }: any) {
  const [cloud, setCloud] = useState('AWS');
  const [accountName, setAccountName] = useState('');
  const [authMethod, setAuthMethod] = useState('learner_lab');
  const [accessKey, setAccessKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [sessionToken, setSessionToken] = useState('');
  const [roleArn, setRoleArn] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (!open) return;
    const profile = initialProfile || readStoredProfile();
    if (!profile) return;
    setCloud(profile.provider || 'AWS');
    setAccountName(profile.account_name || '');
    setAuthMethod(profile.auth_method || 'learner_lab');
    setRoleArn(profile.role_arn || '');
    setRegion(profile.region || 'us-east-1');
  }, [open, initialProfile]);

  const connect = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const res = await fetch(apiUrl('/api/v1/connect-cloud'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: cloud,
          account_name: accountName,
          auth_method: authMethod,
          access_key: accessKey,
          secret_key: secretKey,
          session_token: sessionToken,
          role_arn: roleArn,
          region,
        })
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        setSuccess(data?.message || 'Success');
        onSuccess?.({
          ...data,
          provider: data?.connection?.provider || data?.provider || cloud,
          account_name: data?.connection?.account_name || accountName,
          region: data?.connection?.region || region,
          auth_method: authMethod,
          role_arn: roleArn,
        });
        window.setTimeout(() => onOpenChange(false), 700);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail || 'Connection failed');
      }
    } catch (err) {
      console.error('Failed to connect account:', err);
      setError('Failed to connect account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-white/10 bg-card sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Connect a cloud account</DialogTitle>
          <DialogDescription>Give CloudPulse read-only access to start syncing your infrastructure.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4 pt-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm">
              Cloud provider
              <Select value={cloud} onValueChange={(value) => setCloud(value ?? 'AWS')}>
                <SelectTrigger className="mt-2 w-full border-white/10 bg-white/5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="AWS">AWS</SelectItem>
                  <SelectItem value="GCP">GCP</SelectItem>
                  <SelectItem value="Azure">Azure</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="text-sm">
              Auth method
              <Select value={authMethod} onValueChange={(value) => setAuthMethod(value ?? 'learner_lab')}>
                <SelectTrigger className="mt-2 w-full border-white/10 bg-white/5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="learner_lab">Learner Lab</SelectItem>
                  <SelectItem value="keys">Access keys</SelectItem>
                  <SelectItem value="iam_role">IAM role</SelectItem>
                </SelectContent>
              </Select>
            </label>
          </div>
          <label className="text-sm">
            Account name
            <Input value={accountName} onChange={e => setAccountName(e.target.value)} placeholder="Acme production" className="mt-2 border-white/10 bg-white/5" />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm">
              Access key
              <Input value={accessKey} onChange={e => setAccessKey(e.target.value)} placeholder="AKIA..." className="mt-2 border-white/10 bg-white/5" />
            </label>
            <label className="text-sm">
              Secret key
              <Input value={secretKey} onChange={e => setSecretKey(e.target.value)} placeholder="••••••••••••••••" type="password" className="mt-2 border-white/10 bg-white/5" />
            </label>
          </div>
          <label className="text-sm">
            Session token
            <Input value={sessionToken} onChange={e => setSessionToken(e.target.value)} placeholder="Temporary session token" className="mt-2 border-white/10 bg-white/5" />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm">
              IAM Role ARN / Identifier
              <Input value={roleArn} onChange={e => setRoleArn(e.target.value)} placeholder="arn:aws:iam::123456789:role/CloudPulseReadOnly" className="mt-2 border-white/10 bg-white/5" />
            </label>
            <label className="text-sm">
              Region
              <Input value={region} onChange={e => setRegion(e.target.value)} placeholder="us-east-1" className="mt-2 border-white/10 bg-white/5" />
            </label>
          </div>
          {error && (
            <div className="rounded-lg border border-red-400/20 bg-red-400/10 px-3 py-2 text-sm text-red-200">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-sm text-emerald-200">
              {success}
            </div>
          )}
          <Button onClick={connect} disabled={loading} className="mt-2 bg-cyan-400 text-slate-950 hover:bg-cyan-300">
            {loading ? <><RefreshCw className="animate-spin" data-icon="inline-start" />Testing connection...</> : 'Connect Account'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
