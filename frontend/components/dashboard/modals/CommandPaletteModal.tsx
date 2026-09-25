'use client'

import { useState, useEffect, useMemo } from 'react'
import {
  Activity,
  ArrowRight,
  CircleDollarSign,
  Command,
  GitBranch,
  GitPullRequest,
  LayoutDashboard,
  Network,
  Search,
  Server,
  Settings,
  ShieldAlert,
  Sparkles,
  Zap,
} from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import type { ViewType, ComputeNode } from '@/types/dashboard'

interface CommandPaletteModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentView: ViewType
  onSelectView: (view: ViewType) => void
  nodes?: ComputeNode[]
  onSelectNode?: (node: ComputeNode) => void
  onToggleCurrency?: () => void
  currency?: string
}

interface CommandItem {
  id: string
  title: string
  subtitle?: string
  category: 'Navigation' | 'Instances' | 'Quick Actions'
  icon: any
  action: () => void
  keywords?: string[]
}

export function CommandPaletteModal({
  open,
  onOpenChange,
  currentView,
  onSelectView,
  nodes = [],
  onSelectNode,
  onToggleCurrency,
  currency = 'USD',
}: CommandPaletteModalProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)

  // Listen for Cmd+K / Ctrl+K keyboard shortcut globally
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        onOpenChange(!open)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onOpenChange])

  // Build command list
  const commands = useMemo<CommandItem[]>(() => {
    const list: CommandItem[] = [
      {
        id: 'nav-overview',
        title: 'Executive Overview',
        subtitle: 'High-level cloud spend, active nodes, and top alerts',
        category: 'Navigation',
        icon: LayoutDashboard,
        action: () => {
          onSelectView('overview')
          onOpenChange(false)
        },
        keywords: ['home', 'dashboard', 'spend', 'kpi'],
      },
      {
        id: 'nav-inventory',
        title: 'Compute Inventory',
        subtitle: 'List of all active, stopped, and orphaned EC2 instances',
        category: 'Navigation',
        icon: Server,
        action: () => {
          onSelectView('inventory')
          onOpenChange(false)
        },
        keywords: ['instances', 'vms', 'nodes', 'ebs'],
      },
      {
        id: 'nav-telemetry',
        title: 'Telemetry & Real-Time Metrics',
        subtitle: 'Sub-second CPU, RAM, Disk IOPS, and network graphs',
        category: 'Navigation',
        icon: Activity,
        action: () => {
          onSelectView('telemetry')
          onOpenChange(false)
        },
        keywords: ['cloudwatch', 'stats', 'cpu', 'memory'],
      },
      {
        id: 'nav-security',
        title: 'Security & Exposure Audit',
        subtitle: 'Public security group ports and orphaned Elastic IPs',
        category: 'Navigation',
        icon: ShieldAlert,
        action: () => {
          onSelectView('security')
          onOpenChange(false)
        },
        keywords: ['firewall', 'ports', 'ssh', 'ingress'],
      },
      {
        id: 'nav-optimization',
        title: 'Cost Optimization Engine',
        subtitle: 'Actionable rightsizing, idle cleanup, and alternative plans',
        category: 'Navigation',
        icon: CircleDollarSign,
        action: () => {
          onSelectView('optimization')
          onOpenChange(false)
        },
        keywords: ['savings', 'waste', 'downsize', 'rightsize'],
      },
      {
        id: 'nav-scheduler',
        title: 'Schedules & Pre-Warming',
        subtitle: 'Automated start/stop policies and dev/staging schedules',
        category: 'Navigation',
        icon: Zap,
        action: () => {
          onSelectView('scheduler')
          onOpenChange(false)
        },
        keywords: ['prewarm', 'cron', 'auto-stop', 'grace-period'],
      },
      {
        id: 'nav-gitops',
        title: 'GitOps & SLA Watchdog',
        subtitle: 'Terraform PR generator and post-remediation rollback watchdog',
        category: 'Navigation',
        icon: GitBranch,
        action: () => {
          onSelectView('gitops-sla')
          onOpenChange(false)
        },
        keywords: ['terraform', 'hcl', 'rollback', 'sla'],
      },
      {
        id: 'nav-fleet',
        title: 'Enterprise Fleet (100+)',
        subtitle: 'Cross-account multi-cloud orchestrator and AWS Organization enrollment',
        category: 'Navigation',
        icon: Network,
        action: () => {
          onSelectView('fleet')
          onOpenChange(false)
        },
        keywords: ['accounts', 'multi-cloud', 'cross-account'],
      },
      {
        id: 'nav-cicd',
        title: 'CI/CD & GitHub App Guardrails',
        subtitle: 'Autonomous PR cost analysis and pull request status checks',
        category: 'Navigation',
        icon: GitPullRequest,
        action: () => {
          onSelectView('cicd')
          onOpenChange(false)
        },
        keywords: ['github', 'actions', 'pr-check'],
      },
      {
        id: 'nav-copilot',
        title: 'AI FinOps Copilot',
        subtitle: 'Multi-domain LLM assistant for AWS, OpenCost, and FOCUS lakehouse',
        category: 'Navigation',
        icon: Sparkles,
        action: () => {
          onSelectView('copilot')
          onOpenChange(false)
        },
        keywords: ['ai', 'chat', 'groq', 'rag'],
      },
      {
        id: 'nav-settings',
        title: 'Settings & Notifications',
        subtitle: 'Slack, Microsoft Teams, Twilio webhook integration',
        category: 'Navigation',
        icon: Settings,
        action: () => {
          onSelectView('settings')
          onOpenChange(false)
        },
        keywords: ['slack', 'teams', 'webhooks', 'account'],
      },
    ]

    // Quick Action: Currency Toggle
    if (onToggleCurrency) {
      list.push({
        id: 'act-currency',
        title: `Switch Display Currency (Currently: ${currency})`,
        subtitle: currency === 'USD' ? 'Switch to INR (₹ 84.0/$) with Lakh & Crore formatting' : 'Switch to USD ($) format',
        category: 'Quick Actions',
        icon: CircleDollarSign,
        action: () => {
          onToggleCurrency()
          onOpenChange(false)
        },
        keywords: ['currency', 'usd', 'inr', 'dollar', 'rupee'],
      })
    }

    // Top Compute Instances for fast jump
    if (nodes && nodes.length > 0 && onSelectNode) {
      nodes.slice(0, 10).forEach((node) => {
        list.push({
          id: `instance-${node.instance_id}`,
          title: node.name || node.instance_id,
          subtitle: `${node.instance_id} · ${node.instance_type || 't3.micro'} · ${node.state || 'running'} · ${node.region}`,
          category: 'Instances',
          icon: Server,
          action: () => {
            onSelectNode(node)
            onOpenChange(false)
          },
          keywords: [node.instance_id, node.name || '', node.region || '', node.instance_type || ''],
        })
      })
    }

    return list
  }, [onSelectView, onOpenChange, onToggleCurrency, currency, nodes, onSelectNode])

  // Filter commands by search query
  const filtered = useMemo(() => {
    if (!query.trim()) return commands
    const q = query.toLowerCase().trim()
    return commands.filter((c) => {
      if (c.title.toLowerCase().includes(q)) return true
      if (c.subtitle?.toLowerCase().includes(q)) return true
      if (c.keywords?.some((k) => k.toLowerCase().includes(q))) return true
      return false
    })
  }, [commands, query])

  // Reset selected index when query changes
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  // Keyboard navigation inside command palette
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filtered.length))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % Math.max(1, filtered.length))
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      e.preventDefault()
      filtered[selectedIndex].action()
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 border-border bg-card backdrop-blur-xl sm:max-w-xl overflow-hidden shadow-2xl">
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          <Search className="size-4 text-sky-600 dark:text-sky-400 shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a view name, instance ID, or quick action..."
            className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
            autoFocus
          />
          <Badge variant="outline" className="border-border text-[10px] font-mono text-muted-foreground">
            ESC
          </Badge>
        </div>

        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground">
              No matching commands or instances found.
            </div>
          ) : (
            filtered.map((item, index) => {
              const Icon = item.icon
              const isSelected = index === selectedIndex
              return (
                <div
                  key={item.id}
                  onClick={() => item.action()}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`flex items-center justify-between rounded-lg px-3 py-2 text-xs cursor-pointer transition-colors duration-150 ${
                    isSelected ? 'bg-sky-50 dark:bg-sky-500/15 text-sky-800 dark:text-sky-200 border border-sky-200 dark:border-sky-500/30' : 'text-muted-foreground hover:bg-muted/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className={`flex size-7 items-center justify-center rounded-md shrink-0 ${
                        isSelected ? 'bg-sky-100 dark:bg-sky-500/20 text-sky-700 dark:text-sky-400' : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      <Icon className="size-3.5" />
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium text-foreground tracking-tight flex items-center gap-2 truncate">
                        {item.title}
                        {item.category === 'Quick Actions' && (
                          <span className="text-[10px] rounded px-1.5 py-0.2 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/20 font-mono">
                            Action
                          </span>
                        )}
                      </div>
                      {item.subtitle && (
                        <div className="text-[11px] text-muted-foreground/80 truncate">{item.subtitle}</div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 pl-2">
                    <span className="text-[10px] font-mono text-muted-foreground/60">{item.category}</span>
                    {isSelected && <ArrowRight className="size-3 text-sky-600 dark:text-sky-400" />}
                  </div>
                </div>
              )
            })
          )}
        </div>

        <div className="flex items-center justify-between border-t border-border px-4 py-2 bg-muted/30 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-3">
            <span>Use <kbd className="rounded border border-border bg-background px-1 py-0.5 font-mono text-[10px] text-foreground">↑</kbd> <kbd className="rounded border border-border bg-background px-1 py-0.5 font-mono text-[10px] text-foreground">↓</kbd> to navigate</span>
            <span><kbd className="rounded border border-border bg-background px-1 py-0.5 font-mono text-[10px] text-foreground">↵</kbd> to select</span>
          </div>
          <div className="flex items-center gap-1">
            <Command className="size-3 text-sky-600 dark:text-sky-400" />
            <span>CloudPulse Spotlight</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
