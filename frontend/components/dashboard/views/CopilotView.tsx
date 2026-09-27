'use client'

import { useState, useEffect, useRef } from 'react'
import { FileText, Loader2, Send, Sparkles, Cpu, ShieldCheck, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SectionTitle } from '@/components/dashboard'

import { RichChatRenderer } from '@/components/dashboard/chat/RichChatRenderer'

interface CopilotViewProps {
  apiUrl: (path: string) => string
}

export function CopilotView({ apiUrl }: CopilotViewProps) {
  const [messages, setMessages] = useState<Array<{
    role: 'user' | 'assistant'
    text: string
    model?: string
    tool?: string
    confidence?: number
    decisionProvider?: string
    latencyMs?: number
    executionPlan?: string[]
  }>>([
    {
      role: 'assistant',
      text: "👋 Welcome to **Jew System Architect**, the autonomous One-Model Cloud Architect agent.\n\nPowered by **SemIf (OpenJev open-source)** for sub-millisecond System-1 tool decision-making and instrumented with **LangSmith** tracing.\n\nI continuously perceive and optimize:\n- ⚡ **Live AWS CloudWatch Telemetry** (P95/P99 CPU, Memory, IOPS series)\n- 🛡️ **CloudTrail Spike Forensics** (Principal actors, CI/CD pipeline attribution)\n- 💰 **Real-Time AWS Pricing Rate Cards** (Graviton ARM64 rightsizing ROI)\n- 🛠️ **Automated OpenTofu / Terraform PRs** (Zero-downtime safe IaC remediation)\n- ⏱️ **SLA Safety Watchdog** (60-minute automated rollback guardrails)\n\nAsk me anything or select a prompt below!",
      model: 'SemIf Decision Engine',
      decisionProvider: 'SemIf (OpenJev open-source)',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendMessage = async (queryText: string) => {
    const text = queryText.trim()
    if (!text || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text }])
    setLoading(true)

    try {
      const res = await fetch(apiUrl('/api/v2/architect/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, query: text, history: [] }),
      })
      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.answer || 'No response received from Architect.',
          model: data.provider || 'SemIf',
          tool: data.tool_called,
          confidence: data.confidence,
          decisionProvider: data.provider,
          latencyMs: data.latency_ms,
          executionPlan: data.execution_plan || [],
        },
      ])
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `⚠️ Error communicating with Jew System Architect: ${err?.message || err}`,
          model: 'error',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const chips = [
    'Compare m5.2xlarge with Graviton pricing',
    'Why did our compute cost spike on Friday?',
    'Generate a terraform pull request to downsize idle compute',
    'Inspect CloudWatch P95 telemetry series',
    'Check SLA safety guardrail before modifying nodes',
    'List unattached EBS volumes and exposed security groups',
  ]

  return (
    <>
      <SectionTitle
        eyebrow="One-Model AI Architect Console"
        title="Jew System Architect"
        description="Autonomous cloud system architect driven by SemIf (OpenJev) System-1 decision routing and LangSmith observability."
        action={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-foreground shadow-xs">
              <Zap className="size-3.5 text-foreground" />
              <span>Decision Engine: <strong>SemIf (OpenJev)</strong></span>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground shadow-xs">
              <ShieldCheck className="size-3.5 text-foreground" />
              <span>LangSmith: <strong>Active</strong></span>
            </div>
          </div>
        }
      />

      {/* Decision Status Bar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-2.5 text-xs shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-1.5 font-medium text-foreground">
            <span className="size-2 rounded-full bg-foreground" />
            Decision Engine Online
          </span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">
            Model: <strong className="text-foreground font-mono">SemIf (OpenJev / Jev drop-in)</strong>
          </span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">
            Latency Target: <strong className="text-foreground font-mono">&lt; 15ms</strong>
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="border-border bg-muted text-[11px] text-foreground font-mono">
            Direct Logit Readout
          </Badge>
          <Badge variant="outline" className="border-border bg-muted text-[11px] text-foreground font-mono">
            Zero-Token Generation
          </Badge>
          <Badge variant="outline" className="border-border bg-muted text-[11px] text-foreground font-mono">
            LangSmith Traced
          </Badge>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {chips.map((chip, i) => (
          <button
            key={i}
            onClick={() => sendMessage(chip)}
            disabled={loading}
            className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition hover:border-foreground hover:bg-muted hover:text-foreground disabled:opacity-50 shadow-xs"
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
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground border border-border">
                    <Cpu className="size-4 text-foreground" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-xl p-4 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-primary text-primary-foreground font-medium shadow-xs'
                      : 'border border-border bg-card text-foreground'
                  }`}
                >
                  {m.role === 'assistant' && (m.tool || m.decisionProvider) && (
                    <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground border-b border-border pb-2">
                      {m.decisionProvider && (
                        <span className="rounded bg-muted px-2 py-0.5 font-mono text-foreground border border-border">
                          ⚡ {m.decisionProvider}
                        </span>
                      )}
                      {m.latencyMs !== undefined && (
                        <span className="rounded bg-muted px-2 py-0.5 font-mono text-foreground border border-border">
                          {m.latencyMs}ms
                        </span>
                      )}
                      {m.confidence !== undefined && (
                        <span className="rounded bg-muted px-2 py-0.5 font-mono text-foreground border border-border">
                          {Math.round(m.confidence * 100)}% Confidence
                        </span>
                      )}
                      {m.tool && (
                        <span className="rounded bg-primary text-primary-foreground px-2 py-0.5 font-mono text-[10px]">
                          Tool: {m.tool}
                        </span>
                      )}
                    </div>
                  )}

                  {m.role === 'assistant' ? (
                    <RichChatRenderer content={m.text} />
                  ) : (
                    <div className="whitespace-pre-wrap font-sans leading-relaxed">
                      {m.text}
                    </div>
                  )}

                  {m.role === 'assistant' && m.executionPlan && m.executionPlan.length > 0 && (
                    <div className="mt-3 border-t border-border pt-2 space-y-1">
                      <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">SemIf Execution Plan:</span>
                      <div className="space-y-0.5 font-mono text-[11px] text-muted-foreground">
                        {m.executionPlan.map((step, si) => (
                          <div key={si}>{step}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-3 text-sm text-foreground animate-pulse">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground border border-border shadow-xs">
                  <Sparkles className="size-4 animate-spin text-foreground" />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs">SemIf Decision Engine is evaluating logits and querying live AWS infrastructure...</span>
                  <span className="flex gap-1">
                    <span className="size-1 rounded-full bg-foreground animate-bounce [animation-delay:-0.3s]" />
                    <span className="size-1 rounded-full bg-foreground animate-bounce [animation-delay:-0.15s]" />
                    <span className="size-1 rounded-full bg-foreground animate-bounce" />
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
              placeholder="Ask Jew System Architect: e.g. 'Compare m5.2xlarge with Graviton pricing'..."
              disabled={loading}
              className="border-border bg-background text-foreground placeholder:text-muted-foreground font-mono text-xs"
            />
            <Button
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
              className="bg-primary text-primary-foreground hover:bg-primary/90 font-semibold"
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
