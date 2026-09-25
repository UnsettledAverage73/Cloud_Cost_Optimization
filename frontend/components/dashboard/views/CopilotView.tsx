'use client'

import { useState, useEffect, useRef } from 'react'
import { FileText, Loader2, Send, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SectionTitle } from '@/components/dashboard'

function formatInlineMarkdown(text: string): React.ReactNode {
  if (!text) return null
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g)
  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 1) {
      return (
        <code key={index} className="rounded border border-sky-500/20 bg-sky-500/10 px-1.5 py-0.5 font-mono text-xs text-sky-300">
          {part.slice(1, -1)}
        </code>
      )
    }
    if (part.startsWith('**') && part.endsWith('**') && part.length > 3) {
      return (
        <strong key={index} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      )
    }
    return part
  })
}

function MarkdownText({ content }: { content: string }) {
  if (!content) return null
  const lines = content.split('\n')

  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {lines.map((line, i) => {
        const trimmed = line.trim()
        if (!trimmed) return <div key={i} className="h-1" />

        // Header ###
        if (trimmed.startsWith('### ')) {
          return <h4 key={i} className="text-sm font-semibold text-sky-300 mt-2">{trimmed.slice(4)}</h4>
        }
        if (trimmed.startsWith('## ')) {
          return <h3 key={i} className="text-base font-bold text-foreground mt-3">{trimmed.slice(3)}</h3>
        }
        if (trimmed.startsWith('# ')) {
          return <h2 key={i} className="text-lg font-bold text-foreground mt-3">{trimmed.slice(2)}</h2>
        }

        // Bullet point
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          const bulletText = trimmed.slice(2)
          return (
            <div key={i} className="flex items-start gap-2 pl-2">
              <span className="mt-1.5 size-1.5 rounded-full bg-sky-400 shrink-0 shadow-[0_0_6px_rgba(56,189,248,0.8)]" />
              <span>{formatInlineMarkdown(bulletText)}</span>
            </div>
          )
        }

        // Standard line
        return <p key={i}>{formatInlineMarkdown(line)}</p>
      })}
    </div>
  )
}

interface CopilotViewProps {
  apiUrl: (path: string) => string
}

