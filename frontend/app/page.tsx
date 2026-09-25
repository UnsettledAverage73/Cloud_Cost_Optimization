'use client'

import { useMemo, useState, useEffect, useCallback, useDeferredValue, memo, useRef } from 'react'
import {
  Activity, AlertTriangle, Archive, ArrowDownRight, ArrowUpRight, BarChart3, Bell, Bot, Calendar, Check,
  CheckCircle2, AlertCircle, ChevronDown, ChevronLeft, ChevronRight, CircleDollarSign, Cloud, CloudCog, Copy, Cpu, Database,
  Download, ExternalLink, Eye, FileCode, FileText, GitBranch, GitPullRequest, HardDrive, History, Inbox, LayoutDashboard,
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
import { MetricCard, SectionTitle, SectionStatusBadge, getSectionStatusLabel, Ec2MonitoringGrid, InstanceDetailDrawer } from '@/components/dashboard'
import { useOptimisticToast } from '@/components/ui/optimistic-toast'
import { validateForm, enrollAccountSchema, connectCloudSchema } from '@/lib/validations/forms'
import { addBreadcrumb, captureException } from '@/lib/monitoring/logger'
import type {
  SyncState,
  AccessMode,
  Currency,
  CloudProvider,
  Timeframe,
  ViewType,
  ComputeNode,
  TelemetryPoint,
  SpendPoint,
  CloudAlert,
  OptimizationRecommendation,
  SecurityAudit,
  DashboardSummary,
  ConnectionState,
  ConnectedAccount,
  CloudProfile,
} from '@/types/dashboard'
import { useDashboardStore } from '@/stores/useDashboardStore'

// Base URL for CloudPulse Backend (Render Web Service or local)
import dynamic from 'next/dynamic'
import { ConnectModal } from '@/components/dashboard/modals/ConnectModal'
import { CommandPaletteModal } from '@/components/dashboard/modals/CommandPaletteModal'

const OverviewView = dynamic(() => import('@/components/dashboard/views/OverviewView'), {
  loading: () => <MetricCardSkeleton />,
  ssr: false,
})
const InventoryView = dynamic(() => import('@/components/dashboard/views/InventoryView'), {
  loading: () => <TableSkeleton rows={8} />,
  ssr: false,
})
const TelemetryView = dynamic(() => import('@/components/dashboard/views/TelemetryView'), {
  loading: () => <ChartSkeleton height="h-64" />,
  ssr: false,
})
const SecurityView = dynamic(() => import('@/components/dashboard/views/SecurityView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const OptimizationView = dynamic(() => import('@/components/dashboard/views/OptimizationView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const SchedulerPrewarmView = dynamic(() => import('@/components/dashboard/views/SchedulerPrewarmView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const GitOpsSlaView = dynamic(() => import('@/components/dashboard/views/GitOpsSlaView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const FleetView = dynamic(() => import('@/components/dashboard/views/FleetView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const CiCdGuardrailView = dynamic(() => import('@/components/dashboard/views/CiCdGuardrailView'), {
  loading: () => <TableSkeleton rows={6} />,
  ssr: false,
})
const CopilotView = dynamic(() => import('@/components/dashboard/views/CopilotView'), {
  loading: () => <div className="py-20 text-center text-xs text-muted-foreground">Loading FinOps Copilot...</div>,
  ssr: false,
})
const SettingsView = dynamic(() => import('@/components/dashboard/views/SettingsView'), {
  loading: () => <div className="py-20 text-center text-xs text-muted-foreground">Loading Settings...</div>,
  ssr: false,
})

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
  { id: 'copilot', label: 'AI FinOps Copilot', icon: Sparkles },
  { id: 'settings', label: 'Settings & Notifications', icon: Settings },
]


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
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  const {
    view, setView,
    collapsed, setCollapsed,
    mobileNavOpen, setMobileNavOpen,
    provider, setProvider,
    currency, setCurrency,
    light, setLight,
    connectOpen, setConnectOpen,
    connectionState, setConnectionState,
    connectedAccounts, setConnectedAccounts,
    rememberedProfile, setRememberedProfile,
    selectedAccountKey, setSelectedAccountKey,
    connectionReady, setConnectionReady,
    dataSources, updateDataSource,
    selectedNode, setSelectedNode,
    selectedNodeDetail, setSelectedNodeDetail,
    selectedNodeTelemetry, setSelectedNodeTelemetry,
    selectedNodeLoading, setSelectedNodeLoading,
    search, setSearch,
    status, setStatus,
    securityTab, setSecurityTab,
    timeframe, setTimeframe,
    syncing, setSyncing,
    applied, setApplied,
    nodes, setNodes,
    telemetry, setTelemetry,
    spend, setSpend,
    alerts, setAlerts,
    optimizations, setOptimizations,
    securityAudit, setSecurityAudit,
    revokeSecurityGroupLocally,
    summary, setSummary,
    loading, setLoading,
    dataError, setDataError,
    fetchData: storeFetchData,
    autoRefresh,
    toggleAutoRefresh,
    autoRefreshIntervalSec,
    disconnectAccount,
  } = useDashboardStore();

  const { toast } = useOptimisticToast();

  const connectionAccessMode = connectionState?.access_mode || 'live';
  const connectionWarning = connectionState?.warning || '';

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
  }, [setConnectionState, setConnectedAccounts, setRememberedProfile]);

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
    setSelectedAccountKey,
  ]);

  // Core Data Fetching Handler with caching
  const fetchData = useCallback(async (force = false) => {
    await storeFetchData(apiUrl, force);
  }, [storeFetchData, apiUrl]);

  const [revokingDrawerSg, setRevokingDrawerSg] = useState<string | null>(null);
  const [drawerFeedback, setDrawerFeedback] = useState<string | null>(null);

  const handleDrawerRevoke = useCallback(async (sg: any) => {
    if (!sg?.group_id) return;
    const targetId = sg.group_id;
    const targetName = sg.group_name || targetId;
    setRevokingDrawerSg(targetId);
    setDrawerFeedback(null);

    // Instant optimistic update
    revokeSecurityGroupLocally?.(targetId);
    setDrawerFeedback(`Optimistically revoked public ingress for ${targetName}.`);
    toast({
      title: 'Security Ingress Revoked',
      description: `Closed public 0.0.0.0/0 exposure on ${targetName}. Dispatched rule deletion to AWS.`,
      type: 'security'
    });

    try {
      const endpoint = apiUrl ? apiUrl('/api/security/revoke') : '/api/security/revoke';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ groupId: targetId, groupName: targetName })
      });
      if (res.ok) {
        await storeFetchData(apiUrl, true);
      } else {
        const err = await res.json().catch(() => ({}));
        setDrawerFeedback(`Revocation error: ${err.detail || 'Failed to revoke'}`);
        toast({
          title: 'Revocation Failed',
          description: err.detail || 'Failed to revoke security group on provider.',
          type: 'error'
        });
      }
    } catch (e: any) {
      setDrawerFeedback(`Error: ${e?.message || 'Network error'}`);
      toast({
        title: 'Network Sync Error',
        description: e?.message || 'Network error while contacting CloudPulse backend.',
        type: 'error'
      });
    } finally {
      setRevokingDrawerSg(null);
    }
  }, [apiUrl, revokeSecurityGroupLocally, storeFetchData, toast]);

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
          if (fallback?.connected) {
            setConnectionState({
              connected: true,
              status: fallback.status || 'success',
              message: fallback.message || 'Saved Account Restored',
              provider: fallback.provider,
              account_name: fallback.account_name,
              region: fallback.region,
              role_arn: fallback.role_arn,
              access_mode: fallback.access_mode || 'live',
              warning: fallback.warning || '',
            });
            setConnectedAccounts(Array.isArray(fallback.connected_accounts) ? fallback.connected_accounts : []);
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
              message: fallback.message || 'Saved Account Restored',
              provider: fallback.provider,
              account_name: fallback.account_name,
              region: fallback.region,
              role_arn: fallback.role_arn,
              access_mode: fallback.access_mode || 'live',
              warning: fallback.warning || '',
            });
            setConnectedAccounts(Array.isArray(fallback.connected_accounts) ? fallback.connected_accounts : []);
            setRememberedProfile(profile);
          }
        }
      } finally {
        if (!cancelled) {
          setConnectionReady(true);
          const activeConn = readStoredConnection();
          if (activeConn?.connected) {
            storeFetchData(apiUrl);
          }
        }
      }
    };

    syncConnectionState();

    return () => {
      cancelled = true;
    };
  }, [apiUrl, storeFetchData, setConnectionReady, setConnectionState, setConnectedAccounts, setRememberedProfile]);

  useEffect(() => {
    if (!connectionState?.connected || !autoRefresh) return;

    const intervalMs = (autoRefreshIntervalSec || 60) * 1000;
    const interval = window.setInterval(() => {
      fetchData();
    }, intervalMs);

    return () => window.clearInterval(interval);
  }, [connectionState?.connected, autoRefresh, autoRefreshIntervalSec, fetchData]);

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

  const deferredSearch = useDeferredValue(search);
  const filteredNodes = useMemo(() => {
    if (!Array.isArray(nodes)) return [];
    const q = (deferredSearch || '').toLowerCase();
    return nodes.filter(n =>
      ((n?.name || '') + (n?.instance_id || '')).toLowerCase().includes(q) &&
      (status === 'all' || n?.state === status)
    );
  }, [nodes, deferredSearch, status]);

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
          <div className="flex flex-1 flex-col gap-1 p-3 overflow-y-auto">
            {nav.map(item => {
              const Icon = item.icon;
              const isActive = view === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setView(item.id)}
                  className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-all duration-150 ${
                    isActive
                      ? 'bg-gradient-to-r from-cyan-500/15 via-cyan-500/8 to-transparent border border-cyan-500/25 text-cyan-300 font-medium shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]'
                      : 'text-muted-foreground/90 hover:bg-white/[0.04] hover:text-foreground hover:translate-x-0.5'
                  }`}
                >
                  {isActive && (
                    <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
                  )}
                  <Icon className={`size-4 shrink-0 transition-transform duration-150 ${isActive ? 'text-cyan-400 scale-105' : 'group-hover:scale-105'}`} />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                  {item.id === 'security' && !collapsed && (
                    <span className="ml-auto flex size-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                      <span className="relative inline-flex rounded-full size-2 bg-red-500" />
                    </span>
                  )}
                </button>
              )
            })}
          </div>
          {!collapsed && (
            <div className="border-t border-white/8 p-3">
              <div className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="relative flex size-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full size-2 bg-emerald-400" />
                  </span>
                  <span className="text-[11px] text-muted-foreground font-medium">FinOps Core</span>
                </div>
                <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">Active</span>
              </div>
            </div>
          )}
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
          <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-2 sm:gap-4 border-b border-white/[0.08] bg-background/80 px-3 sm:px-4 backdrop-blur-xl lg:px-8 shadow-xs">
            {syncing && (
              <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-cyan-500 via-indigo-500 to-cyan-400 animate-pulse z-30" />
            )}
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
              <div className="hidden items-center gap-2 text-sm md:flex min-w-0 max-w-[200px]">
                <span className="text-muted-foreground shrink-0">Workspace</span>
                <ChevronRight className="size-3 text-muted-foreground shrink-0" />
                <span className="font-medium truncate">{connectionState?.account_name || 'Production Fleet'}</span>
              </div>
            </div>
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <div className={`hidden items-center gap-2 rounded-full border px-3 py-1 text-xs md:flex shrink-0 ${connectionState?.connected ? (connectionAccessMode === 'limited' ? 'border-amber-400/30 bg-amber-400/10 text-amber-300' : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300 shadow-[0_0_12px_-2px_rgba(16,185,129,0.3)]') : 'border-white/10 bg-white/5 text-muted-foreground'}`}>
                <span className="relative flex size-2">
                  {connectionState?.connected && (
                    <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${connectionAccessMode === 'limited' ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                  )}
                  <span className={`relative inline-flex rounded-full size-2 ${connectionState?.connected ? (connectionAccessMode === 'limited' ? 'bg-amber-400' : 'bg-emerald-400') : 'bg-slate-500'}`} />
                </span>
                {connectionState?.connected
                  ? (connectionAccessMode === 'limited'
                    ? `Limited access · ${connectionState?.provider || 'AWS'}`
                    : `Live Telemetry · ${connectionState?.provider || 'AWS'}`)
                  : 'Not connected'}
              </div>
              {connectionState?.connected && (
                <Select
                  value={selectedAccountKey || connectionKey(connectionState)}
                  onValueChange={(value) => {
                    if (value === '__disconnect__') {
                      disconnectAccount();
                      toast({
                        title: 'Account Disconnected',
                        description: 'Removed cloud credentials from active session.',
                        type: 'warning'
                      });
                      return;
                    }
                    const accounts = Array.isArray(connectedAccounts) && connectedAccounts.length > 0 ? connectedAccounts : [connectionState];
                    const next = accounts.find((account: any) => connectionKey(account) === value);
                    if (next) {
                      switchAccount(next);
                      toast({
                        title: 'Switched Account',
                        description: `Now monitoring ${next.account_name || 'account'} (${next.region || 'us-east-1'}).`,
                        type: 'info'
                      });
                    }
                  }}
                >
                  <SelectTrigger className="hidden h-9 max-w-[200px] border-white/10 bg-white/5 sm:flex">
                    <span className="truncate text-xs font-medium">
                      {(() => {
                        const accounts = Array.isArray(connectedAccounts) && connectedAccounts.length > 0 ? connectedAccounts : [connectionState];
                        const matched = accounts.find((a: any) => connectionKey(a) === (selectedAccountKey || connectionKey(connectionState)));
                        if (matched?.account_name) {
                          return `${matched.account_name} (${matched.region || 'us-east-1'})`;
                        }
                        if (connectionState?.account_name) {
                          return `${connectionState.account_name} (${connectionState.region || 'us-east-1'})`;
                        }
                        return 'Connected AWS';
                      })()}
                    </span>
                  </SelectTrigger>
                  <SelectContent>
                    {(Array.isArray(connectedAccounts) && connectedAccounts.length > 0 ? connectedAccounts : [connectionState]).map((account: any) => (
                      <SelectItem key={connectionKey(account)} value={connectionKey(account)}>
                        {account?.account_name || 'Connected account'} · {account?.region || 'us-east-1'}{account?.active ? ' · Active' : ''}
                      </SelectItem>
                    ))}
                    <SelectItem value="__disconnect__" className="text-red-400 focus:text-red-300">
                      Disconnect Account
                    </SelectItem>
                  </SelectContent>
                </Select>
              )}
              <Select value={provider} onValueChange={(value) => {
                const next = value ?? 'all';
                setProvider(next);
                toast({
                  title: `Provider Filter: ${next.toUpperCase()}`,
                  description: next === 'all' ? 'Displaying resources across all active cloud accounts.' : `Filtered views to ${next.toUpperCase()} infrastructure.`,
                  type: 'info'
                });
              }}>
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
              <Select value={currency} onValueChange={(value) => {
                const next = (value as 'USD' | 'INR') || 'USD';
                setCurrency(next);
                toast({
                  title: `Currency: ${next}`,
                  description: next === 'INR' ? 'Recalculated all fleet costs and savings to INR (₹ Lakhs / Crores).' : 'Recalculated all fleet costs and savings to USD ($).',
                  type: 'info'
                });
              }}>
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
                onClick={() => {
                  const next = currency === 'USD' ? 'INR' : 'USD';
                  setCurrency(next);
                  toast({
                    title: `Currency: ${next}`,
                    description: `Active display currency changed to ${next}.`,
                    type: 'info'
                  });
                }}
                title="Toggle Currency"
              >
                {currency === 'USD' ? '$' : '₹'}
              </Button>
              <Button
                variant={autoRefresh ? "secondary" : "ghost"}
                size="sm"
                onClick={() => {
                  toggleAutoRefresh();
                  toast({
                    title: !autoRefresh ? 'Autonomous Live Sync Active' : 'Auto-Sync Paused',
                    description: !autoRefresh ? 'Sub-minute autonomous telemetry streaming engaged.' : 'Switched to manual sync mode.',
                    type: !autoRefresh ? 'success' : 'info'
                  });
                }}
                title={autoRefresh ? "Auto-refresh is active (every 60s). Click to pause." : "Auto-refresh is paused. Click to enable."}
                className={`h-8 px-2 text-xs font-medium border border-white/10 transition-all ${autoRefresh ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.2)]' : 'text-muted-foreground hover:text-foreground'}`}
              >
                <span className={`mr-1.5 size-1.5 rounded-full ${autoRefresh ? 'bg-cyan-400 animate-pulse' : 'bg-slate-500'}`} />
                <span className="hidden lg:inline">{autoRefresh ? 'Auto-sync ON' : 'Auto-sync OFF'}</span>
                <span className="lg:hidden">{autoRefresh ? 'Auto' : 'Manual'}</span>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  fetchData(true);
                  toast({
                    title: 'Syncing Multi-Cloud Telemetry',
                    description: 'Querying AWS CloudWatch, hypervisors, and telemetry ring buffers...',
                    type: 'info'
                  });
                }}
                aria-label="Refresh data"
                className="size-8 sm:size-9"
                title="Manual refresh"
              >
                <RefreshCw className={`size-4 ${syncing ? 'animate-spin text-cyan-400' : ''}`} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setLight(!light);
                  toast({
                    title: light ? 'Dark Theme Active' : 'Light Theme Active',
                    description: 'Workspace palette updated.',
                    type: 'info'
                  });
                }}
                aria-label="Toggle theme"
                className="size-8 sm:size-9"
              >
                {light ? <Moon className="size-4" /> : <Sun className="size-4 text-amber-400" />}
              </Button>
              <Button size="sm" onClick={() => setConnectOpen(true)} className="h-8 sm:h-9 bg-cyan-400 text-slate-950 hover:bg-cyan-300 px-2.5 sm:px-3 text-xs sm:text-sm font-medium shadow-[0_0_15px_-2px_rgba(6,182,212,0.3)]">
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
                    <OverviewView
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
                    <InventoryView
                      accessMode={connectionAccessMode}
                      search={search}
                      setSearch={setSearch}
                      status={status}
                      setStatus={setStatus}
                      filteredNodes={filteredNodes}
                      setSelectedNode={setSelectedNode}
                      sectionStatus={dataSources.nodes?.status || (syncing ? 'loading' : 'idle')}
                      apiUrl={apiUrl}
                      currency={currency}
                    />
                  </SectionErrorBoundary>
                )}
                {view === 'telemetry' && (
                  <SectionErrorBoundary title="Telemetry Analytics">
                    <TelemetryView
                      accessMode={connectionAccessMode}
                      telemetry={telemetry}
                      timeframe={timeframe}
                      setTimeframe={setTimeframe}
                      sectionStatus={dataSources.telemetry?.status || (syncing ? 'loading' : 'idle')}
                      nodes={nodes}
                      apiUrl={apiUrl}
                    />
                  </SectionErrorBoundary>
                )}
                {view === 'security' && (
                  <SectionErrorBoundary title="Security Center">
                    <SecurityView
                      accessMode={connectionAccessMode}
                      tab={securityTab}
                      setTab={setSecurityTab}
                      summary={summary}
                      audit={securityAudit}
                      sectionStatus={dataSources.security?.status || (syncing ? 'loading' : 'idle')}
                      apiUrl={apiUrl}
                      onRefresh={fetchData}
                      revokeSecurityGroupLocally={revokeSecurityGroupLocally}
                    />
                  </SectionErrorBoundary>
                )}
                {view === 'optimization' && (
                  <SectionErrorBoundary title="Cost Optimization">
                    <OptimizationView
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
                      nodes={nodes}
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
                      nodes={nodes}
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
      <InstanceDetailDrawer
        open={Boolean(selectedNode)}
        onOpenChange={(isOpen) => {
          if (!isOpen) {
            setSelectedNode(null);
            setSelectedNodeDetail(null);
            setSelectedNodeTelemetry([]);
          }
        }}
        node={selectedNode}
        nodeDetail={selectedNodeDetail}
        loading={selectedNodeLoading}
        currency={currency}
        rate={84.0}
        apiUrl={apiUrl}
        formatCurrency={formatCurrency}
        onRevokeSg={handleDrawerRevoke}
        onOpenFullTelemetry={(instId) => {
          setSelectedNode(null);
          setSelectedNodeDetail(null);
          setSelectedNodeTelemetry([]);
          setView('telemetry');
        }}
      />
      <ConnectModal
        open={connectOpen}
        onOpenChange={setConnectOpen}
        initialProfile={rememberedProfile}
        apiUrl={apiUrl}
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
      <CommandPaletteModal
        open={commandPaletteOpen}
        onOpenChange={setCommandPaletteOpen}
        currentView={view}
        onSelectView={setView}
        nodes={nodes}
        onSelectNode={(node) => setSelectedNode(node)}
        onToggleCurrency={() => {
          const next = currency === 'USD' ? 'INR' : 'USD';
          setCurrency(next);
          toast({
            title: `Currency: ${next}`,
            description: `Active display currency changed to ${next}.`,
            type: 'info'
          });
        }}
        currency={currency}
      />
    </div>
  )
}