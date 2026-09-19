'use client'

import { useMemo, useState, useEffect, useCallback } from 'react'
import {
  Activity, AlertTriangle, Archive, ArrowDownRight, ArrowUpRight, BarChart3, Bell, Bot, Check,
  ChevronDown, ChevronLeft, ChevronRight, CircleDollarSign, Cloud, CloudCog, Cpu, Database,
  ExternalLink, HardDrive, KeyRound, LayoutDashboard, Menu, Moon, MoreHorizontal, Network,
  PanelLeft, Plus, RefreshCw, Search, Send, Server, Settings, ShieldAlert, SlidersHorizontal,
  Sparkles, Sun, X, Zap, Loader2
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

// Base URL for CloudPulse Backend (Render Web Service or local)
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '')
const apiUrl = (path: string) => path.startsWith('http') ? path : `${API_BASE}${path}`

// Navigation configuration
const nav = [
  { id: 'overview', label: 'Executive Overview', icon: LayoutDashboard },
  { id: 'inventory', label: 'Inventory', icon: Server },
  { id: 'telemetry', label: 'Telemetry & Metrics', icon: Activity },
  { id: 'security', label: 'Security & Exposure', icon: ShieldAlert },
  { id: 'optimization', label: 'Cost Optimization', icon: CircleDollarSign },
  { id: 'copilot', label: 'AI FinOps Copilot', icon: Sparkles },
  { id: 'settings', label: 'Settings & API Keys', icon: Settings },
]

function MetricCard({ icon: Icon, label, value, detail, tone = 'cyan', trend }: any) {
  return (
    <Card className="border-white/8 bg-card/70 shadow-lg shadow-black/10 backdrop-blur">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className={`flex size-10 items-center justify-center rounded-xl bg-${tone}-500/10 text-${tone}-400`}>
            <Icon className="size-5" />
          </div>
          {trend && (
            <span className="flex items-center gap-1 text-xs font-medium text-emerald-400">
              <ArrowUpRight className="size-3" />{trend}
            </span>
          )}
        </div>
        <div className="mt-5 text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
        <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
      </CardContent>
    </Card>
  )
}

