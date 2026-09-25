import { create } from 'zustand'
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
  DataSourceCoverage,
} from '@/types/dashboard'

export const PROFILE_STORAGE_KEY = 'cloudpulse_remembered_profile'
export const CONNECTION_STORAGE_KEY = 'cloudpulse_connection'
export const AUTOREFRESH_STORAGE_KEY = 'cloudpulse_auto_refresh'

export function getStoredConnection(): ConnectionState | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(CONNECTION_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') {
      return {
        connected: Boolean(parsed.connected),
        status: parsed.status || (parsed.connected ? 'success' : 'disconnected'),
        message: parsed.message || '',
        provider: parsed.provider,
        account_name: parsed.account_name,
        region: parsed.region,
        role_arn: parsed.role_arn,
        access_mode: parsed.access_mode || 'live',
        warning: parsed.warning || '',
      }
    }
  } catch {
    // ignore parsing failure
  }
  return null
}

export function getStoredAccounts(): ConnectedAccount[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(CONNECTION_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed?.connected_accounts) ? parsed.connected_accounts : []
  } catch {
    return []
  }
}

export function getStoredProfile(): CloudProfile | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function getStoredAutoRefresh(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const raw = window.localStorage.getItem(AUTOREFRESH_STORAGE_KEY)
    return raw === 'true'
  } catch {
    return false
  }
}

export interface DashboardStoreState {
  // Navigation & UI Layout
  view: ViewType
  setView: (view: ViewType) => void
  collapsed: boolean
  setCollapsed: (collapsed: boolean) => void
  mobileNavOpen: boolean
  setMobileNavOpen: (open: boolean) => void
  light: boolean
  setLight: (light: boolean) => void
  connectOpen: boolean
  setConnectOpen: (open: boolean) => void

  // Auto-Refresh & Background Polling Controls
  autoRefresh: boolean
  setAutoRefresh: (autoRefresh: boolean) => void
  toggleAutoRefresh: () => void
  autoRefreshIntervalSec: number
  setAutoRefreshIntervalSec: (interval: number) => void

  // Filters & Controls
  provider: CloudProvider
  setProvider: (provider: CloudProvider) => void
  currency: Currency
  setCurrency: (currency: Currency) => void
  search: string
  setSearch: (search: string) => void
  status: string
  setStatus: (status: string) => void
  securityTab: string
  setSecurityTab: (tab: string) => void
  timeframe: Timeframe
  setTimeframe: (timeframe: Timeframe) => void

  // Connection & Auth
  connectionState: ConnectionState
  setConnectionState: (state: ConnectionState | ((prev: ConnectionState) => ConnectionState)) => void
  connectedAccounts: ConnectedAccount[]
  setConnectedAccounts: (accounts: ConnectedAccount[]) => void
  rememberedProfile: CloudProfile | null
  setRememberedProfile: (profile: CloudProfile | null) => void
  selectedAccountKey: string
  setSelectedAccountKey: (key: string) => void
  connectionReady: boolean
  setConnectionReady: (ready: boolean) => void
  disconnectAccount: () => void

  // Cloud Data & Metrics
  summary: DashboardSummary | null
  setSummary: (summary: DashboardSummary | null) => void
  nodes: ComputeNode[]
  setNodes: (nodes: ComputeNode[]) => void
  telemetry: TelemetryPoint[]
  setTelemetry: (telemetry: TelemetryPoint[]) => void
  spend: SpendPoint[]
  setSpend: (spend: SpendPoint[]) => void
  alerts: CloudAlert[]
  setAlerts: (alerts: CloudAlert[]) => void
  optimizations: OptimizationRecommendation[]
  setOptimizations: (optimizations: OptimizationRecommendation[]) => void
  securityAudit: SecurityAudit | null
  setSecurityAudit: (audit: SecurityAudit | null) => void
  applied: string[]
  setApplied: (applied: string[] | ((prev: string[]) => string[])) => void

  // Selected Node Details
  selectedNode: ComputeNode | null
  setSelectedNode: (node: ComputeNode | null) => void
  selectedNodeDetail: any
  setSelectedNodeDetail: (detail: any) => void
  selectedNodeTelemetry: any[]
  setSelectedNodeTelemetry: (telemetry: any[]) => void
  selectedNodeLoading: boolean
  setSelectedNodeLoading: (loading: boolean) => void

