'use client'

import React, { useState, useEffect } from 'react'
import {
  Loader2,
  Play,
  Terminal,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TableSkeleton } from '@/components/empty-state'
import { SectionTitle } from '@/components/dashboard'
import { formatCurrency, formatInteger } from '@/lib/formatters'
import type { Currency } from '@/types/dashboard'

export function LakehouseView({ currency = 'USD', apiUrl }: { currency: 'USD' | 'INR'; apiUrl: (path: string) => string }) {
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<any>(null);
  const [query, setQuery] = useState(
    'SELECT ServiceName, SUM(EffectiveCost) as TotalSpend, COUNT(*) as ResourceCount FROM focus_costs GROUP BY ServiceName ORDER BY TotalSpend DESC LIMIT 10;'
  );
  const [executing, setExecuting] = useState(false);
  const [queryResult, setQueryResult] = useState<any>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchAnalytics = async () => {
      setLoading(true);
      try {
        const res = await fetch(apiUrl('/api/v2/focus/analytics'));
        if (res.ok && !cancelled) {
          setAnalytics(await res.json());
        }
      } catch (err) {
        console.error('Failed to fetch FOCUS analytics:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchAnalytics();
    return () => {
      cancelled = true;
    };
  }, [apiUrl]);

  const runQuery = async (sqlToRun?: string) => {
    const sql = sqlToRun || query;
    setExecuting(true);
    setQueryError(null);
    try {
      const res = await fetch(apiUrl('/api/v2/focus/query'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: sql }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setQueryError(data.error || 'SQL execution failed');
        setQueryResult(null);
      } else {
        setQueryResult(data);
      }
    } catch (err: any) {
      setQueryError(err?.message || 'Execution error');
      setQueryResult(null);
    } finally {
      setExecuting(false);
    }
  };

  const presets = [
    {
      label: 'By Cloud Service',
      sql: 'SELECT ServiceName, SUM(EffectiveCost) as Spend, COUNT(*) as Resources FROM focus_costs GROUP BY ServiceName ORDER BY Spend DESC;',
    },
    {
      label: 'By Billing Account',
      sql: 'SELECT BillingAccountId, SUM(EffectiveCost) as TotalSpend, COUNT(DISTINCT ServiceName) as Services FROM focus_costs GROUP BY BillingAccountId;',
    },
    {
      label: 'Top Cost Drivers',
      sql: 'SELECT ResourceID, ServiceName, EffectiveCost, RegionName FROM focus_costs ORDER BY EffectiveCost DESC LIMIT 5;',
    },
    {
      label: 'By Region',
      sql: 'SELECT RegionName, SUM(EffectiveCost) as Spend FROM focus_costs GROUP BY RegionName ORDER BY Spend DESC;',
    },
  ];

  return (
    <>
      <SectionTitle
        eyebrow="Zero-Copy Lakehouse"
        title="DuckDB FOCUS 1.0 SQL Analytics"
        description="Sub-millisecond analytical queries directly over normalized FinOps Open Cost & Usage Specification (FOCUS 1.0) datasets."
        status={
          <Badge variant="outline" className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            DuckDB Parquet Engine
          </Badge>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <span className="text-xs text-muted-foreground">Tracked Cloud Services</span>
            <div className="mt-3 text-2xl font-bold text-cyan-300">
              {analytics?.spend_by_service?.length || 3}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Normalized FOCUS 1.0 services</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <span className="text-xs text-muted-foreground">Billing Accounts</span>
            <div className="mt-3 text-2xl font-bold">
              {analytics?.spend_by_account?.length || 1}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">Multi-tenant sovereign accounts</div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70">
          <CardContent className="p-5">
            <span className="text-xs text-muted-foreground">Primary Spend Driver</span>
            <div className="mt-3 truncate text-xl font-bold text-emerald-300">
              {analytics?.spend_by_service?.[0]?.ServiceName || 'Compute (EC2)'}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {formatCurrency(analytics?.spend_by_service?.[0]?.TotalEffectiveCost, currency)}/mo run-rate
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Card className="border-white/8 bg-card/70 lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base font-semibold">Spend by Cloud Service</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {(analytics?.spend_by_service || []).map((s: any, idx: number) => (
              <div key={`${s.ServiceName}-${idx}`} className="rounded-lg border border-white/8 bg-white/5 p-3 text-xs">
                <div className="flex items-center justify-between font-medium">
                  <span className="truncate text-muted-foreground">{s.ServiceName}</span>
                  <span className="font-semibold text-cyan-300">
                    {formatCurrency(s.TotalEffectiveCost, currency)}
                  </span>
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground/80">
                  {s.ResourceCount} resources · {s.ProviderName || 'AWS'}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70 lg:col-span-2">
          <CardHeader>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <Terminal className="size-4 text-cyan-400" />
                DuckDB FOCUS 1.0 SQL Query Runner
              </CardTitle>
              <div className="flex flex-wrap items-center gap-1.5">
                {presets.map(p => (
                  <Button
                    key={p.label}
                    size="sm"
                    variant="ghost"
                    className="h-7 border border-white/8 px-2 text-[11px] text-cyan-300 hover:bg-cyan-400/10"
                    onClick={() => {
                      setQuery(p.sql);
                      runQuery(p.sql);
                    }}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="relative">
              <textarea
                value={query}
                onChange={e => setQuery(e.target.value)}
                className="h-28 w-full resize-none rounded-lg border border-white/10 bg-black/60 p-3 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:border-cyan-400 focus:outline-none"
                placeholder="Enter SQL query against 'focus_costs' table..."
              />
              <Button
                size="sm"
                className="absolute bottom-3 right-3 bg-cyan-400 text-slate-950 hover:bg-cyan-300"
                onClick={() => runQuery()}
                disabled={executing || !query.trim()}
              >
                {executing ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Play className="mr-1 size-3" />}
                Run SQL
              </Button>
            </div>

            {queryError && (
              <div className="rounded-lg border border-red-400/20 bg-red-400/10 p-3 text-xs text-red-300">
                {queryError}
              </div>
            )}

            {executing ? (
              <div className="pt-2">
                <TableSkeleton rows={4} cols={4} />
              </div>
            ) : queryResult ? (
              <div className="flex flex-col gap-2 pt-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Returned {queryResult.row_count || queryResult.rows?.length || 0} rows</span>
                  <span className="font-mono text-[11px] text-cyan-300">Engine: DuckDB in-memory</span>
                </div>
                <div className="max-h-60 overflow-auto rounded-lg border border-white/8">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-white/8 hover:bg-transparent">
                        {(queryResult.columns || Object.keys(queryResult.rows?.[0] || {})).map((col: string) => (
                          <TableHead key={col} className="text-xs font-semibold text-cyan-300">{col}</TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(queryResult.rows || []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={(queryResult.columns || ['Result']).length} className="py-8 text-center text-xs text-muted-foreground">
                            Query executed successfully with 0 rows returned.
                          </TableCell>
                        </TableRow>
                      ) : (
                        (queryResult.rows || []).map((row: any, rIdx: number) => (
                          <TableRow key={rIdx} className="border-white/8">
                            {(queryResult.columns || Object.keys(row)).map((col: string) => (
                              <TableCell key={col} className="font-mono text-xs">
                                {typeof row[col] === 'number' && col.toLowerCase().includes('cost')
                                  ? formatCurrency(row[col], currency)
                                  : String(row[col] ?? '')}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </>
  );
}


export default LakehouseView