function SectionTitle({ eyebrow, title, description, action, status }: any) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-cyan-400">
          <span className="size-1.5 rounded-full bg-cyan-400" />{eyebrow}
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-balance">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {status}
        {action}
      </div>
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
      if (failed.length > 0 && connectionAccessMode !== 'limited') {
        setDataError(`Loaded ${Object.keys(requests).length - failed.length}/${Object.keys(requests).length} data sources. Some AWS APIs are unavailable for this account.`);
      }
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

  const loadedDataSources = DATA_SOURCES.filter(source => dataSources[source.key]?.status === 'ready' || dataSources[source.key]?.status === 'partial');
  const failedDataSources = DATA_SOURCES.filter(source => dataSources[source.key]?.status === 'error');
  const overviewStatus: SyncState = dataSources.summary?.status || (syncing ? 'loading' : 'idle');

  return (
    <div className={light ? 'light' : 'dark'}>
      <main className="min-h-screen bg-background text-foreground">
        <aside className={`fixed inset-y-0 left-0 z-30 hidden border-r border-white/8 bg-sidebar/90 transition-all lg:flex lg:flex-col ${collapsed ? 'w-20' : 'w-64'}`}>
          <div className="flex h-16 items-center gap-3 border-b border-white/8 px-5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-cyan-400 text-slate-950">
              <CloudCog className="size-5" />
            </div>
            {!collapsed && <span className="text-lg font-semibold tracking-tight">Cloud<span className="text-cyan-400">Pulse</span></span>}
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

        <div className={`transition-all ${collapsed ? 'lg:pl-20' : 'lg:pl-64'}`}>
          <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b border-white/8 bg-background/80 px-4 backdrop-blur-xl lg:px-8">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation"><Menu /></Button>
              <Button variant="ghost" size="icon" className="hidden lg:inline-flex" onClick={() => setCollapsed(!collapsed)} aria-label="Collapse sidebar"><PanelLeft /></Button>
              <div className="hidden items-center gap-2 text-sm md:flex">
                <span className="text-muted-foreground">Workspace</span>
                <ChevronRight className="size-3 text-muted-foreground" />
                <span className="font-medium">Acme Corp - Prod</span>
                <ChevronDown className="size-3 text-muted-foreground" />
              </div>
            </div>
            <div className="flex items-center gap-2">
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
              <div className="hidden items-center gap-2 border-l border-white/10 pl-3 text-xs text-muted-foreground md:flex">
                <span className={`size-1.5 rounded-full ${connectionAccessMode === 'limited' ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                {connectionAccessMode === 'limited' ? 'Limited access / sample inventory' : 'Live Dynamic Data'}
              </div>
              <Button variant="ghost" size="icon" onClick={fetchData} aria-label="Refresh data">
                <RefreshCw className={syncing ? 'animate-spin' : ''} />
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setLight(!light)} aria-label="Toggle theme">
                {light ? <Moon /> : <Sun />}
              </Button>
              <Button size="sm" onClick={() => setConnectOpen(true)} className="bg-cyan-400 text-slate-950 hover:bg-cyan-300">
                <Plus data-icon="inline-start" />Connect Account
              </Button>
            </div>
          </header>

          <div className="p-4 lg:p-8">
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
                        <div className="text-sm font-medium text-amber-100">Learner Lab limited mode</div>
                        <p className="mt-1 text-sm text-amber-100/80">
                          {connectionWarning || 'AWS is connected, but live EC2 discovery is denied in this Learner Lab. Inventory and reports will use notebook or seeded fallback data where needed, and the account stays saved for refreshes.'}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                )}
                {connectionAccessMode !== 'limited' && (loadedDataSources.length > 0 || failedDataSources.length > 0 || dataError) && (
                  <Card className="mb-6 border-white/8 bg-card/70">
                    <CardContent className="flex flex-col gap-4 p-5">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium">Current data coverage</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {loadedDataSources.length} data sources ready{failedDataSources.length ? ` · ${failedDataSources.length} unavailable` : ''}{connectionAccessMode === 'limited' ? ' · notebook fallback active' : ''}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span className={`size-2 rounded-full ${syncing ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                          {syncing ? 'Refreshing' : connectionAccessMode === 'limited' ? 'Fallback synced' : 'Synced'}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {loadedDataSources.map(source => (
                          <Badge key={source.key} className="bg-emerald-400/10 text-emerald-300 hover:bg-emerald-400/10">
                            {source.label}
                          </Badge>
                        ))}
                        {failedDataSources.map(source => (
                          <Badge key={source.key} variant="outline" className="border-amber-400/30 text-amber-300">
                            {source.label} unavailable
                          </Badge>
                        ))}
                      </div>
                      {dataError && (
                        <div className="rounded-lg border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
                          {dataError}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
                {view === 'overview' && (
                  <Overview
                    accessMode={connectionAccessMode}
                    setView={setView}
                    spend={spend}
                    alerts={alerts}
                    summary={summary}
                    currency={currency}
                    sectionStatus={dataSources.summary?.status || 'idle'}
                  />
                )}
                {view === 'inventory' && (
                  <Inventory
                    accessMode={connectionAccessMode}
                    search={search}
                    setSearch={setSearch}
                    status={status}
                    setStatus={setStatus}
                    filteredNodes={filteredNodes}
                    setSelectedNode={setSelectedNode}
                    sectionStatus={dataSources.nodes?.status || 'idle'}
                  />
                )}
                {view === 'telemetry' && (
                  <Telemetry
                    accessMode={connectionAccessMode}
                    telemetry={telemetry}
                    timeframe={timeframe}
                    setTimeframe={setTimeframe}
                    sectionStatus={dataSources.telemetry?.status || 'idle'}
                  />
                )}
                {view === 'security' && (
                  <Security
                    accessMode={connectionAccessMode}
                    tab={securityTab}
                    setTab={setSecurityTab}
                    summary={summary}
                    audit={securityAudit}
                    sectionStatus={dataSources.security?.status || 'idle'}
                  />
                )}
                {view === 'optimization' && (
                  <Optimization
                    accessMode={connectionAccessMode}
                    items={optimizations}
                    applied={applied}
                    setApplied={setApplied}
                    currency={currency}
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
                )}
                {view === 'copilot' && (
                  <CopilotView apiUrl={apiUrl} />
                )}
                {view === 'settings' && (
                  <SettingsView
                    connectionState={connectionState}
                    connectedAccounts={connectedAccounts}
                    rememberedProfile={rememberedProfile}
                    onSwitchAccount={switchAccount}
                    selectedAccountKey={selectedAccountKey}
                  />
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



function Overview({ accessMode, setView, spend, alerts, summary, sectionStatus, currency = 'USD' }: any) {
  const totalSpend = summary?.monthly_spend ?? 0;
  const activeNodes = summary?.running_nodes ?? 0;
  const totalNodes = summary?.total_nodes ?? 0;
  const wastedSpend = summary?.wasted_monthly_spend ?? 0;
  const criticalRisks = summary?.critical_security_risks ?? 0;
  const lastSynced = summary?.last_synced ? new Date(summary.last_synced).toLocaleString() : 'Just now';
  const summaryMode = accessMode === 'limited' ? 'Notebook fallback' : summary?.partial ? 'Partial data' : 'Live data';

  return (
    <>
      <SectionTitle
        eyebrow="Executive overview"
        title="Your cloud, at a glance."
        description="A unified operational view across connected providers."
        status={<SectionStatusBadge status={sectionStatus} />}
        action={
          <Button variant="outline" onClick={() => setView('optimization')}>
            <Sparkles data-icon="inline-start" />View savings opportunities
          </Button>
        }
      />
    
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={CircleDollarSign} label={`Total monthly spend (${currency})`} value={formatCurrency(totalSpend, currency)} detail={`Last synced ${lastSynced}`} tone="cyan" trend="Live" />
        <MetricCard icon={Cpu} label="Active compute nodes" value={formatInteger(activeNodes)} detail={`${formatInteger(Math.max(totalNodes - activeNodes, 0))} stopped · ${formatInteger(totalNodes)} total`} tone="emerald" />
        <MetricCard icon={ArrowDownRight} label={`Monthly wasted spend (${currency})`} value={formatCurrency(wastedSpend, currency)} detail="Actionable savings" tone="amber" />
        <MetricCard icon={ShieldAlert} label="Critical security risks" value={formatInteger(criticalRisks)} detail="Exposure alerts from the backend" tone="red" />
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card className="border-white/8 bg-card/70">
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base">30-day spend by provider</CardTitle>
              <p className="mt-1 text-xs text-muted-foreground">Daily run-rate · USD thousands</p>
            </div>
            <Badge variant="outline" className="border-white/10 text-muted-foreground">{summaryMode}</Badge>
          </CardHeader>
          <CardContent className="h-72">
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
                <XAxis dataKey="day" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="aws" name="AWS" stackId="1" stroke="var(--chart-1)" fill="url(#aws)" />
                <Area type="monotone" dataKey="gcp" name="GCP" stackId="1" stroke="var(--chart-2)" fill="url(#gcp)" />
                <Area type="monotone" dataKey="azure" name="Azure" stackId="1" stroke="var(--chart-3)" fill="var(--chart-3)" fillOpacity={.16} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardHeader>
            <CardTitle className="text-base">Quick alerts</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">Items needing your attention</p>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
  {(Array.isArray(alerts) ? alerts : []).map((alert: any, idx: number) => (
    <div key={alert.id || alert.title || idx} className="flex items-start gap-3 rounded-lg border border-white/8 bg-white/[.03] p-3">
      <div className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-${alert.tone || 'amber'}-400/10 text-${alert.tone || 'amber'}-400`}>
        <AlertTriangle className="size-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{alert.title || 'Untitled Alert'}</div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">{alert.desc || alert.description || ''}</div>
      </div>
      {alert.tag && (
        <Badge variant="outline" className="border-white/10 text-[10px]">{alert.tag}</Badge>
      )}
    </div>
  ))}
</CardContent>
        </Card>

      </div>
    </>
  )
}

function Inventory({ accessMode, search, setSearch, status, setStatus, filteredNodes, setSelectedNode, sectionStatus }: any) {
  return (
    <>
      <SectionTitle
        eyebrow="Inventory"
        title="Compute & storage"
        description={accessMode === 'limited' ? 'Track fallback inventory from the notebook pipeline while live EC2 discovery is blocked.' : 'Track every node, volume, and exposure across your estate.'}
        status={<SectionStatusBadge status={sectionStatus} />}
        action={<Button variant="outline"><Archive data-icon="inline-start" />{accessMode === 'limited' ? 'Export fallback inventory' : 'Export inventory'}</Button>}
      />
      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative min-w-64 flex-1">
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search instances, IDs, IPs..." className="border-white/10 bg-white/5 pl-9" />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-36 border-white/10 bg-white/5">
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
        description={accessMode === 'limited' ? 'Telemetry is shown from cached or notebook-generated data when live CloudWatch access is unavailable.' : 'Real-time health signals from active nodes.'}
        status={<SectionStatusBadge status={sectionStatus} />}
        action={
          <div className="flex items-center gap-2">
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
              <ResponsiveContainer width="100%" height="100%">
                {kind === 'bar' ? (
                  <BarChart data={telemetry}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.12)" vertical={false} />
                    <XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="read" fill="var(--chart-1)" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="write" fill="var(--chart-2)" radius={[3, 3, 0, 0]} />
                  </BarChart>
                ) : (
                  <LineChart data={telemetry}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.12)" vertical={false} />
                    <XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
                    <Tooltip content={<ChartTooltip />} />
                    {key === 'cpu' && <ReferenceLine y={80} stroke="var(--destructive)" strokeDasharray="4 4" />}
                    <Line type="monotone" dataKey={key === 'network' ? 'netIn' : key} stroke="var(--chart-1)" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey={key === 'network' ? 'netOut' : undefined} stroke="var(--chart-2)" strokeWidth={2} dot={false} />
                  </LineChart>
                )}
              </ResponsiveContainer>
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
        description={accessMode === 'limited' ? 'Security findings are based on fallback inventory because live discovery is denied in this Learner Lab.' : 'Resolve public attack surface and unmanaged resources.'}
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
        <TabsList className="mb-4 bg-white/5">
          <TabsTrigger value="groups">Security groups</TabsTrigger>
          <TabsTrigger value="ips">Elastic IPs & NAT</TabsTrigger>
          <TabsTrigger value="logs">CloudWatch logs</TabsTrigger>
        </TabsList>
        <TabsContent value="groups">
          <Card className="border-white/8 bg-card/70">
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
          </Card>
        </TabsContent>
        <TabsContent value="ips">
          <Card className="border-white/8 bg-card/70">
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

function Optimization({ accessMode, items = [], applied, setApplied, sectionStatus, currency = 'USD' }: any) {
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

  return (
    <>
      <SectionTitle
        eyebrow="Optimization engine"
        title="Make every cloud dollar count."
        description={accessMode === 'limited' ? 'Savings recommendations are generated from the fallback notebook inventory.' : 'Prioritized recommendations based on usage, pricing, and risk signals.'}
        status={<SectionStatusBadge status={sectionStatus} />}
        action={
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
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
          {formatInteger(items.length)} {accessMode === 'limited' ? 'fallback recommendations' : 'live recommendations'}
        </span>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
          {formatCurrency(items.reduce((sum: number, item: any) => sum + Number(item.savings ?? 0), 0), currency)} potential savings
        </span>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
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
                <div className="mt-5 flex items-center justify-between">
                  <div>
                    <div className="text-xl font-semibold text-emerald-300">Saves {formatCurrency(Number(item.savings ?? 0), currency)}/mo</div>
                  </div>
                  <Button size="sm" variant={done ? 'secondary' : 'outline'} onClick={() => toggleOptimization(item.id)}>
                    {done ? <><Check data-icon="inline-start" />Applied</> : 'Review'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </>
  )
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

function SettingsView({ connectionState, connectedAccounts, rememberedProfile, onSwitchAccount, selectedAccountKey }: any) {
  const [orgName, setOrgName] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadSettings = async () => {
      try {
        const res = await fetch(apiUrl('/api/settings'));
        const data = await res.json();
        if (!cancelled) {
          setOrgName(data?.organization || '');
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
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(apiUrl('/api/settings'), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ orgName })
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <SectionTitle eyebrow="Workspace settings" title="Settings & API keys" description="Manage organization access and provider connections." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-white/8 bg-card/70">
          <CardHeader><CardTitle className="text-base">Organization profile</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="text-xs text-muted-foreground">
              {loaded ? 'Loaded from backend settings.' : 'Loading settings...'}
            </div>
            <label className="text-sm">
              Organization name
              <Input value={orgName} onChange={e => setOrgName(e.target.value)} className="mt-2 border-white/10 bg-white/5" />
            </label>
            <Button className="w-fit bg-cyan-400 text-slate-950 hover:bg-cyan-300" onClick={handleSave} disabled={saving || !loaded}>
              {saving ? 'Saving...' : 'Save changes'}
            </Button>
          </CardContent>
        </Card>
        <Card className="border-white/8 bg-card/70">
          <CardHeader>
            <CardTitle className="text-base">Connected AWS profiles</CardTitle>
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
      <DialogContent className="border-white/10 bg-card sm:max-w-lg">
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
