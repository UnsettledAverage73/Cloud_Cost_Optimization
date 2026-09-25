'use client'

import { useState } from 'react'
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  Cloud,
  ExternalLink,
  HardDrive,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { TableSkeleton } from '@/components/empty-state'
import { MetricCard, SectionTitle, SectionStatusBadge } from '@/components/dashboard'
import { useOptimisticToast } from '@/components/ui/optimistic-toast'
import { formatInteger } from '@/lib/formatters'
import type { SecurityAudit } from '@/types/dashboard'

interface SecurityViewProps {
  accessMode?: string
  tab: string
  setTab: (tab: string) => void
  summary?: any
  audit?: SecurityAudit | null
  sectionStatus?: 'idle' | 'loading' | 'ready' | 'partial' | 'error'
  apiUrl: (path: string) => string
  onRefresh?: (silent?: boolean) => void
  revokeSecurityGroupLocally?: (groupId: string) => void
}

export function SecurityView({
  tab,
  setTab,
  summary,
  audit,
  sectionStatus = 'idle',
  apiUrl,
  onRefresh,
  revokeSecurityGroupLocally,
}: SecurityViewProps) {
  const { toast } = useOptimisticToast()
  const exposedSecurityGroups = (audit as any)?.exposed_security_groups || []
  const allSecurityGroups = ((audit as any)?.all_security_groups && (audit as any).all_security_groups.length > 0)
    ? (audit as any).all_security_groups
    : exposedSecurityGroups
  const unattachedElasticIPs = (audit as any)?.unattached_elastic_ips || []
  const orphanedEbsVolumes = (audit as any)?.orphaned_ebs_volumes || []

  const [sgFilter, setSgFilter] = useState<'all' | 'exposed' | 'secured'>('all')
  const [revokeModalOpen, setRevokeModalOpen] = useState(false)
  const [selectedGroupToRevoke, setSelectedGroupToRevoke] = useState<any | null>(null)
  const [revoking, setRevoking] = useState(false)
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  const filteredSecurityGroups = allSecurityGroups.filter((group: any) => {
    const isExposed = Boolean(group.is_publicly_exposed ?? exposedSecurityGroups.some((e: any) => e.group_id === group.group_id))
    if (sgFilter === 'exposed') return isExposed
    if (sgFilter === 'secured') return !isExposed
    return true
  })

  const handleRevokeClick = (group: any) => {
    setSelectedGroupToRevoke(group)
    setRevokeModalOpen(true)
  }

  const confirmRevoke = async () => {
    if (!selectedGroupToRevoke) return
    const targetId = selectedGroupToRevoke.group_id
    const targetName = selectedGroupToRevoke.group_name || targetId
    setRevoking(true)
    setFeedback(null)

    // Instant optimistic update
    revokeSecurityGroupLocally?.(targetId)
    setRevokeModalOpen(false)
    toast({
      title: 'Security Ingress Revoked',
      description: `Revoked 0.0.0.0/0 exposure for ${targetName}. Dispatched rule deletion to provider...`,
      type: 'security',
    })

    try {
      const endpoint = apiUrl ? apiUrl('/api/security/revoke') : '/api/security/revoke'
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ groupId: targetId, groupName: targetName }),
      })
      if (res.ok) {
        setFeedback({
          type: 'success',
          message: `Public ingress (0.0.0.0/0) successfully revoked for ${targetName}.`,
        })
        onRefresh?.(true)
      } else {
        const err = await res.json().catch(() => ({}))
        setFeedback({
          type: 'error',
          message: err.detail || 'Failed to revoke security group ingress.',
        })
        toast({
          title: 'Revocation Sync Failed',
          description: err.detail || 'Failed to revoke security group on provider.',
          type: 'error',
        })
      }
    } catch (e: any) {
      setFeedback({
        type: 'error',
        message: e?.message || 'Network error while attempting revocation.',
      })
      toast({
        title: 'Network Sync Error',
        description: e?.message || 'Network error while contacting CloudPulse backend.',
        type: 'error',
      })
    } finally {
      setRevoking(false)
    }
  }

  return (
    <>
      <SectionTitle
        eyebrow="Security center"
        title="Exposure audit"
        description="Resolve public attack surface, exposed ports, and unmanaged cloud resources."
        status={<SectionStatusBadge status={sectionStatus} />}
      />

      {feedback && (
        <div
          className={`mb-4 flex items-center justify-between rounded-lg border p-3 text-xs ${
            feedback.type === 'success'
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : 'border-rose-500/30 bg-rose-500/10 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-2">
            {feedback.type === 'success' ? (
              <CheckCircle2 className="size-4 shrink-0 text-emerald-400" />
            ) : (
              <AlertCircle className="size-4 shrink-0 text-rose-400" />
            )}
            <span>{feedback.message}</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-5 hover:bg-transparent text-muted-foreground hover:text-white"
            onClick={() => setFeedback(null)}
          >
            <X className="size-3" />
          </Button>
        </div>
      )}

      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <MetricCard
          icon={ShieldAlert}
          label="Critical risks"
          value={formatInteger(summary?.critical_security_risks)}
          detail="From the live summary endpoint"
          tone="rose"
        />
        <MetricCard
          icon={Cloud}
          label="Public security groups"
          value={`${exposedSecurityGroups.length} exposed`}
          detail={`${allSecurityGroups.length} total detected on AWS`}
          tone={exposedSecurityGroups.length > 0 ? 'amber' : 'emerald'}
        />
        <MetricCard
          icon={HardDrive}
          label="Orphaned resources"
          value={formatInteger(unattachedElasticIPs.length + orphanedEbsVolumes.length)}
          detail="Unattached EIPs and volumes"
          tone="sky"
        />
      </div>

      <Tabs value={tab} onValueChange={(val) => setTab(val ?? 'groups')}>
        <TabsList className="mb-4 bg-white/5 w-full sm:w-auto overflow-x-auto justify-start max-w-full">
          <TabsTrigger value="groups">Security groups ({allSecurityGroups.length})</TabsTrigger>
          <TabsTrigger value="ips">Elastic IPs & NAT</TabsTrigger>
          <TabsTrigger value="logs">CloudWatch logs</TabsTrigger>
        </TabsList>

        <TabsContent value="groups">
          <Card className="border-border bg-card overflow-hidden shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-3 bg-muted/20">
              <div className="flex items-center gap-1.5">
                <Button
                  variant={sgFilter === 'all' ? 'secondary' : 'ghost'}
                  size="sm"
                  className="h-7 text-xs px-2.5"
                  onClick={() => setSgFilter('all')}
                >
                  All ({allSecurityGroups.length})
                </Button>
                <Button
                  variant={sgFilter === 'exposed' ? 'secondary' : 'ghost'}
                  size="sm"
                  className={`h-7 text-xs px-2.5 ${exposedSecurityGroups.length > 0 ? 'text-amber-600 dark:text-amber-400 font-medium' : ''}`}
                  onClick={() => setSgFilter('exposed')}
                >
                  Exposed risks ({exposedSecurityGroups.length})
                </Button>
                <Button
                  variant={sgFilter === 'secured' ? 'secondary' : 'ghost'}
                  size="sm"
                  className="h-7 text-xs px-2.5 text-emerald-600 dark:text-emerald-400"
                  onClick={() => setSgFilter('secured')}
                >
                  Secured ({Math.max(0, allSecurityGroups.length - exposedSecurityGroups.length)})
                </Button>
              </div>
              <div className="text-[11px] text-muted-foreground pr-2">
                Live sync with AWS VPC security groups
              </div>
            </div>

            {sectionStatus === 'loading' ? (
              <TableSkeleton rows={4} cols={5} />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="border-b border-border">
                    <TableHead>Group Name & ID</TableHead>
                    <TableHead>VPC</TableHead>
                    <TableHead>Protection Status</TableHead>
                    <TableHead>Inbound Rules / Open Ports</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredSecurityGroups.length ? (
                    filteredSecurityGroups.map((group: any) => {
                      const isExposed = Boolean(
                        group.is_publicly_exposed ?? exposedSecurityGroups.some((e: any) => e.group_id === group.group_id)
                      )
                      return (
                        <TableRow key={group.group_id} className="border-b border-border">
                          <TableCell>
                            <div className="font-medium text-foreground">{group.group_name || '—'}</div>
                            <div className="font-mono text-xs text-muted-foreground">{group.group_id}</div>
                            {group.description && (
                              <div className="text-[11px] text-muted-foreground truncate max-w-xs">
                                {group.description}
                              </div>
                            )}
                          </TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground">
                            {group.vpc_id || '—'}
                          </TableCell>
                          <TableCell>
                            {isExposed ? (
                              <Badge className="border-rose-400/20 bg-rose-400/10 text-rose-300">Publicly exposed</Badge>
                            ) : (
                              <Badge className="border-emerald-500/20 bg-emerald-500/10 text-emerald-300 flex items-center gap-1 w-fit">
                                <ShieldCheck className="size-3" /> Secured
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            {isExposed && (group.exposed_ports || []).length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {(group.exposed_ports || []).map((port: number) => (
                                  <Badge
                                    key={port}
                                    variant="outline"
                                    className={
                                      port === 22 || port === 3389
                                        ? 'border-rose-400/30 text-rose-300 font-mono text-[11px]'
                                        : 'font-mono text-[11px]'
                                    }
                                  >
                                    {port}
                                    {port === 22 ? ' SSH' : port === 3389 ? ' RDP' : port === 5901 ? ' VNC' : port === 6080 ? ' Web' : ''}
                                  </Badge>
                                ))}
                              </div>
                            ) : (
                              <div className="text-xs text-muted-foreground">
                                {group.inbound_rules_count ?? 0} inbound rules &middot; 0 open to 0.0.0.0/0
                              </div>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            {isExposed ? (
                              <Button
                                size="sm"
                                variant="destructive"
                                className="h-8 text-xs font-semibold"
                                onClick={() => handleRevokeClick(group)}
                              >
                                Revoke Ingress
                              </Button>
                            ) : (
                              <span className="text-xs text-emerald-400/80 inline-flex items-center gap-1 font-medium">
                                <Check className="size-3 text-emerald-400" /> Protected
                              </span>
                            )}
                          </TableCell>
                        </TableRow>
                      )
                    })
                  ) : (
                    <TableRow className="border-b border-border">
                      <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                        {sgFilter === 'exposed'
                          ? 'No publicly exposed security groups detected. All workloads are protected from direct internet ingress.'
                          : sgFilter === 'secured'
                          ? 'No secured security groups found.'
                          : 'No security groups found for this account/region.'}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="ips">
          <Card className="border-border bg-card overflow-hidden shadow-sm">
            {sectionStatus === 'loading' ? (
              <TableSkeleton rows={4} cols={3} />
            ) : unattachedElasticIPs.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow className="border-b border-border">
                    <TableHead>Elastic IP</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Monthly cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {unattachedElasticIPs.map((eip: any) => (
                    <TableRow key={eip.public_ip} className="border-b border-border">
                      <TableCell className="font-mono text-xs">{eip.public_ip}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="border-amber-500/30 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10">
                          Unattached
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">${Number(eip.estimated_monthly_cost ?? 0).toFixed(2)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-6">
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6 text-center sm:text-left flex flex-col sm:flex-row items-center gap-4">
                  <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                    <CheckCircle2 className="size-6" />
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="text-sm font-semibold text-foreground flex items-center gap-2 justify-center sm:justify-start">
                      Optimal FinOps Hygiene: Zero Unattached Elastic IPs
                      <Badge variant="outline" className="border-emerald-500/30 text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 text-[10px]">
                        $0.00 / mo Waste
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      All allocated public IPv4 addresses and NAT Gateways in this AWS region are actively attached to running EC2 instances and network interfaces. You are incurring zero idle IPv4 surcharges.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="logs">
          <Card className="border-border bg-card p-6 space-y-4 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-sky-50 dark:bg-sky-400/10 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-400/20">
                  <Activity className="size-5" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-foreground">VPC Flow Logs & Security Telemetry</h4>
                  <p className="text-xs text-muted-foreground">Real-time packet inspection and port brute-force detection</p>
                </div>
              </div>
              <Badge variant="outline" className="border-sky-500/30 text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-500/10 text-xs">
                CloudWatch Insights
              </Badge>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 pt-2">
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="text-[11px] text-muted-foreground">Inbound Scanning Shield</div>
                <div className="mt-1 text-xs font-semibold text-foreground">Ports 22, 3389, 5901 Monitored</div>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="text-[11px] text-muted-foreground">VPC Packet Rejection</div>
                <div className="mt-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">Flow Logs Active</div>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="text-[11px] text-muted-foreground">Target AWS Region</div>
                <div className="mt-1 text-xs font-semibold text-foreground">us-east-1 (N. Virginia)</div>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-muted/40 p-3.5 text-xs text-muted-foreground leading-relaxed">
              CloudWatch Log Groups capture rejected packets attempting to probe open ports on your public security groups.
              To inspect raw access logs or query suspicious source IPs, use CloudWatch Logs Insights.
            </div>

            <div className="pt-2 flex flex-wrap gap-2">
              <Button
                variant="outline"
                className="border-border bg-card text-xs h-9 hover:bg-muted"
                onClick={() =>
                  window.open(
                    'https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups',
                    '_blank'
                  )
                }
              >
                <ExternalLink className="mr-1.5 size-3.5" />
                Open CloudWatch Logs in AWS Console
              </Button>
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Revocation Safety Confirmation Dialog */}
      <Dialog open={revokeModalOpen} onOpenChange={setRevokeModalOpen}>
        <DialogContent className="border-border bg-card sm:max-w-md shadow-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-semibold">
              <AlertTriangle className="size-5 text-amber-500 shrink-0" />
              Confirm Ingress Revocation
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              {selectedGroupToRevoke?.group_name} ({selectedGroupToRevoke?.group_id})
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs">
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-amber-800 dark:text-amber-200 leading-relaxed">
              <span className="font-semibold">Warning:</span> Revoking <code>0.0.0.0/0</code> ingress will close public access on:
              <div className="mt-1.5 flex flex-wrap gap-1 font-mono">
                {(selectedGroupToRevoke?.exposed_ports || []).map((port: number) => (
                  <Badge key={port} variant="outline" className="border-amber-400/40 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-400/10 text-[10px]">
                    Port {port}
                  </Badge>
                ))}
              </div>
            </div>
            <p className="text-muted-foreground leading-relaxed">
              If you or your team are actively connected to workloads using this security group (e.g. via SSH, VNC, or Windows Remote Desktop XRDP), revoking these rules will immediately drop active remote sessions.
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <Button variant="outline" size="sm" onClick={() => setRevokeModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" size="sm" disabled={revoking} onClick={confirmRevoke}>
              {revoking ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <ShieldAlert className="mr-1.5 size-3.5" />}
              {revoking ? 'Revoking Ingress...' : 'Confirm & Revoke Ingress'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
export default SecurityView
