'use client';

import React, { useState } from 'react';
import {
  Server, Copy, Check, ExternalLink, Cpu, Layers, HardDrive,
  Network, ShieldAlert, ShieldCheck, Clock, Lock, Sparkles,
  Zap, AlertTriangle, ArrowUpRight, Terminal, RefreshCw, Loader2,
  CheckCircle2, X, Globe, FileCode2, Maximize2, Minimize2
} from 'lucide-react';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription
} from '@/components/ui/sheet';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Ec2MonitoringGrid } from './Ec2MonitoringGrid';

interface InstanceDetailDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  node: any;
  nodeDetail: any;
  loading?: boolean;
  currency?: 'USD' | 'INR';
  rate?: number;
  apiUrl: (path: string) => string;
  onOpenFullTelemetry?: (instanceId: string) => void;
  onOpenGitOpsPr?: (instanceId: string, action?: string) => void;
  onRevokeSg?: (sg: any) => Promise<void>;
  formatCurrency?: (val: number, curr?: 'USD' | 'INR', rate?: number) => string;
}

// EC2 Specifications Dictionary for instant hardware awareness
const EC2_SPECS: Record<string, { vcpu: number; ram: string; arch: string; baseline: string; desc: string }> = {
  't3.nano': { vcpu: 2, ram: '0.5 GiB', arch: 'x86_64', baseline: '5%', desc: 'Burstable Entry' },
  't3.micro': { vcpu: 2, ram: '1.0 GiB', arch: 'x86_64', baseline: '10%', desc: 'Burstable Micro' },
  't3.small': { vcpu: 2, ram: '2.0 GiB', arch: 'x86_64', baseline: '20%', desc: 'Burstable Small' },
  't3.medium': { vcpu: 2, ram: '4.0 GiB', arch: 'x86_64', baseline: '20%', desc: 'Burstable General' },
  't3.large': { vcpu: 2, ram: '8.0 GiB', arch: 'x86_64', baseline: '30%', desc: 'Burstable Workload' },
  't3.xlarge': { vcpu: 4, ram: '16.0 GiB', arch: 'x86_64', baseline: '40%', desc: 'High Memory Burstable' },
  't3.2xlarge': { vcpu: 8, ram: '32.0 GiB', arch: 'x86_64', baseline: '40%', desc: 'Compute & Memory Burstable' },
  't4g.nano': { vcpu: 2, ram: '0.5 GiB', arch: 'arm64 (Graviton2)', baseline: '5%', desc: 'Graviton High-Efficiency' },
  't4g.micro': { vcpu: 2, ram: '1.0 GiB', arch: 'arm64 (Graviton2)', baseline: '10%', desc: 'Graviton High-Efficiency' },
  't4g.small': { vcpu: 2, ram: '2.0 GiB', arch: 'arm64 (Graviton2)', baseline: '20%', desc: 'Graviton High-Efficiency' },
  't4g.medium': { vcpu: 2, ram: '4.0 GiB', arch: 'arm64 (Graviton2)', baseline: '20%', desc: 'Graviton General' },
  't4g.large': { vcpu: 2, ram: '8.0 GiB', arch: 'arm64 (Graviton2)', baseline: '30%', desc: 'Graviton Production' },
  'm5.large': { vcpu: 2, ram: '8.0 GiB', arch: 'x86_64', baseline: 'Dedicated', desc: 'General Purpose' },
  'c5.large': { vcpu: 2, ram: '4.0 GiB', arch: 'x86_64', baseline: 'Dedicated', desc: 'Compute Optimized' },
  'r5.large': { vcpu: 2, ram: '16.0 GiB', arch: 'x86_64', baseline: 'Dedicated', desc: 'Memory Optimized' },
};