  // Data Source & Sync State
  dataSources: DataSourceCoverage
  updateDataSource: (key: string, patch: { status: SyncState; error?: string }) => void
  syncing: boolean
  setSyncing: (syncing: boolean) => void
  loading: boolean
  setLoading: (loading: boolean) => void
  dataError: string
  setDataError: (err: string) => void

  // Caching mechanism
  lastFetchedAt: number | null
  cacheTtlMs: number
  invalidateCache: () => void
  revokeSecurityGroupLocally: (groupId: string) => void

  // Async Data Fetching & Caching Orchestration
  fetchData: (apiUrl: (path: string) => string, force?: boolean) => Promise<void>
}

const DATA_SOURCE_KEYS = [
  'summary',
  'nodes',
  'telemetry',
  'spend',
  'alerts',
  'optimizations',
  'security',
  'applied',
]

export const useDashboardStore = create<DashboardStoreState>((set, get) => {
  const initialConnection = getStoredConnection()
  const initialAccounts = getStoredAccounts()
  const initialProfile = getStoredProfile()
  const initialAutoRefresh = getStoredAutoRefresh()

  return {
    // Navigation & UI Layout
    view: 'inventory',
    setView: (view) => set({ view }),
    collapsed: false,
    setCollapsed: (collapsed) => set({ collapsed }),
    mobileNavOpen: false,
    setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
    light: false,
    setLight: (light) => set({ light }),
    connectOpen: false,
    setConnectOpen: (connectOpen) => set({ connectOpen }),

    // Auto-Refresh & Background Polling Controls
    autoRefresh: initialAutoRefresh,
    setAutoRefresh: (autoRefresh) => {
      if (typeof window !== 'undefined') {
        try {
          window.localStorage.setItem(AUTOREFRESH_STORAGE_KEY, String(autoRefresh))
        } catch {}
      }
      set({ autoRefresh })
    },
    toggleAutoRefresh: () => {
      const next = !get().autoRefresh
      if (typeof window !== 'undefined') {
        try {
          window.localStorage.setItem(AUTOREFRESH_STORAGE_KEY, String(next))
        } catch {}
      }
      set({ autoRefresh: next })
    },
    autoRefreshIntervalSec: 60,
    setAutoRefreshIntervalSec: (autoRefreshIntervalSec) => set({ autoRefreshIntervalSec }),

    // Filters & Controls
    provider: 'all',
    setProvider: (provider) => {
      set({ provider })
      get().invalidateCache()
    },
    currency: 'USD',
    setCurrency: (currency) => set({ currency }),
    search: '',
    setSearch: (search) => set({ search }),
    status: 'all',
    setStatus: (status) => set({ status }),
    securityTab: 'groups',
    setSecurityTab: (securityTab) => set({ securityTab }),
    timeframe: '24h',
    setTimeframe: (timeframe) => {
      set({ timeframe })
      get().invalidateCache()
    },

    // Connection & Auth
    connectionState: initialConnection || { connected: false, status: 'disconnected', message: '' },
    setConnectionState: (state) =>
      set((prev) => {
        const next = typeof state === 'function' ? state(prev.connectionState) : state
        if (typeof window !== 'undefined' && next) {
          if (next.connected) {
            try {
              const raw = window.localStorage.getItem(CONNECTION_STORAGE_KEY)
              const current = raw ? JSON.parse(raw) : {}
              window.localStorage.setItem(
                CONNECTION_STORAGE_KEY,
                JSON.stringify({
                  ...current,
                  ...next,
                  connected_accounts: prev.connectedAccounts || current.connected_accounts || [],
                })
              )
            } catch {}
          }
        }
        return { connectionState: next }
      }),
    connectedAccounts: initialAccounts || [],
    setConnectedAccounts: (connectedAccounts) =>
      set((prev) => {
        if (typeof window !== 'undefined') {
          try {
            const raw = window.localStorage.getItem(CONNECTION_STORAGE_KEY)
            const current = raw ? JSON.parse(raw) : {}
            window.localStorage.setItem(
              CONNECTION_STORAGE_KEY,
              JSON.stringify({
                ...current,
                connected_accounts: connectedAccounts,
              })
            )
          } catch {}
        }
        return { connectedAccounts }
      }),
    rememberedProfile: initialProfile || null,
    setRememberedProfile: (rememberedProfile) => {
      if (typeof window !== 'undefined' && rememberedProfile) {
        try {
          window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(rememberedProfile))
        } catch {}
      }
      set({ rememberedProfile })
    },
    selectedAccountKey: '',
    setSelectedAccountKey: (selectedAccountKey) => set({ selectedAccountKey }),
    connectionReady: Boolean(initialConnection?.connected),
    setConnectionReady: (connectionReady) => set({ connectionReady }),
    disconnectAccount: () => {
      if (typeof window !== 'undefined') {
        try {
          window.localStorage.removeItem(CONNECTION_STORAGE_KEY)
        } catch {}
      }
      set({
        connectionState: { connected: false, status: 'disconnected', message: '', access_mode: null, warning: null },
        connectedAccounts: [],
        selectedAccountKey: '',
        connectionReady: false,
        summary: null,
        nodes: [],
        telemetry: [],
        spend: [],
        alerts: [],
        optimizations: [],
        securityAudit: null,
        applied: [],
        dataSources: {},
        dataError: 'Account disconnected.',
      })
    },

    // Cloud Data & Metrics
    summary: null,
    setSummary: (summary) => set({ summary }),
    nodes: [],
    setNodes: (nodes) => set({ nodes }),
    telemetry: [],
    setTelemetry: (telemetry) => set({ telemetry }),
    spend: [],
    setSpend: (spend) => set({ spend }),
    alerts: [],
    setAlerts: (alerts) => set({ alerts }),
    optimizations: [],
    setOptimizations: (optimizations) => set({ optimizations }),
    securityAudit: null,
    setSecurityAudit: (securityAudit) => set({ securityAudit }),
    applied: [],
    setApplied: (applied) =>
      set((prev) => ({
        applied: typeof applied === 'function' ? applied(prev.applied) : applied,
      })),

    // Selected Node Details
    selectedNode: null,
    setSelectedNode: (selectedNode) => set({ selectedNode }),
    selectedNodeDetail: null,
    setSelectedNodeDetail: (selectedNodeDetail) => set({ selectedNodeDetail }),
    selectedNodeTelemetry: [],
    setSelectedNodeTelemetry: (selectedNodeTelemetry) => set({ selectedNodeTelemetry }),
    selectedNodeLoading: false,
    setSelectedNodeLoading: (selectedNodeLoading) => set({ selectedNodeLoading }),

    // Data Source & Sync State
    dataSources: {},
    updateDataSource: (key, patch) =>
      set((prev) => ({
        dataSources: {
          ...prev.dataSources,
          [key]: patch,
        },
      })),
    syncing: false,
    setSyncing: (syncing) => set({ syncing }),
    loading: !initialConnection?.connected,
    setLoading: (loading) => set({ loading }),
    dataError: '',
    setDataError: (dataError) => set({ dataError }),

    // Caching
    lastFetchedAt: null,
    cacheTtlMs: 20000, // 20s caching to prevent rapid duplicate fetches
    invalidateCache: () => set({ lastFetchedAt: null }),
    revokeSecurityGroupLocally: (groupId: string) => {
      set((prev) => {
        const currentAudit = prev.securityAudit
        const updatedExposed = (currentAudit?.exposed_security_groups || []).filter(
          (sg: any) => sg.group_id !== groupId
        )
        const updatedAll = (currentAudit?.all_security_groups || []).map((sg: any) =>
          sg.group_id === groupId
            ? { ...sg, is_publicly_exposed: false, exposed_ports: [], inbound_rules_count: 0 }
            : sg
        )
        const updatedAudit = currentAudit
          ? {
              ...currentAudit,
              exposed_security_groups: updatedExposed,
              all_security_groups: updatedAll,
            }
          : currentAudit

        const currentSummary = prev.summary
        const updatedSummary = currentSummary
          ? {
              ...currentSummary,
              critical_security_risks: Math.max(0, updatedExposed.length),
            }
          : currentSummary

        const currentDetail = prev.selectedNodeDetail
        let updatedDetail = currentDetail
        if (currentDetail) {
          const updateSgList = (list: any[]) =>
            list.map((sg) =>
              sg.group_id === groupId
                ? { ...sg, is_publicly_exposed: false, exposed_ports: [] }
                : sg
            )
          updatedDetail = {
            ...currentDetail,
            security_groups_detail: Array.isArray(currentDetail.security_groups_detail)
              ? updateSgList(currentDetail.security_groups_detail)
              : currentDetail.security_groups_detail,
            security_groups: Array.isArray(currentDetail.security_groups)
              ? updateSgList(currentDetail.security_groups)
              : currentDetail.security_groups,
          }
        }

        return {
          securityAudit: updatedAudit,
          summary: updatedSummary,
          selectedNodeDetail: updatedDetail,
          lastFetchedAt: null,
        }
      })
    },

    // Data Fetching & Caching Orchestrator with Stale-While-Revalidate
    fetchData: async (apiUrl, force = false) => {
      const { connectionState, lastFetchedAt, cacheTtlMs, provider, timeframe } = get()

      if (!connectionState?.connected) {
        set({
          summary: null,
          nodes: [],
          telemetry: [],
          spend: [],
          alerts: [],
          optimizations: [],
          securityAudit: null,
          applied: [],
          dataSources: {},
          dataError: 'Connect an AWS account to load live data.',
          loading: false,
          syncing: false,
        })
        return
      }

      // Check cache freshness
      const now = Date.now()
      if (!force && lastFetchedAt && now - lastFetchedAt < cacheTtlMs) {
        return
      }

      // Preserve existing ready statuses during background sync so UI doesn't flicker
      const currentSources = get().dataSources
      const initialSources: DataSourceCoverage = { ...currentSources }
      DATA_SOURCE_KEYS.forEach((key) => {
        if (!currentSources[key] || currentSources[key]?.status !== 'ready') {
          initialSources[key] = { status: 'loading' }
        }
      })

      set({ syncing: true, dataError: '', dataSources: initialSources })

      const fetchLive = async (url: string, timeoutMs = 25000) => {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), timeoutMs)
        try {
          const res = await fetch(apiUrl(url), { signal: controller.signal })
          const responseBody = await res.json().catch(() => ({}))
          if (!res.ok) {
            throw new Error(responseBody?.detail || `Live data request failed (${res.status})`)
          }
          return responseBody
        } catch (err) {
          if (err instanceof DOMException && err.name === 'AbortError') {
            throw new Error(`Timed out after ${Math.round(timeoutMs / 1000)}s`)
          }
          throw err
        } finally {
          clearTimeout(timer)
        }
      }

      const requests = {
        summary: fetchLive('/api/v1/dashboard/summary'),
        nodes: fetchLive(`/api/nodes?provider=${provider}`),
        telemetry: fetchLive(`/api/telemetry?timeframe=${timeframe}`),
        spend: fetchLive(`/api/spend?provider=${provider}`),
        alerts: fetchLive('/api/alerts'),
        optimizations: fetchLive('/api/v1/optimizations'),
        security: fetchLive('/api/v1/security/audit'),
        applied: fetchLive('/api/optimizations/applied'),
      }

      try {
        const results = await Promise.allSettled(
          Object.entries(requests).map(async ([key, promise]) => [key, await promise] as const)
        )

        const resolved = Object.fromEntries(
          results.flatMap((result) => {
            if (result.status === 'fulfilled') return [result.value]
            return []
          })
        ) as Record<string, any>

        const failed = results
          .map((result, index) => ({ result, key: Object.keys(requests)[index] }))
          .filter((item): item is { key: string; result: PromiseRejectedResult } => item.result.status === 'rejected')
          .map((item) => ({
            key: item.key,
            error: item.result.reason instanceof Error ? item.result.reason.message : String(item.result.reason),
          }))

        const updatedSources: DataSourceCoverage = {}

        // Summary handling with graceful fallback & stale preservation
        if (resolved.summary) {
          set({ summary: resolved.summary })
          updatedSources['summary'] = { status: 'ready' }
        } else if (get().summary && !get().summary?.partial) {
          updatedSources['summary'] = { status: 'ready' }
        } else {
          const currentNodes = resolved.nodes || get().nodes || []
          const nodeCount = Array.isArray(currentNodes) ? currentNodes.length : 0
          const runningCount = Array.isArray(currentNodes)
            ? currentNodes.filter((node: any) => node?.state === 'running').length
            : 0
          const currentSpend = resolved.spend || get().spend || []
          const currentSecurity = resolved.security || get().securityAudit
          set({
            summary: {
              monthly_spend: Array.isArray(currentSpend)
                ? currentSpend.reduce((sum: number, row: any) => sum + Number(row?.aws ?? 0), 0)
                : (get().summary?.monthly_spend || 0),
              total_nodes: nodeCount || (get().summary?.total_nodes || 0),
              running_nodes: runningCount || (get().summary?.running_nodes || 0),
              stopped_nodes: Math.max(nodeCount - runningCount, 0),
              wasted_monthly_spend: get().summary?.wasted_monthly_spend || 0,
              critical_security_risks: Array.isArray(currentSecurity?.exposed_security_groups)
                ? currentSecurity.exposed_security_groups.length
                : (get().summary?.critical_security_risks || 0),
              last_synced: new Date().toISOString(),
              partial: true,
            },
          })
          updatedSources['summary'] = { status: 'partial', error: 'Summary rebuilt from partial results.' }
        }

        // Nodes: Stale-while-revalidate preservation
        if (Array.isArray(resolved.nodes)) {
          set({ nodes: resolved.nodes })
          updatedSources['nodes'] = { status: 'ready' }
        } else if (get().nodes && get().nodes.length > 0) {
          updatedSources['nodes'] = { status: 'ready' }
        } else {
          set({ nodes: [] })
          updatedSources['nodes'] = { status: 'error' }
        }

        // Telemetry
        if (Array.isArray(resolved.telemetry)) {
          set({ telemetry: resolved.telemetry })
          updatedSources['telemetry'] = { status: 'ready' }
        } else if (get().telemetry && get().telemetry.length > 0) {
          updatedSources['telemetry'] = { status: 'ready' }
        } else {
          set({ telemetry: [] })
          updatedSources['telemetry'] = { status: 'error' }
        }

        // Spend
        if (Array.isArray(resolved.spend)) {
          set({ spend: resolved.spend })
          updatedSources['spend'] = { status: 'ready' }
        } else if (get().spend && get().spend.length > 0) {
          updatedSources['spend'] = { status: 'ready' }
        } else {
          set({ spend: [] })
          updatedSources['spend'] = { status: 'error' }
        }

        // Alerts
        if (Array.isArray(resolved.alerts)) {
          set({ alerts: resolved.alerts })
          updatedSources['alerts'] = { status: 'ready' }
        } else if (get().alerts && get().alerts.length > 0) {
          updatedSources['alerts'] = { status: 'ready' }
        } else {
          set({ alerts: [] })
          updatedSources['alerts'] = { status: 'error' }
        }

        // Optimizations
        if (Array.isArray(resolved.optimizations?.recommendations)) {
          set({ optimizations: resolved.optimizations.recommendations })
          updatedSources['optimizations'] = { status: 'ready' }
        } else if (get().optimizations && get().optimizations.length > 0) {
          updatedSources['optimizations'] = { status: 'ready' }
        } else {
          set({ optimizations: [] })
          updatedSources['optimizations'] = { status: 'error' }
        }

        // Security Audit
        if (resolved.security) {
          set({ securityAudit: resolved.security })
          updatedSources['security'] = { status: 'ready' }
        } else if (get().securityAudit) {
          updatedSources['security'] = { status: 'ready' }
        } else {
          set({ securityAudit: null })
          updatedSources['security'] = { status: 'error' }
        }

        // Applied Fixes
        if (Array.isArray(resolved.applied?.applied)) {
          set({ applied: resolved.applied.applied })
          updatedSources['applied'] = { status: 'ready' }
        } else if (get().applied && get().applied.length > 0) {
          updatedSources['applied'] = { status: 'ready' }
        } else {
          set({ applied: [] })
          updatedSources['applied'] = { status: 'error' }
        }

        // Record any errors without overwriting valid data
        failed.forEach((item) => {
          if (item.key === 'summary' && updatedSources['summary']?.status === 'partial') {
            updatedSources['summary'].error = item.error
            return
          }
          if (updatedSources[item.key]?.status !== 'ready') {
            updatedSources[item.key] = { status: 'error', error: item.error }
          }
        })

        set((prev) => ({
          dataSources: { ...prev.dataSources, ...updatedSources },
          lastFetchedAt: Date.now(),
        }))
      } finally {
        set({ syncing: false, loading: false })
      }
    },
  }
})
