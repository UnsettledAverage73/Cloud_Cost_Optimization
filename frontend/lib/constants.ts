import {
  LayoutDashboard,
  Server,
  Activity,
  ShieldAlert,
  CircleDollarSign,
  Zap,
  GitBranch,
  Network,
  GitPullRequest,
  Sparkles,
  Settings,
  type LucideIcon,
} from 'lucide-react'
import type { ViewType } from '@/types/dashboard'

export interface NavItem {
  id: ViewType
  label: string
  icon: LucideIcon
}

export const NAVIGATION_ITEMS: NavItem[] = [
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

export const DATA_SOURCES = [
  { key: 'summary', label: 'Summary' },
  { key: 'nodes', label: 'Instances' },
  { key: 'telemetry', label: 'Telemetry' },
  { key: 'spend', label: 'Spend' },
  { key: 'alerts', label: 'Alerts' },
  { key: 'optimizations', label: 'Optimizations' },
  { key: 'security', label: 'Security audit' },
  { key: 'applied', label: 'Applied fixes' },
] as const

export function connectionKey(account: any): string {
  return [
    account?.provider || '',
    account?.account_name || '',
    account?.region || '',
    account?.role_arn || '',
    account?.access_key_last4 || '',
  ].join('::')
}
