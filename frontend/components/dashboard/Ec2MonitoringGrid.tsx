'use client';

import React, { useState } from 'react';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import {
  Cpu, HardDrive, Network, Activity, Zap, ShieldAlert,
  Radio, CheckCircle2, AlertTriangle, Layers, Server, RefreshCw
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useRealtimeTelemetry } from '@/hooks/useRealtimeTelemetry';
import { AgentDeploymentModal } from './AgentDeploymentModal';

interface Ec2MonitoringGridProps {
  instanceId: string;
  instanceName?: string;
  instanceType?: string;
  apiUrl?: (path: string) => string;
  inDrawer?: boolean;
}

function formatBytes(bytes: number) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function Ec2MonitoringGrid({
  instanceId,
  instanceName = 'EC2 Instance',
  instanceType = 't3.micro',
  apiUrl,
  inDrawer = false,
}: Ec2MonitoringGridProps) {
  const {
    points,
    isLive,
    connectionMode,
    cwAgentEnabled,
    setCwAgentEnabled,
    timeframe,
    setTimeframe,
    latestPoint,
  } = useRealtimeTelemetry(instanceId, 60, apiUrl);

  const [agentModalOpen, setAgentModalOpen] = useState(false);
  const timeframes: Array<'1h' | '3h' | '12h' | '1d' | '3d' | '1w'> = ['1h', '3h', '12h', '1d', '3d', '1w'];

  // Current stats
  const curCpu = latestPoint?.cpu ?? 0;
  const curMem = latestPoint?.mem ?? 0;
  const curDisk = latestPoint?.disk ?? 0;
  const curNetIn = latestPoint?.net_in_bytes ?? 0;
  const curNetOut = latestPoint?.net_out_bytes ?? 0;
  const curPktsIn = latestPoint?.packets_in ?? 0;
  const curPktsOut = latestPoint?.packets_out ?? 0;
  const curCredits = latestPoint?.cpu_credits ?? 144.0;

  return (
    <div className="space-y-4">
      {/* Real-Time Monitoring Header & Controls */}
      <div className={`flex flex-col gap-2.5 rounded-xl border border-white/10 bg-white/[0.03] p-3 sm:flex-row sm:items-center sm:justify-between ${inDrawer ? 'text-xs' : ''}`}>
        <div className="flex items-center gap-2.5">
          <div className="relative flex size-2.5 shrink-0">
            {isLive ? (
              <>
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex size-2.5 rounded-full bg-emerald-500" />
              </>
            ) : (
              <span className="relative inline-flex size-2.5 rounded-full bg-amber-500" />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold text-foreground">
                AWS Live Telemetry
              </span>
              <Badge
                variant="outline"
                className={`text-[9px] px-1.5 py-0 font-mono ${
                  connectionMode === 'websocket'
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                    : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                }`}
              >
                {connectionMode === 'websocket' ? 'LIVE STREAM (2s)' : 'FALLBACK POLLING'}
              </Badge>
            </div>
            {!inDrawer && (
              <p className="text-[11px] text-muted-foreground truncate">
                Instance: <span className="font-mono text-cyan-300">{instanceId}</span> ({instanceName} • {instanceType})
              </p>
            )}
          </div>
        </div>

        {/* Timeframe selector & Agent Hub / CWAgent */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Agent Deployment Hub Button */}
          <button
            onClick={() => setAgentModalOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-cyan-500/30 bg-cyan-500/15 hover:bg-cyan-500/25 px-2.5 py-1 text-[10px] font-semibold text-cyan-200 transition-all shadow-[0_0_12px_rgba(6,182,212,0.15)]"
          >
            <Zap className="size-3 text-cyan-400 animate-pulse" />
            <span>⚡️ Real-Time Agent Hub</span>
          </button>

          {/* CWAgent Toggle */}
          <button
            onClick={() => setCwAgentEnabled(!cwAgentEnabled)}
            className={`flex items-center gap-1.5 rounded-lg border px-2 py-1 text-[10px] font-medium transition-colors ${
              cwAgentEnabled
                ? 'border-purple-500/40 bg-purple-500/15 text-purple-300'
                : 'border-white/10 bg-white/5 text-muted-foreground hover:bg-white/10'
            }`}
          >
            <Layers className="size-3 text-purple-400" />
            <span>In-Guest CWAgent</span>
            <span className={`size-1.5 rounded-full ${cwAgentEnabled ? 'bg-purple-400' : 'bg-white/30'}`} />
          </button>

          {/* Timeframe Presets */}
          <div className="flex items-center rounded-lg border border-white/10 bg-white/5 p-0.5">
            {timeframes.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                  timeframe === tf
                    ? 'bg-cyan-500 text-slate-950 font-semibold shadow-sm'
                    : 'text-muted-foreground hover:text-white'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 8-Card Live Metric Grid (Exact AWS EC2 Console Specification) */}
      <div className={inDrawer ? "grid grid-cols-1 sm:grid-cols-2 gap-2.5" : "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"}>

        {/* CARD 1: CPU Utilization (%) */}
        <Card className="border-white/8 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-3">
            <CardTitle className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <Cpu className="size-3.5 text-cyan-400" />
              1. CPU Utilization
            </CardTitle>
            <div className="flex items-center gap-1 font-mono text-xs font-bold text-cyan-300">
              {curCpu.toFixed(1)}%
            </div>
          </CardHeader>
          <div className="px-3 pb-1 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Path A: Hypervisor</span>
            {curCpu < 5.0 ? (
              <span className="font-semibold text-amber-400 flex items-center gap-1">
                <AlertTriangle className="size-2.5" /> Idle Waste (&lt;5%)
              </span>
            ) : curCpu > 80.0 ? (
              <span className="font-semibold text-red-400 flex items-center gap-1">
                <AlertTriangle className="size-2.5" /> High Load (&gt;80%)
              </span>
            ) : (
              <span className="text-emerald-400 font-medium">Optimal</span>
            )}
          </div>
          <CardContent className="h-28 p-1 pt-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={points} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <defs>
                  <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis domain={[0, 100]} tick={{ fontSize: 9 }} stroke="#64748b" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px', borderRadius: '6px' }}
                  formatter={(val: any) => [`${val}%`, 'CPU Utilization']}
                />
                <Area type="monotone" dataKey="cpu" stroke="#06b6d4" strokeWidth={2} fill="url(#cpuGrad)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* CARD 2: Memory Utilization (%) */}
        <Card className="border-white/8 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-3">
            <CardTitle className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <Activity className="size-3.5 text-purple-400" />
              2. Memory Utilization
            </CardTitle>
            <div className="flex items-center gap-1 font-mono text-xs font-bold text-purple-300">
              {cwAgentEnabled ? `${curMem.toFixed(1)}%` : 'N/A'}
            </div>
          </CardHeader>
          <div className="px-3 pb-1 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Path B: In-Guest CWAgent</span>
            <span className={cwAgentEnabled ? 'text-purple-400' : 'text-amber-400'}>
              {cwAgentEnabled ? 'In-Guest Active' : 'Agent Disabled'}
            </span>
          </div>
          <CardContent className="h-28 p-1 pt-0">
            {cwAgentEnabled ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={points} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="memGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#a855f7" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="timestamp" hide />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 9 }} stroke="#64748b" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px', borderRadius: '6px' }}
                    formatter={(val: any) => [`${val}%`, 'RAM Used']}
                  />
                  <Area type="monotone" dataKey="mem" stroke="#a855f7" strokeWidth={2} fill="url(#memGrad)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center p-2 text-center text-[11px] text-muted-foreground">
                <span className="font-semibold text-white/80">Hypervisor Isolation</span>
                <span className="text-[10px] text-muted-foreground mt-0.5">Toggle CWAgent above to view RAM</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* CARD 3: Disk Space Used (%) */}
        <Card className="border-white/8 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-3">
            <CardTitle className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <HardDrive className="size-3.5 text-amber-400" />
              3. Disk Space Used
            </CardTitle>
            <div className="flex items-center gap-1 font-mono text-xs font-bold text-amber-300">
              {cwAgentEnabled ? `${curDisk.toFixed(1)}%` : 'N/A'}
            </div>
          </CardHeader>
          <div className="px-3 pb-1 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Path B: Root Volume /</span>
            {curDisk > 85.0 ? (
              <span className="font-semibold text-red-400">Expand Warning (&gt;85%)</span>
            ) : (
              <span className="text-emerald-400">Healthy</span>
            )}
          </div>
          <CardContent className="h-28 p-1 pt-0">
            {cwAgentEnabled ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={points} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="diskGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="timestamp" hide />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 9 }} stroke="#64748b" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px', borderRadius: '6px' }}
                    formatter={(val: any) => [`${val}%`, 'Disk Space']}
                  />
                  <Area type="monotone" dataKey="disk" stroke="#f59e0b" strokeWidth={2} fill="url(#diskGrad)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center p-2 text-center text-[11px] text-muted-foreground">
                <span className="font-semibold text-white/80">In-Guest FS Metrics</span>
                <span className="text-[10px] text-muted-foreground mt-0.5">Toggle CWAgent to view mounts</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* CARD 4: Network In (Bytes) */}
        <Card className="border-white/8 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-3">
            <CardTitle className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <Network className="size-3.5 text-blue-400" />
              4. Network In
            </CardTitle>
            <div className="flex items-center gap-1 font-mono text-xs font-bold text-blue-300">
              {formatBytes(curNetIn)}/s
            </div>
          </CardHeader>
          <div className="px-3 pb-1 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Path A: EC2 Hypervisor</span>
            <span className="text-cyan-400">Ingress B/s</span>
          </div>
          <CardContent className="h-28 p-1 pt-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis tick={{ fontSize: 9 }} stroke="#64748b" tickFormatter={(v) => formatBytes(v)} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px', borderRadius: '6px' }}
                  formatter={(val: any) => [`${formatBytes(val)}/s`, 'Network In']}
                />
                <Line type="monotone" dataKey="net_in_bytes" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* CARD 5: Network Out (Bytes) */}
        <Card className="border-white/8 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-3">
            <CardTitle className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <Network className="size-3.5 text-indigo-400" />
              5. Network Out
            </CardTitle>
            <div className="flex items-center gap-1 font-mono text-xs font-bold text-indigo-300">
              {formatBytes(curNetOut)}/s
            </div>
          </CardHeader>
          <div className="px-3 pb-1 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Path A: EC2 Hypervisor</span>
            <span className="text-indigo-400">Egress Egress B/s</span>
          </div>
          <CardContent className="h-28 p-1 pt-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis tick={{ fontSize: 9 }} stroke="#64748b" tickFormatter={(v) => formatBytes(v)} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px', borderRadius: '6px' }}
                  formatter={(val: any) => [`${formatBytes(val)}/s`, 'Network Out']}
                />
                <Line type="monotone" dataKey="net_out_bytes" stroke="#6366f1" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* CARD 6: Network Packets In */}
        <Card className="border-white/8 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-3">
            <CardTitle className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <Radio className="size-3.5 text-emerald-400" />
              6. Network Packets In
            </CardTitle>
            <div className="flex items-center gap-1 font-mono text-xs font-bold text-emerald-300">
              {curPktsIn.toLocaleString()} p/s
            </div>
          </CardHeader>
          <div className="px-3 pb-1 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>DDoS / Flood Baseline</span>
            <span className="text-emerald-400">Normal</span>
          </div>
          <CardContent className="h-28 p-1 pt-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={points} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis tick={{ fontSize: 9 }} stroke="#64748b" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px', borderRadius: '6px' }}
                  formatter={(val: any) => [`${val} p/s`, 'Packets In']}
                />
                <Bar dataKey="packets_in" fill="#10b981" radius={[2, 2, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* CARD 7: Network Packets Out */}
        <Card className="border-white/8 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-3">
            <CardTitle className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <Radio className="size-3.5 text-teal-400" />
              7. Network Packets Out
            </CardTitle>
            <div className="flex items-center gap-1 font-mono text-xs font-bold text-teal-300">
              {curPktsOut.toLocaleString()} p/s
            </div>
          </CardHeader>
          <div className="px-3 pb-1 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Outbound Packets</span>
            <span className="text-teal-400">Normal</span>
          </div>
          <CardContent className="h-28 p-1 pt-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={points} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis tick={{ fontSize: 9 }} stroke="#64748b" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px', borderRadius: '6px' }}
                  formatter={(val: any) => [`${val} p/s`, 'Packets Out']}
                />
                <Bar dataKey="packets_out" fill="#14b8a6" radius={[2, 2, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* CARD 8: CPU Credit Balance */}
        <Card className="border-white/8 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-3">
            <CardTitle className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <Zap className="size-3.5 text-pink-400" />
              8. CPU Credit Balance
            </CardTitle>
            <div className="flex items-center gap-1 font-mono text-xs font-bold text-pink-300">
              {curCredits.toFixed(1)}
            </div>
          </CardHeader>
          <div className="px-3 pb-1 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Burstable (t2/t3/t4g)</span>
            <span className={curCredits < 30 ? 'text-red-400 font-semibold' : 'text-emerald-400'}>
              {curCredits < 30 ? 'Low Credits' : 'Healthy Balance'}
            </span>
          </div>
          <CardContent className="h-28 p-1 pt-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis domain={[0, 150]} tick={{ fontSize: 9 }} stroke="#64748b" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px', borderRadius: '6px' }}
                  formatter={(val: any) => [`${val} credits`, 'Balance']}
                />
                <Line type="monotone" dataKey="cpu_credits" stroke="#ec4899" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

      </div>

      {/* Zero-Config Real-Time Agent Deployment & Consent Hub Modal */}
      <AgentDeploymentModal
        open={agentModalOpen}
        onOpenChange={setAgentModalOpen}
        apiUrl={apiUrl}
        activeInstanceId={instanceId}
      />
    </div>
  );
}
