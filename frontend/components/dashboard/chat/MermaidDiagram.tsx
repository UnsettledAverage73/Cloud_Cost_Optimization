'use client'

import React, { useEffect, useRef, useState } from 'react'
import { Check, Copy, Eye, Code2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface MermaidDiagramProps {
  chart: string
  id?: string
}

export function MermaidDiagram({ chart, id }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [showRaw, setShowRaw] = useState(false)
  const [copied, setCopied] = useState(false)

  const diagramId = useRef(id || `mermaid-${Math.random().toString(36).substring(2, 9)}`).current

  useEffect(() => {
    let isMounted = true

    const renderChart = async () => {
      try {
        setError(null)
        const mermaid = (await import('mermaid')).default

        // Configure strict monochrome theme
        mermaid.initialize({
          startOnLoad: false,
          theme: 'neutral',
          themeVariables: {
            darkMode: true,
            background: '#000000',
            primaryColor: '#18181b',
            primaryTextColor: '#ffffff',
            primaryBorderColor: '#3f3f46',
            lineColor: '#ffffff',
            secondaryColor: '#27272a',
            tertiaryColor: '#09090b',
            nodeBorder: '#52525b',
            mainBkg: '#09090b',
            clusterBkg: '#18181b',
            clusterBorder: '#3f3f46',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            fontSize: '12px',
          },
          securityLevel: 'loose',
        })

        // Clean chart input
        const cleanChart = chart.trim()
        const { svg: renderedSvg } = await mermaid.render(diagramId, cleanChart)

        if (isMounted) {
          setSvg(renderedSvg)
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || 'Failed to render diagram')
        }
      }
    }

    renderChart()

    return () => {
      isMounted = false
    }
  }, [chart, diagramId])

  const copyChart = () => {
    navigator.clipboard.writeText(chart)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      {/* Diagram Header Toolbar */}
      <div className="flex items-center justify-between border-b border-border bg-muted/40 px-3 py-1.5 text-xs">
        <div className="flex items-center gap-2 font-mono text-[11px] text-foreground font-medium">
          <span className="size-2 rounded-full bg-foreground" />
          <span>Architecture Topology Diagram</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowRaw(!showRaw)}
            className="h-6 px-2 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted"
          >
            {showRaw ? <Eye className="mr-1 size-3" /> : <Code2 className="mr-1 size-3" />}
            {showRaw ? 'Preview' : 'Mermaid HCL'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={copyChart}
            className="h-6 px-2 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted"
          >
            {copied ? <Check className="mr-1 size-3" /> : <Copy className="mr-1 size-3" />}
            {copied ? 'Copied' : 'Copy'}
          </Button>
        </div>
      </div>

      {/* Main Diagram Area */}
      <div className="p-4">
        {showRaw ? (
          <pre className="overflow-x-auto rounded-lg border border-border bg-background p-3 font-mono text-xs text-foreground">
            {chart}
          </pre>
        ) : error ? (
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/20 p-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <AlertTriangle className="size-4" />
              <span>Diagram Syntax Fallback</span>
            </div>
            <pre className="overflow-x-auto font-mono text-xs">{chart}</pre>
          </div>
        ) : svg ? (
          <div
            ref={containerRef}
            className="flex justify-center overflow-x-auto py-2 [&>svg]:max-w-full [&>svg]:h-auto text-foreground"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        ) : (
          <div className="flex items-center justify-center py-6 text-xs text-muted-foreground animate-pulse font-mono">
            Rendering architectural topology...
          </div>
        )}
      </div>
    </div>
  )
}
export default MermaidDiagram
