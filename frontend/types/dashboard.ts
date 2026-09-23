import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export type SyncState = 'idle' | 'loading' | 'ready' | 'partial' | 'error'
export type AccessMode = 'live' | 'read_only' | 'limited' | 'error'
export type Currency = 'USD' | 'INR'
export type CloudProvider = 'all' | 'AWS' | 'GCP' | 'Azure'
export type Timeframe = '24h' | '7d' | '30d' | '90d'

export type ViewType =
  | 'overview'
  | 'inventory'
  | 'telemetry'
  | 'security'
  | 'optimization'
  | 'scheduler'
  | 'gitops-sla'
  | 'fleet'
  | 'cicd'
  | 'kubernetes'
  | 'lakehouse'
  | 'copilot'
  | 'settings'
  | (string & {})

export interface ComputeNode {
  instance_id: string
  name?: string
  type?: string
  instance_type?: string
  state?: 'running' | 'stopped' | 'terminated' | string
  region?: string
  availability_zone?: string
  public_ip?: string
  private_ip?: string
  vpc_id?: string
  subnet_id?: string
  platform?: string
  architecture?: string
  lifecycle?: string
  key_name?: string
  image_id?: string
  launch_time?: string
  volumes?: number
  attached_volume_ids?: string[]
  cost?: number
  monthly_cost?: number
  wasted_cost?: number
  cpu_utilization?: number
  tags?: Record<string, string>
}

export interface TelemetryPoint {
  time: string
  cpu?: number
  memory?: number
  network?: number
  disk?: number
}

export interface SpendPoint {
  date: string
  aws?: number
  gcp?: number
  azure?: number
  total?: number
}

export interface CloudAlert {
  id?: string
  title: string
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info' | string
  message?: string
  tag?: string
  category?: string
  resource?: string
  timestamp?: string
}

export interface OptimizationRecommendation {
  id: string
  title: string
  category: string
  type?: string
  monthly_savings?: number
  savings?: number
  impact?: string
  severity?: string
  resource_id?: string
  description?: string
  action_type?: string
  details?: Record<string, unknown>
}

export interface SecurityAudit {
  score?: number
  exposed_security_groups?: Array<{
    group_id: string
    group_name: string
    risk: string
    description?: string
    ports?: number[]
  }>
  findings?: Array<{
    id: string
    title: string
    severity: string
    resource: string
    description: string
  }>
  critical_count?: number
}

export interface DashboardSummary {
  monthly_spend: number
  running_nodes: number
  total_nodes: number
  stopped_nodes?: number
  wasted_monthly_spend: number
  critical_security_risks: number
  last_synced?: string
  partial?: boolean
  currency?: string
}

export interface ConnectionState {
  connected: boolean
  status: 'disconnected' | 'connecting' | 'success' | 'limited' | 'error' | string
  message: string
  provider?: string | null
  account_name?: string | null
  region?: string | null
  role_arn?: string | null
  access_mode?: AccessMode | null
  warning?: string | null
}

export interface ConnectedAccount {
  account_id?: string
  account_name?: string
  provider?: string
  region?: string
  role_arn?: string
  active?: boolean
  access_key_last4?: string
}

export interface CloudProfile {
  provider: string
  account_name: string
  auth_method: string
  region: string
  role_arn?: string
  connected_at: string
}

export interface DataSourceStatus {
  status: SyncState
  error?: string
  count?: number
}

export type DataSourceCoverage = Record<string, DataSourceStatus>

export interface FleetAccount {
  account_id: string
  account_name: string
  region: string
  role_arn?: string
  is_management?: boolean
  status?: string
  monthly_spend?: number
  nodes_count?: number
}

export interface FleetSummary {
  total_accounts_registered: number
  total_fleet_monthly_spend: number
  total_fleet_nodes: number
  total_fleet_volumes: number
  total_fleet_eips: number
}

export interface MetricCardProps {
  icon: LucideIcon
  label: string
  value: string | number
  detail?: string
  tone?: 'cyan' | 'emerald' | 'amber' | 'red' | 'purple'
  trend?: string
}

export interface SectionTitleProps {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
  status?: ReactNode
}

export interface SectionStatusBadgeProps {
  status: SyncState
}
