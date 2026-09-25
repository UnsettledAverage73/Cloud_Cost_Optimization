'use client'

import { useState } from 'react'
import { Activity, Server } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { EmptyState, ChartSkeleton } from '@/components/empty-state'
import { SectionTitle, SectionStatusBadge, Ec2MonitoringGrid } from '@/components/dashboard'
import { ChartTooltip } from '@/components/dashboard/ChartTooltip'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Timeframe, ComputeNode, TelemetryPoint } from '@/types/dashboard'

interface TelemetryViewProps {
  accessMode?: string
  telemetry: TelemetryPoint[]
  timeframe: Timeframe
  setTimeframe: (tf: Timeframe) => void
  sectionStatus?: 'idle' | 'loading' | 'ready' | 'partial' | 'error'
  nodes: ComputeNode[]
  apiUrl: (path: string) => string
}

export function TelemetryView({
  telemetry = [],
  timeframe = '24h',
  setTimeframe,
  sectionStatus = 'idle',
  nodes = [],
  apiUrl,
}: TelemetryViewProps) {
  const nodeList = Array.isArray(nodes) && nodes.length > 0 ? nodes : [
    { instance_id: 'i-036358db85d245e3a', name: 'api-gateway-prod', instance_type: 't3.micro' },
    { instance_id: 'i-09f81a2b3c4d5e6f7', name: 'worker-node-01', instance_type: 't3.medium' },
  ]
  const [selectedInstId, setSelectedInstId] = useState<string>(nodeList[0]?.instance_id || 'i-036358db85d245e3a')
  const activeNode = nodeList.find((n: any) => n.instance_id === selectedInstId) || nodeList[0]

  return (
    <>
      <SectionTitle
        eyebrow="Live Telemetry & Metrics"
        title="AWS EC2 Real-Time Monitoring Console"
        description="Sub-second streaming of CPU, Memory, Disk, and Network telemetry for every active cloud instance."
        status={<SectionStatusBadge status={sectionStatus} />}
        action={
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground font-medium">Select Instance:</span>
            <Select
              value={selectedInstId}
              onValueChange={(val) => {
                if (val) setSelectedInstId(val)
              }}
            >
              <SelectTrigger className="w-56 border-border bg-card text-xs font-mono text-sky-700 dark:text-sky-300">
                <Server className="size-3.5 mr-1 text-sky-600 dark:text-sky-400" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {nodeList.map((n: any) => (
                  <SelectItem key={n.instance_id} value={n.instance_id} className="text-xs font-mono">
                    {n.name ? `${n.name} (${n.instance_id})` : n.instance_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
      />

      {/* 8-Card Real-Time Live Monitoring Grid */}
      <Ec2MonitoringGrid
        instanceId={selectedInstId}
        instanceName={activeNode?.name || 'EC2 Instance'}
        instanceType={(activeNode as any)?.instance_type || (activeNode as any)?.type || 't3.micro'}
        apiUrl={apiUrl}
      />

      {/* Fleet-Wide Aggregated Signals */}
      <div className="mt-8 pt-6 border-t border-border space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Fleet-Wide Aggregated Telemetry</h3>
            <p className="text-xs text-muted-foreground">Historical utilization patterns across all cluster nodes</p>
          </div>
          <ToggleGroup
            value={[timeframe]}
            onValueChange={(v) => {
              if (v?.[0]) setTimeframe(v[0] as Timeframe)
            }}
          >
            <ToggleGroupItem value="1h">1H</ToggleGroupItem>
            <ToggleGroupItem value="6h">6H</ToggleGroupItem>
            <ToggleGroupItem value="24h">24H</ToggleGroupItem>
            <ToggleGroupItem value="7d">7D</ToggleGroupItem>
          </ToggleGroup>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            ['CPU utilization', 'cpu', 'CPU %', 'line'],
            ['Memory usage', 'mem', 'Memory %', 'area'],
            ['Network traffic', 'network', 'MB/s', 'network'],
            ['Disk IOPS', 'iops', 'IOPS', 'bar'],
          ].map(([title, key, unit, kind]) => (
            <Card key={title} className="border-border bg-card shadow-xs">
              <CardHeader className="flex-row items-center justify-between pb-2">
                <div>
                  <CardTitle className="text-sm font-semibold">{title}</CardTitle>
                  <p className="mt-1 text-xs text-muted-foreground">{unit} · last {timeframe}</p>
                </div>
                <span className="size-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
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
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.1)" vertical={false} />
                        <XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} minTickGap={16} interval="preserveStartEnd" />
                        <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} width={30} />
                        <Tooltip content={<ChartTooltip />} />
                        <Bar dataKey="read" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="write" fill="var(--chart-2)" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    ) : (
                      <LineChart data={telemetry}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.1)" vertical={false} />
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
      </div>
    </>
  )
}
export default TelemetryView