export function CopilotView({ apiUrl }: CopilotViewProps) {
  const [messages, setMessages] = useState<Array<{
    role: 'user' | 'assistant'
    text: string
    model?: string
    tool?: string
    citations?: string[]
    formattedSavings?: string
  }>>([
    {
      role: 'assistant',
      text: "👋 Welcome to **CloudPulse Autonomous FinOps Copilot**, powered by **Groq Cloud LLM** (compound-mini / compound / Qwen 27B) and our unified multi-domain RAG pipeline.\n\nI continuously retrieve and correlate:\n- ⚡ **Live AWS Telemetry** (EC2, EBS, EIP, SGs, CloudWatch, S3)\n- ☸️ **CNCF OpenCost Container Allocations** (pod CPU/RAM efficiency & rightsizing diffs)\n- 🏛️ **FOCUS 1.0 Lakehouse** (DuckDB in-memory OLAP spend analytics)\n- 📚 **AWS Well-Architected Framework & Enterprise Tagging Policies**\n\nAsk me anything or click one of the quick prompts below!",
      model: 'groq/compound-mini',
      citations: ['Live AWS EC2 Telemetry', 'CNCF OpenCost', 'FOCUS 1.0 Lakehouse', 'Well-Architected KB'],
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [ragStatus, setRagStatus] = useState<any>(null)
  const [generatingReport, setGeneratingReport] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Fetch live RAG pipeline telemetry status
  useEffect(() => {
    let cancelled = false
    const fetchRagStatus = async () => {
      try {
        const res = await fetch(apiUrl('/api/v2/copilot/rag/status'))
        if (res.ok) {
          const data = await res.json()
          if (!cancelled) setRagStatus(data)
        }
      } catch {
        // silent failover to default
      }
    }
    fetchRagStatus()
    const interval = setInterval(fetchRagStatus, 20000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [apiUrl])

  const sendMessage = async (queryText: string) => {
    const text = queryText.trim()
    if (!text || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text }])
    setLoading(true)

    try {
      const res = await fetch(apiUrl('/api/v2/copilot/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, prompt: text, history: [] }),
      })
      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.answer || data.response || 'No response received from Copilot.',
          model: data.model || ragStatus?.active_model || 'groq',
          tool: data.tool_called,
          citations: data.citations || data.tool_result?.citations || [],
          formattedSavings: data.formatted_monthly_savings || data.tool_result?.formatted_monthly_savings,
        },
      ])
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `⚠️ Error communicating with Copilot: ${err?.message || err}`,
          model: 'error',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const generateExecutiveReport = async () => {
    if (generatingReport || loading) return
    setGeneratingReport(true)
    setMessages((prev) => [
      ...prev,
      { role: 'user', text: '📊 Generate Executive FinOps & Container Optimization Report across all live infrastructure.' },
    ])

    try {
      const res = await fetch(apiUrl('/api/v2/copilot/rag/recommendations'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ focus_domain: 'all' }),
      })
      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.report_markdown || 'Report generation complete.',
          model: data.model || 'groq/compound-mini',
          tool: 'finops_rag_recommendations',
          citations: data.citations || ['AWS EC2 Telemetry', 'CNCF OpenCost', 'FOCUS 1.0 Lakehouse'],
          formattedSavings: data.formatted_monthly_savings,
        },
      ])
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `⚠️ Report generation failed: ${err?.message || err}`,
          model: 'error',
        },
      ])
    } finally {
      setGeneratingReport(false)
    }
  }

  const chips = [
    'Analyze Kubernetes container rightsizing & idle waste',
    'Show spend breakdown by service (FOCUS 1.0)',
    'Compare m5.2xlarge with Graviton pricing',
    'S3 Intelligent-Tiering & lifecycle optimization',
    'Why did we have a spike in cloud spend?',
    'Generate Terraform PR to downsize idle compute',
    '/audit',
    '/optimize',
    '/forecast',
  ]

  return (
    <>
      <SectionTitle
        eyebrow="Autonomous Copilot & RAG Pipeline"
        title="AI FinOps Architect & Telemetry Intelligence"
        description="Multi-domain sovereign cloud economist powered by Groq LLM inference, CNCF OpenCost, DuckDB FOCUS 1.0 Lakehouse, and TimescaleDB."
        action={
          <div className="flex items-center gap-2">
            <Button
              onClick={generateExecutiveReport}
              disabled={generatingReport || loading}
              variant="outline"
              size="sm"
              className="border-sky-400/30 bg-sky-400/10 text-sky-300 hover:bg-sky-400/20 text-xs"
            >
              {generatingReport ? (
                <>
                  <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                  Synthesizing Report...
                </>
              ) : (
                <>
                  <FileText className="mr-1.5 size-3.5" />
                  Generate Executive Report
                </>
              )}
            </Button>
            <div className="flex items-center gap-2 rounded-full border border-sky-400/30 bg-sky-400/10 px-3 py-1 text-xs text-sky-300">
              <Sparkles className="size-3.5" />
              <span>Backend: <strong>{ragStatus?.active_model || 'Groq LLM'}</strong></span>
            </div>
          </div>
        }
      />

      {/* Real-Time RAG Pipeline Status Bar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-2.5 text-xs shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400">
            <span className="size-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            RAG Pipeline Live
          </span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">
            Model: <strong className="text-foreground font-mono">{ragStatus?.active_model || 'groq/compound-mini'}</strong>
          </span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">
            Policies: <strong className="text-sky-700 dark:text-sky-300">{ragStatus?.retrieval_sources?.indexed_finops_policies ?? 11} Indexed</strong>
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="border-sky-500/20 bg-sky-50 dark:bg-sky-400/5 text-[11px] text-sky-700 dark:text-sky-300">
            AWS Compute: {ragStatus?.retrieval_sources?.compute_nodes ?? 0}
          </Badge>
          <Badge variant="outline" className="border-sky-500/20 bg-sky-50 dark:bg-sky-400/5 text-[11px] text-sky-700 dark:text-sky-300">
            EBS Volumes: {ragStatus?.retrieval_sources?.ebs_volumes ?? 0}
          </Badge>
          <Badge variant="outline" className="border-purple-500/20 bg-purple-50 dark:bg-purple-400/5 text-[11px] text-purple-700 dark:text-purple-300">
            K8s Pods: {ragStatus?.retrieval_sources?.kubernetes_workloads ?? 0}
          </Badge>
          <Badge variant="outline" className="border-amber-500/20 bg-amber-50 dark:bg-amber-400/5 text-[11px] text-amber-700 dark:text-amber-300">
            FOCUS Lakehouse: Active
          </Badge>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {chips.map((chip, i) => (
          <button
            key={i}
            onClick={() => sendMessage(chip)}
            disabled={loading}
            className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition hover:border-sky-500/40 hover:bg-sky-50 dark:hover:bg-sky-400/10 hover:text-sky-700 dark:hover:text-sky-300 disabled:opacity-50 shadow-xs"
          >
            {chip}
          </button>
        ))}
      </div>

      <Card className="flex flex-col border-border bg-card shadow-sm">
        <CardContent className="flex flex-1 flex-col gap-4 p-4 lg:p-6">
          <div className="flex flex-col gap-4 overflow-y-auto" style={{ minHeight: '380px', maxHeight: '520px' }}>
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.role === 'assistant' && (
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sky-50 dark:bg-sky-400/10 text-sky-600 dark:text-sky-300 border border-sky-200 dark:border-sky-400/20">
                    <Sparkles className="size-4" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-xl p-4 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-sky-600 text-white font-medium shadow-xs'
                      : 'border border-border bg-muted/30 text-foreground'
                  }`}
                >
                  {m.role === 'assistant' && (
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                      {m.model && (
                        <span className="rounded bg-muted px-1.5 py-0.5 font-mono">
                          {m.model}
                        </span>
                      )}
                      {m.tool && (
                        <span className="rounded border border-sky-500/20 bg-sky-50 dark:bg-sky-400/10 px-1.5 py-0.5 font-mono text-sky-700 dark:text-sky-300">
                          tool: {m.tool}
                        </span>
                      )}
                      {m.formattedSavings && (
                        <span className="rounded border border-emerald-500/30 bg-emerald-50 dark:bg-emerald-400/10 px-1.5 py-0.5 font-mono text-emerald-700 dark:text-emerald-300">
                          💰 Recoverable: {m.formattedSavings}
                        </span>
                      )}
                    </div>
                  )}
                  {m.role === 'assistant' ? (
                    <MarkdownText content={m.text} />
                  ) : (
                    <div className="whitespace-pre-wrap font-sans leading-relaxed">
                      {m.text}
                    </div>
                  )}
                  {m.role === 'assistant' && m.citations && m.citations.length > 0 && (
                    <div className="mt-3 border-t border-border pt-2 flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Grounded Sources:</span>
                      {m.citations.map((c, ci) => (
                        <span
                          key={ci}
                          className="rounded bg-sky-50 dark:bg-sky-400/10 border border-sky-200 dark:border-sky-400/20 px-2 py-0.5 text-[10px] text-sky-700 dark:text-sky-300 font-mono"
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-3 text-sm text-sky-700 dark:text-sky-300 animate-pulse">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sky-50 dark:bg-sky-400/10 text-sky-600 dark:text-sky-300 border border-sky-200 dark:border-sky-400/30 shadow-xs">
                  <Sparkles className="size-4 animate-spin" />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs">Copilot is synthesizing telemetry across AWS, OpenCost, and FOCUS Lakehouse</span>
                  <span className="flex gap-1">
                    <span className="size-1 rounded-full bg-sky-500 animate-bounce [animation-delay:-0.3s]" />
                    <span className="size-1 rounded-full bg-sky-500 animate-bounce [animation-delay:-0.15s]" />
                    <span className="size-1 rounded-full bg-sky-500 animate-bounce" />
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="mt-4 flex gap-2 border-t border-border pt-4">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
              placeholder="Ask a question about AWS, Kubernetes containers, FOCUS spend, or type /audit, /optimize..."
              disabled={loading}
              className="border-border bg-background text-foreground placeholder:text-muted-foreground"
            />
            <Button
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
              className="bg-sky-600 dark:bg-sky-400 text-white dark:text-slate-950 hover:bg-sky-700 dark:hover:bg-sky-300 font-semibold"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            </Button>
          </div>
        </CardContent>
      </Card>
    </>
  )
}
export default CopilotView
