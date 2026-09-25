'use client'

export function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-border bg-card/95 backdrop-blur-md p-3 text-xs shadow-xl text-card-foreground">
      <div className="mb-2 font-medium text-muted-foreground">{label}</div>
      <div className="space-y-1">
        {payload.map((p: any) => (
          <div key={p.dataKey} className="flex items-center justify-between gap-6">
            <span className="font-medium" style={{ color: p.color }}>{p.name}</span>
            <b className="font-mono text-foreground">${p.value}k</b>
          </div>
        ))}
      </div>
    </div>
  )
}