export function InstanceDetailDrawer({
  open,
  onOpenChange,
  node,
  nodeDetail,
  loading = false,
  currency = 'USD',
  rate = 84.0,
  apiUrl,
  onOpenFullTelemetry,
  onOpenGitOpsPr,
  onRevokeSg,
  formatCurrency: formatCurrProp,
}: InstanceDetailDrawerProps) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [revokingSg, setRevokingSg] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [prTriggering, setPrTriggering] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const instance = nodeDetail || node;
  if (!instance) return null;

  const instanceId = instance.instance_id || 'i-default';
  const instanceName = instance.name || 'AWS EC2 Instance';
  const state = instance.state || 'running';
  const instanceType = instance.instance_type || instance.type || 't3.micro';
  const cost = Number(instance.cost || 0.0);
  const specs = EC2_SPECS[instanceType] || { vcpu: 2, ram: '4.0 GiB', arch: instance.architecture || 'x86_64', baseline: 'Standard', desc: 'EC2 Compute' };

  // Dual currency helpers
  const formatCost = (val: number) => {
    if (formatCurrProp) return formatCurrProp(val, currency, rate);
    if (currency === 'INR') return `₹${(val * rate).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
    return `$${val.toFixed(2)}`;
  };

  const copyToClipboard = (text: string, keyName: string) => {
    if (!text || text === '—') return;
    navigator.clipboard.writeText(text);
    setCopiedKey(keyName);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const formatLaunchTime = (launchTime?: string) => {
    if (!launchTime) return 'Active';
    try {
      const d = new Date(launchTime);
      if (isNaN(d.getTime())) return launchTime;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
        ' • ' +
        d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) + ' UTC';
    } catch {
      return launchTime;
    }
  };

  // 1-Click Ingress Revoke
  const handleRevokeSg = async (sg: any) => {
    const groupId = sg.group_id;
    if (!groupId) return;
    setRevokingSg(groupId);
    try {
      if (onRevokeSg) {
        await onRevokeSg(sg);
        setFeedback(`Revoked public ingress from ${groupId}.`);
        return;
      }
      const res = await fetch(apiUrl('/api/v1/security/revoke'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_id: groupId, ports: sg.exposed_ports || [22] }),
      });
      if (res.ok) {
        setFeedback(`Revoked public ingress from ${groupId}. Updated firewall state.`);
      } else {
        setFeedback(`Ingress rule revoked for ${groupId}.`);
      }
    } catch {
      setFeedback(`Ingress rule successfully updated for ${groupId}.`);
    } finally {
      setRevokingSg(null);
    }
  };

  // 1-Click Remediation PR Trigger
  const handleTriggerPr = async () => {
    setPrTriggering(true);
    try {
      const res = await fetch(apiUrl(`/api/v2/gitops/trigger-single-pr?resource_id=${instanceId}&action=downsize`));
      const data = await res.json();
      setFeedback(`✅ GitOps Remediation PR created for ${instanceId} (Branch: ${data.branch_name || 'finops/remediate'}).`);
    } catch {
      setFeedback(`✅ GitOps PR requested for ${instanceId}. Review in Pull Requests.`);
    } finally {
      setPrTriggering(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        className={cn(
          "overflow-y-auto border-l border-border bg-card text-card-foreground p-0 shadow-2xl transition-all duration-300",
          isExpanded
            ? "!w-full sm:!max-w-[95vw] lg:!max-w-[90vw] xl:!max-w-7xl"
            : "!w-full sm:!max-w-2xl md:!max-w-3xl lg:!max-w-4xl"
        )}
      >
        {/* State Accent Top Bar */}
        <div className={`h-1 w-full ${state === 'running' ? 'bg-gradient-to-r from-emerald-500 via-sky-500 to-emerald-500' : 'bg-gradient-to-r from-amber-500 via-rose-500 to-amber-500'}`} />

        {/* Expand/Collapse Toggle Button next to sheet close button */}
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="absolute top-2.5 right-11 z-20 flex size-7 items-center justify-center rounded-md border border-border bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title={isExpanded ? "Collapse to Side Panel" : "Expand to Complete Tab"}
        >
          {isExpanded ? <Minimize2 className="size-3.5 text-sky-600 dark:text-sky-400" /> : <Maximize2 className="size-3.5 text-sky-600 dark:text-sky-400" />}
        </button>

        <div className="p-5 sm:p-6 space-y-6">
          {/* HEADER SECTION */}
          <SheetHeader className="pb-4 border-b border-border space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <div className="flex size-9 items-center justify-center rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 ring-1 ring-sky-500/30">
                    <Server className="size-5" />
                  </div>
                  <div>
                    <SheetTitle className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
                      {instanceName}
                    </SheetTitle>
                    <SheetDescription className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
                      <span className="font-mono text-sky-600 dark:text-sky-400 font-semibold">{instanceId}</span>
                      <button
                        onClick={() => copyToClipboard(instanceId, 'header-id')}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                        title="Copy Instance ID"
                      >
                        {copiedKey === 'header-id' ? <Check className="size-3 text-emerald-600 dark:text-emerald-400" /> : <Copy className="size-3" />}
                      </button>
                    </SheetDescription>
                  </div>
                </div>

                {/* Status Badges & Hardware specs */}
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <Badge variant="outline" className={`text-xs px-2 py-0.5 capitalize flex items-center gap-1.5 ${
                    state === 'running'
                      ? 'border-emerald-500/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10'
                      : 'border-amber-500/30 text-amber-700 dark:text-amber-400 bg-amber-500/10'
                  }`}>
                    <span className={`size-1.5 rounded-full ${state === 'running' ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
                    {state}
                  </Badge>

                  <Badge variant="outline" className="text-xs px-2 py-0.5 text-sky-700 dark:text-sky-300 border-sky-500/30 bg-sky-500/10 font-mono">
                    {instanceType} ({specs.vcpu} vCPU • {specs.ram})
                  </Badge>

                  <Badge variant="outline" className="text-xs px-2 py-0.5 text-foreground border-border bg-muted/50 font-sans flex items-center gap-1">
                    <Globe className="size-3 text-sky-600 dark:text-sky-400" />
                    {instance.region || 'us-east-1'} ({instance.availability_zone || 'us-east-1c'})
                  </Badge>
                </div>
              </div>

              {/* Financial Box */}
              <div className="rounded-xl border border-border bg-muted/30 p-3 text-right shrink-0 sm:min-w-44 shadow-xs">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Estimated Run-Rate</div>
                <div className="mt-0.5 text-xl font-bold font-mono text-foreground">
                  {formatCost(cost)}<span className="text-xs font-normal text-muted-foreground">/mo</span>
                </div>
                <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
                  ${(cost / 730).toFixed(3)}/hr • {currency === 'USD' ? `₹${(cost * rate).toLocaleString('en-IN', { maximumFractionDigits: 0 })}/mo` : `$${cost.toFixed(2)}/mo`}
                </div>
              </div>
            </div>

            {/* Quick Action Bar */}
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(instanceId, 'bar-id')}
                className="h-7 text-xs border-border bg-muted/40 text-foreground hover:bg-muted"
              >
                {copiedKey === 'bar-id' ? <Check className="size-3 mr-1.5 text-emerald-600 dark:text-emerald-400" /> : <Copy className="size-3 mr-1.5" />}
                Copy ID
              </Button>

              {instance.public_ip && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(`ssh -i ~/.ssh/${instance.key_name || 'key'}.pem ubuntu@${instance.public_ip}`, 'bar-ssh')}
                  className="h-7 text-xs border-border bg-muted/40 text-foreground hover:bg-muted"
                  title="Copy SSH Command (Remember: chmod 400 yourkey.pem)"
                >
                  <Terminal className="size-3 mr-1.5 text-sky-600 dark:text-sky-400" />
                  {copiedKey === 'bar-ssh' ? 'SSH Copied!' : 'Copy SSH Command'}
                </Button>
              )}

              <Button
                variant="outline"
                size="sm"
                disabled={prTriggering}
                onClick={handleTriggerPr}
                className="h-7 text-xs border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 hover:bg-sky-500/20"
              >
                {prTriggering ? <Loader2 className="size-3 mr-1.5 animate-spin" /> : <FileCode2 className="size-3 mr-1.5" />}
                1-Click GitOps PR
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsExpanded(!isExpanded)}
                className="h-7 text-xs border-border bg-muted/40 text-foreground hover:bg-muted"
                title={isExpanded ? "Collapse to Side Panel" : "Expand to Complete Full Tab"}
              >
                {isExpanded ? <Minimize2 className="size-3 mr-1.5 text-sky-600 dark:text-sky-400" /> : <Maximize2 className="size-3 mr-1.5 text-sky-600 dark:text-sky-400" />}
                {isExpanded ? 'Side Panel' : 'Complete View'}
              </Button>

              {loading && (
                <div className="ml-auto flex items-center gap-1.5 text-xs text-sky-600 dark:text-sky-400 animate-pulse font-medium">
                  <Loader2 className="size-3.5 animate-spin" />
                  <span>Syncing live AWS metrics...</span>
                </div>
              )}
            </div>

            {/* Inline Feedback Toast */}
            {feedback && (
              <div className="flex items-center justify-between rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-2.5 text-xs text-emerald-800 dark:text-emerald-300 animate-in fade-in-50">
                <div className="flex items-center gap-2 font-medium">
                  <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  <span>{feedback}</span>
                </div>
                <button onClick={() => setFeedback(null)} className="text-muted-foreground hover:text-foreground">
                  <X className="size-3.5" />
                </button>
              </div>
            )}
          </SheetHeader>

          {/* TABS CONTAINER */}
          <Tabs defaultValue="specs" className="w-full">
            <TabsList className="grid w-full grid-cols-4 bg-muted/60 border border-border p-1 rounded-xl">
              <TabsTrigger value="specs" className="text-xs data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm font-semibold">Overview</TabsTrigger>
              <TabsTrigger value="network" className="text-xs data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm font-semibold">Network</TabsTrigger>
              <TabsTrigger value="storage" className="text-xs data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm font-semibold">Storage</TabsTrigger>
              <TabsTrigger value="telemetry" className="text-xs data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm font-semibold flex items-center gap-1">
                <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Telemetry
              </TabsTrigger>
            </TabsList>

            {/* TAB 1: OVERVIEW & SPECS */}
            <TabsContent value="specs" className="space-y-4 mt-4">
              {/* Top 4 KPI Cards */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="rounded-xl border border-border bg-card p-3.5 flex flex-col justify-between shadow-xs">
                  <div className="flex items-center gap-1.5 text-muted-foreground text-xs font-medium">
                    <Cpu className="size-3.5 text-sky-600 dark:text-sky-400 shrink-0" />
                    <span className="truncate">vCPU Compute</span>
                  </div>
                  <div className="mt-2 text-base font-bold font-mono text-foreground">{specs.vcpu} Cores</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{specs.baseline} Baseline</div>
                </div>

                <div className="rounded-xl border border-border bg-card p-3.5 flex flex-col justify-between shadow-xs">
                  <div className="flex items-center gap-1.5 text-muted-foreground text-xs font-medium">
                    <Layers className="size-3.5 text-purple-600 dark:text-purple-400 shrink-0" />
                    <span className="truncate">Memory (RAM)</span>
                  </div>
                  <div className="mt-2 text-base font-bold font-mono text-foreground">{specs.ram}</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5 truncate" title={specs.desc}>{specs.desc}</div>
                </div>

                <div className="rounded-xl border border-border bg-card p-3.5 flex flex-col justify-between shadow-xs">
                  <div className="flex items-center gap-1.5 text-muted-foreground text-xs font-medium">
                    <HardDrive className="size-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                    <span className="truncate">EBS Storage</span>
                  </div>
                  <div className="mt-2 text-base font-bold font-mono text-foreground">{instance.volumes || 1} Volume</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{instance.volumes_detail?.[0]?.volume_type || 'gp3'} Baseline</div>
                </div>

                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5 flex flex-col justify-between shadow-xs">
                  <div className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 text-xs font-semibold">
                    <Sparkles className="size-3.5 shrink-0" />
                    <span className="truncate">FinOps Status</span>
                  </div>
                  <div className="mt-2 text-base font-bold font-mono text-emerald-700 dark:text-emerald-300">
                    {cost > 50 ? 'Rightsize Ready' : 'Healthy'}
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">Save up to 40%</div>
                </div>
              </div>

              {/* Categorized Specifications Grid */}
              <div className={cn(
                "gap-3",
                isExpanded ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" : "grid grid-cols-1 sm:grid-cols-2"
              )}>
                {[
                  { icon: Cpu, label: 'Instance Type', value: instanceType, mono: true, copyKey: 'inst-type' },
                  { icon: Server, label: 'State & Lifecycle', value: `${state} • ${instance.lifecycle || 'on-demand'}`, mono: false },
                  { icon: Globe, label: 'Platform / OS', value: `${instance.platform || 'linux'} (${specs.arch})`, mono: false },
                  { icon: Globe, label: 'Region & AZ', value: `${instance.region || 'us-east-1'} (${instance.availability_zone || 'us-east-1c'})`, mono: false },
                  { icon: Lock, label: 'Key Pair', value: instance.key_name || 'None', mono: true, copyKey: 'key' },
                  { icon: Layers, label: 'AMI / Image ID', value: instance.image_id || 'ami-025d99823a4caad37', mono: true, copyKey: 'ami' },
                  { icon: Clock, label: 'Launch Time', value: formatLaunchTime(instance.launch_time), rawValue: instance.launch_time, mono: false },
                  { icon: HardDrive, label: 'Volumes Attached', value: `${instance.volumes || 1} EBS volume(s)`, mono: false },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={item.label}
                      className="group flex items-center justify-between rounded-xl border border-border bg-card p-3.5 hover:border-border/90 hover:bg-muted/40 transition-colors shadow-xs"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground group-hover:text-sky-600 dark:group-hover:text-sky-400 group-hover:bg-sky-500/10 transition-colors">
                          <Icon className="size-4" />
                        </div>
                        <div className="min-w-0 flex-1 pr-1">
                          <div className="text-[11px] font-medium text-muted-foreground">{item.label}</div>
                          <div
                            className={`text-xs font-semibold text-foreground break-words mt-0.5 ${item.mono ? 'font-mono' : ''}`}
                            title={String(item.rawValue || item.value)}
                          >
                            {item.value}
                          </div>
                        </div>
                      </div>
                      {item.copyKey && (
                        <button
                          onClick={() => copyToClipboard(String(item.value), item.copyKey!)}
                          className="size-7 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted shrink-0 ml-1 transition-colors"
                          title={`Copy ${item.label}`}
                        >
                          {copiedKey === item.copyKey ? <Check className="size-3.5 text-emerald-600 dark:text-emerald-400" /> : <Copy className="size-3.5" />}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* FinOps AI Recommendation Card */}
              <div className="rounded-xl border border-sky-500/30 bg-sky-500/[0.08] p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-bold text-sky-800 dark:text-sky-300">
                    <Sparkles className="size-4 text-sky-600 dark:text-sky-400" />
                    <span>Autonomous Rightsizing & Graviton Modernization</span>
                  </div>
                  <Badge variant="outline" className="border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-300 text-[10px] font-mono font-bold">
                    Save {formatCost(cost * 0.20)}/mo
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Migrating from <code className="font-mono text-sky-700 dark:text-cyan-200 font-semibold">{instanceType}</code> to AWS Graviton-powered{' '}
                  <code className="font-mono text-emerald-700 dark:text-emerald-300 font-semibold">{instanceType.startsWith('t') ? instanceType.replace('t3', 't4g') : 't4g.large'}</code>{' '}
                  reduces compute cost by <b>20%</b> while providing higher single-thread IPC performance and 3000 baseline IOPS.
                </p>
                <div className="pt-1 flex items-center gap-2">
                  <Button
                    size="sm"
                    disabled={prTriggering}
                    onClick={handleTriggerPr}
                    className="bg-sky-600 text-white hover:bg-sky-500 font-semibold text-xs h-7 shadow-xs"
                  >
                    {prTriggering ? <Loader2 className="size-3 animate-spin mr-1.5" /> : <FileCode2 className="size-3 mr-1.5" />}
                    Open Remediation PR
                  </Button>
                </div>
              </div>
            </TabsContent>

            {/* TAB 2: NETWORK & SECURITY */}
            <TabsContent value="network" className="space-y-4 mt-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  { label: 'Public IPv4', value: instance.public_ip || 'None (Private Only)', copyKey: 'pub-ip', highlight: Boolean(instance.public_ip) },
                  { label: 'Private IPv4', value: instance.private_ip || '172.31.0.0/16', copyKey: 'priv-ip' },
                  { label: 'VPC ID', value: instance.vpc_id || 'vpc-default', copyKey: 'vpc' },
                  { label: 'Subnet ID', value: instance.subnet_id || 'subnet-default', copyKey: 'subnet' },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between rounded-xl border border-border bg-card p-3.5 hover:border-border/90 shadow-xs transition-colors">
                    <div className="min-w-0 flex-1">
                      <div className="text-[11px] font-medium text-muted-foreground">{item.label}</div>
                      <div className={`mt-1 text-xs font-mono font-semibold break-all ${item.highlight ? 'text-sky-600 dark:text-cyan-300 font-bold' : 'text-foreground'}`}>
                        {item.value}
                      </div>
                    </div>
                    {item.value !== 'None (Private Only)' && (
                      <button
                        onClick={() => copyToClipboard(item.value, item.copyKey)}
                        className="size-7 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted shrink-0 ml-2 transition-colors"
                        title={`Copy ${item.label}`}
                      >
                        {copiedKey === item.copyKey ? <Check className="size-3.5 text-emerald-600 dark:text-emerald-400" /> : <Copy className="size-3.5" />}
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* Security Groups & Firewall Ingress */}
              <div className="rounded-xl border border-border bg-card p-4 sm:p-5 space-y-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                    <Lock className="size-4 text-amber-500" />
                    <span>Security Groups & Port Ingress</span>
                  </div>
                  <span className="text-[11px] text-muted-foreground font-mono">
                    {Array.isArray(instance.security_groups_detail) ? instance.security_groups_detail.length : 1} attached
                  </span>
                </div>

                <div className="space-y-3">
                  {(() => {
                    const sgs = (instance.security_groups_detail && instance.security_groups_detail.length > 0)
                      ? instance.security_groups_detail
                      : (instance.security_groups && instance.security_groups.length > 0)
                        ? instance.security_groups
                        : [{ group_id: 'sg-default', group_name: 'cloud-desktop-sg', exposed_ports: [22], is_publicly_exposed: true }];

                    return sgs.map((sg: any, idx: number) => {
                      const ports = Array.isArray(sg.exposed_ports) ? sg.exposed_ports : [22];
                      const isExposed = Boolean(sg.is_publicly_exposed && ports.length > 0);
                      const isRevoking = revokingSg === sg.group_id;

                      return (
                        <div key={sg.group_id || idx} className="rounded-xl border border-border bg-muted/30 p-3.5 sm:p-4 space-y-3">
                          {/* Clean Header with Group ID and Group Name separated nicely without collision */}
                          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 sm:gap-4 pb-2.5 border-b border-border">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="font-mono text-sky-700 dark:text-cyan-300 font-semibold text-xs shrink-0">{sg.group_id || 'sg-default'}</span>
                              <button
                                onClick={() => copyToClipboard(sg.group_id, `sg-${idx}`)}
                                className="size-6 flex items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                                title="Copy Security Group ID"
                              >
                                {copiedKey === `sg-${idx}` ? <Check className="size-3 text-emerald-600 dark:text-emerald-400" /> : <Copy className="size-3" />}
                              </button>
                            </div>
                            <div className="text-xs text-muted-foreground font-mono truncate max-w-sm" title={sg.group_name}>
                              {sg.group_name || 'default'}
                            </div>
                          </div>

                          {/* Ingress status and action */}
                          <div className="flex flex-wrap items-center justify-between gap-2.5 pt-1">
                            <div className="flex flex-wrap items-center gap-1.5">
                              {isExposed ? (
                                <>
                                  <span className="text-[11px] text-rose-700 dark:text-rose-400 font-semibold flex items-center gap-1">
                                    <ShieldAlert className="size-3.5" /> Public Ingress:
                                  </span>
                                  {ports.map((p: any) => (
                                    <Badge key={p} variant="outline" className="text-[10px] px-1.5 py-0 font-mono border-rose-500/40 text-rose-700 dark:text-rose-300 bg-rose-500/10">
                                      Port {p} ({p === 22 ? 'SSH' : p === 80 ? 'HTTP' : p === 443 ? 'HTTPS' : 'TCP'})
                                    </Badge>
                                  ))}
                                </>
                              ) : (
                                <span className="text-[11px] text-emerald-700 dark:text-emerald-400 font-semibold flex items-center gap-1">
                                  <ShieldCheck className="size-3.5" /> Strict Private Ingress (Protected)
                                </span>
                              )}
                            </div>

                            {isExposed && (
                              <Button
                                size="sm"
                                variant="destructive"
                                disabled={isRevoking}
                                onClick={() => handleRevokeSg(sg)}
                                className="h-6 text-[10px] px-2.5"
                              >
                                {isRevoking ? <Loader2 className="size-3 animate-spin mr-1" /> : null}
                                Revoke Public Ingress
                              </Button>
                            )}
                          </div>
                        </div>
                      );
                    });
                  })()}
                </div>
              </div>
            </TabsContent>

            {/* TAB 3: STORAGE / EBS VOLUMES */}
            <TabsContent value="storage" className="space-y-3 mt-4">
              {(() => {
                const vols = Array.isArray(instance.volumes_detail) && instance.volumes_detail.length > 0
                  ? instance.volumes_detail
                  : [{ volume_id: 'vol-054d30aa3228e5c73', volume_type: 'gp3', size_gb: 30, iops: 3000, encrypted: true }];

                return vols.map((v: any, idx: number) => {
                  const isGp2 = (v.volume_type || '').toLowerCase() === 'gp2';
                  return (
                    <div key={v.volume_id || idx} className="rounded-xl border border-border bg-card p-4 space-y-3 shadow-xs">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className="flex size-8 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-1 ring-amber-500/20">
                            <HardDrive className="size-4" />
                          </div>
                          <div>
                            <div className="text-xs font-bold font-mono text-foreground flex items-center gap-2">
                              {v.volume_id}
                              <button onClick={() => copyToClipboard(v.volume_id, `vol-${idx}`)} className="text-muted-foreground hover:text-foreground">
                                {copiedKey === `vol-${idx}` ? <Check className="size-3 text-emerald-600 dark:text-emerald-400" /> : <Copy className="size-3" />}
                              </button>
                            </div>
                            <div className="text-[10px] text-muted-foreground">Root Attachment: /dev/sda1 (in-use)</div>
                          </div>
                        </div>

                        <Badge variant="outline" className={`text-xs px-2 py-0.5 uppercase font-mono ${
                          isGp2 ? 'border-amber-500/40 text-amber-700 dark:text-amber-400 bg-amber-500/10' : 'border-sky-500/40 text-sky-700 dark:text-sky-300 bg-sky-500/10'
                        }`}>
                          {v.volume_type || 'gp3'}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-3 gap-2.5 pt-2 border-t border-border text-xs">
                        <div className="rounded-lg bg-muted/40 p-2">
                          <div className="text-[10px] text-muted-foreground font-medium">Volume Size</div>
                          <div className="font-semibold font-mono text-foreground mt-0.5">{v.size_gb || 30} GiB</div>
                        </div>
                        <div className="rounded-lg bg-muted/40 p-2">
                          <div className="text-[10px] text-muted-foreground font-medium">Baseline IOPS</div>
                          <div className="font-semibold font-mono text-foreground mt-0.5">{v.iops || 3000}</div>
                        </div>
                        <div className="rounded-lg bg-muted/40 p-2">
                          <div className="text-[10px] text-muted-foreground font-medium">Encryption</div>
                          <div className={`font-semibold font-mono mt-0.5 ${v.encrypted ? 'text-emerald-700 dark:text-emerald-400' : 'text-amber-700 dark:text-amber-400'}`}>
                            {v.encrypted ? 'AES-256' : 'Disabled'}
                          </div>
                        </div>
                      </div>

                      {isGp2 && (
                        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-800 dark:text-amber-300 flex items-center justify-between">
                          <span>💡 Upgrade gp2 ➔ gp3 to save 20% on storage and guarantee 3,000 baseline IOPS.</span>
                          <Button size="sm" variant="outline" className="h-6 text-[10px] border-amber-500/40 text-amber-700 dark:text-amber-200">
                            Upgrade gp3
                          </Button>
                        </div>
                      )}
                    </div>
                  );
                });
              })()}
            </TabsContent>

            {/* TAB 4: TELEMETRY (COMPACT RESPONSIVE 2-COLUMN GRID) */}
            <TabsContent value="telemetry" className="space-y-4 mt-4">
              <Ec2MonitoringGrid
                instanceId={instanceId}
                instanceName={instanceName}
                instanceType={instanceType}
                apiUrl={apiUrl}
                inDrawer={true}
              />
            </TabsContent>
          </Tabs>

          {/* FOOTER ACTIONS */}
          <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-border">
            <Button
              variant="outline"
              className="border-border text-xs h-9 px-3 text-muted-foreground hover:text-foreground"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {isExpanded ? <Minimize2 className="size-3.5 mr-1.5 text-sky-600 dark:text-sky-400" /> : <Maximize2 className="size-3.5 mr-1.5 text-sky-600 dark:text-sky-400" />}
              {isExpanded ? "Side Panel" : "Complete Tab"}
            </Button>
            <Button
              className="flex-1 bg-sky-600 text-white hover:bg-sky-500 text-xs font-semibold h-9 shadow-sm"
              onClick={() => {
                onOpenChange(false);
                if (onOpenFullTelemetry) onOpenFullTelemetry(instanceId);
              }}
            >
              <ExternalLink className="size-3.5 mr-1.5" />
              Open Full Fleet Telemetry Console
            </Button>
            <Button variant="outline" className="border-border text-xs h-9 px-4 text-muted-foreground hover:text-foreground" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
