'use client'

import { Download, MoreHorizontal, Search, Server, SlidersHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState, TableSkeleton } from '@/components/empty-state'
import { SectionTitle, SectionStatusBadge } from '@/components/dashboard'
import { formatCurrency } from '@/lib/formatters'
import type { Currency, ComputeNode } from '@/types/dashboard'

interface InventoryViewProps {
  accessMode?: string
  search: string
  setSearch: (search: string) => void
  status: string
  setStatus: (status: string) => void
  filteredNodes: ComputeNode[]
  setSelectedNode: (node: ComputeNode | null) => void
  sectionStatus?: 'idle' | 'loading' | 'ready' | 'partial' | 'error'
  apiUrl: (path: string) => string
  currency?: Currency
}

export function InventoryView({
  search,
  setSearch,
  status,
  setStatus,
  filteredNodes = [],
  setSelectedNode,
  sectionStatus = 'idle',
  apiUrl,
  currency = 'USD',
}: InventoryViewProps) {
  const pdfUrl = typeof apiUrl === 'function'
    ? apiUrl(`/api/v2/analytics/pov/report.pdf?currency=${currency || 'USD'}&inline=true`)
    : `/api/v2/analytics/pov/report.pdf?currency=${currency || 'USD'}&inline=true`

  return (
    <>
      <SectionTitle
        eyebrow="Inventory"
        title="Compute & storage"
        description="Track every node, volume, and exposure across your estate."
        status={<SectionStatusBadge status={sectionStatus} />}
        action={
          <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" className="border-sky-500/30 text-sky-700 dark:text-sky-300 hover:bg-sky-500/10 text-xs font-medium">
              <Download className="mr-1.5 size-3.5" />Export Complete Cost & Inventory PDF
            </Button>
          </a>
        }
      />
      <div className="mb-4 flex flex-col sm:flex-row gap-3">
        <div className="relative w-full sm:flex-1">
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search instances, IDs, IPs, types..."
            className="border-border bg-card pl-9 text-sm focus:border-sky-500/50 shadow-xs"
          />
        </div>
        <Select value={status} onValueChange={(val) => setStatus(val ?? 'all')}>
          <SelectTrigger className="w-full sm:w-40 border-border bg-card text-sm shadow-xs">
            <SlidersHorizontal className="mr-2 size-3.5 text-muted-foreground" />
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
      <Card className="overflow-hidden border border-border bg-card shadow-xs">
        {sectionStatus === 'loading' ? (
          <TableSkeleton rows={6} cols={8} />
        ) : (!Array.isArray(filteredNodes) || filteredNodes.length === 0) ? (
          <EmptyState
            icon={Server}
            title="No compute instances found"
            description={
              search || status !== 'all'
                ? 'No instances match your current filter criteria.'
                : 'No live EC2 nodes discovered in this connected region.'
            }
            action={
              search || status !== 'all' ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearch('')
                    setStatus('all')
                  }}
                >
                  Clear filters
                </Button>
              ) : undefined
            }
            className="my-6 border-0"
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-b border-border bg-muted/30 hover:bg-muted/30">
                <TableHead className="w-10" />
                <TableHead className="font-semibold text-foreground">Instance</TableHead>
                <TableHead className="font-semibold text-foreground">Status</TableHead>
                <TableHead className="font-semibold text-foreground">Type</TableHead>
                <TableHead className="font-semibold text-foreground">Region</TableHead>
                <TableHead className="font-semibold text-foreground">Public IP</TableHead>
                <TableHead className="font-semibold text-foreground">Volumes</TableHead>
                <TableHead className="text-right font-semibold text-foreground">Monthly cost</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredNodes.map((n: any) => (
                <TableRow
                  key={n.instance_id}
                  onClick={() => setSelectedNode(n)}
                  className="cursor-pointer border-b border-border hover:bg-muted/50 transition-colors duration-150"
                >
                  <TableCell>
                    <input
                      type="checkbox"
                      aria-label={`Select ${n.name}`}
                      className="accent-sky-600 rounded"
                      onClick={(e) => e.stopPropagation()}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="font-semibold text-foreground tracking-tight">{n.name}</div>
                    <div className="font-mono text-[11px] text-muted-foreground">{n.instance_id}</div>
                  </TableCell>
                  <TableCell>
                    <span className="flex items-center gap-2 text-xs capitalize">
                      <span className="relative flex size-2">
                        {n.state === 'running' && (
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                        )}
                        <span
                          className={`relative inline-flex rounded-full size-2 ${
                            n.state === 'running' ? 'bg-emerald-500' : n.state === 'stopped' ? 'bg-amber-500' : 'bg-rose-500'
                          }`}
                        />
                      </span>
                      <span className={n.state === 'running' ? 'text-emerald-700 dark:text-emerald-300 font-semibold' : 'text-muted-foreground'}>
                        {n.state}
                      </span>
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 font-mono text-[11px]">
                      {n.instance_type || n.type || '—'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground font-medium">{n.region}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{n.public_ip || '—'}</TableCell>
                  <TableCell className="text-xs text-muted-foreground font-medium">{n.volumes} attached</TableCell>
                  <TableCell className="text-right font-mono text-xs font-bold text-foreground">
                    {formatCurrency(Number(n.cost), currency)}
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" aria-label="More actions" onClick={(e) => e.stopPropagation()}>
                      <MoreHorizontal className="size-4 text-muted-foreground" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </>
  )
}
export default InventoryView
