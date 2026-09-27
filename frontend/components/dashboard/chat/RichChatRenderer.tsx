'use client'

import React from 'react'
import { MermaidDiagram } from './MermaidDiagram'
import { CodeBlock } from './CodeBlock'
import { Info, AlertTriangle, Lightbulb, ShieldAlert, CheckCircle2 } from 'lucide-react'

interface RichChatRendererProps {
  content: string
}

function formatInline(text: string): React.ReactNode {
  if (!text) return null
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g)

  return parts.map((part, idx) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 1) {
      return (
        <code
          key={idx}
          className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground font-medium"
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    if (part.startsWith('**') && part.endsWith('**') && part.length > 3) {
      return (
        <strong key={idx} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return (
        <em key={idx} className="italic text-foreground">
          {part.slice(1, -1)}
        </em>
      )
    }
    return part
  })
}

export function RichChatRenderer({ content }: RichChatRendererProps) {
  if (!content) return null

  // Tokenize content into blocks (code blocks, mermaid diagrams, alerts, paragraphs)
  const blocks: Array<{
    type: 'text' | 'code' | 'mermaid' | 'alert'
    language?: string
    alertType?: 'note' | 'warning' | 'tip' | 'important'
    content: string
  }> = []

  const lines = content.split('\n')
  let currentCode: string[] = []
  let currentLang = ''
  let inCodeBlock = false
  let currentText: string[] = []
  let inAlert = false
  let currentAlert: string[] = []
  let currentAlertType: 'note' | 'warning' | 'tip' | 'important' = 'note'

  const flushText = () => {
    if (currentText.length > 0) {
      blocks.push({ type: 'text', content: currentText.join('\n') })
      currentText = []
    }
  }

  const flushAlert = () => {
    if (currentAlert.length > 0) {
      blocks.push({
        type: 'alert',
        alertType: currentAlertType,
        content: currentAlert.join('\n'),
      })
      currentAlert = []
      inAlert = false
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // Fenced Code Block Detection
    if (trimmed.startsWith('```')) {
      if (inAlert) flushAlert()

      if (inCodeBlock) {
        // Closing code block
        const codeContent = currentCode.join('\n')
        if (currentLang.toLowerCase() === 'mermaid') {
          blocks.push({ type: 'mermaid', content: codeContent })
        } else {
          blocks.push({ type: 'code', language: currentLang || 'text', content: codeContent })
        }
        currentCode = []
        currentLang = ''
        inCodeBlock = false
      } else {
        // Opening code block
        flushText()
        currentLang = trimmed.slice(3).trim()
        inCodeBlock = true
      }
      continue
    }

    if (inCodeBlock) {
      currentCode.push(line)
      continue
    }

    // Callout / Alert Block Detection (> [!NOTE], > [!WARNING], > [!TIP])
    if (trimmed.startsWith('> [!') || trimmed.startsWith('>[!')) {
      flushText()
      inAlert = true
      const alertMatch = trimmed.match(/>\s*\[!(NOTE|WARNING|TIP|IMPORTANT|CAUTION)\]/i)
      const tag = alertMatch ? alertMatch[1].toLowerCase() : 'note'
      currentAlertType = (tag === 'caution' ? 'warning' : tag) as any
      continue
    }

    if (inAlert) {
      if (trimmed.startsWith('>')) {
        currentAlert.push(trimmed.replace(/^>\s?/, ''))
        continue
      } else {
        flushAlert()
      }
    }

    currentText.push(line)
  }

  if (inCodeBlock) {
    const codeContent = currentCode.join('\n')
    if (currentLang.toLowerCase() === 'mermaid') {
      blocks.push({ type: 'mermaid', content: codeContent })
    } else {
      blocks.push({ type: 'code', language: currentLang || 'text', content: codeContent })
    }
  }

  if (inAlert) flushAlert()
  flushText()

  return (
    <div className="space-y-2 text-sm leading-relaxed text-foreground">
      {blocks.map((block, bIdx) => {
        if (block.type === 'mermaid') {
          return <MermaidDiagram key={bIdx} chart={block.content} id={`diag-${bIdx}`} />
        }

        if (block.type === 'code') {
          return <CodeBlock key={bIdx} code={block.content} language={block.language} />
        }

        if (block.type === 'alert') {
          const isWarning = block.alertType === 'warning'
          const isTip = block.alertType === 'tip'
          const isImportant = block.alertType === 'important'

          return (
            <div
              key={bIdx}
              className="my-3 flex items-start gap-3 rounded-xl border border-border bg-card p-3.5 shadow-xs"
            >
              <div className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-lg border border-border bg-muted text-foreground">
                {isWarning ? (
                  <AlertTriangle className="size-3.5" />
                ) : isTip ? (
                  <Lightbulb className="size-3.5" />
                ) : isImportant ? (
                  <ShieldAlert className="size-3.5" />
                ) : (
                  <Info className="size-3.5" />
                )}
              </div>
              <div className="flex-1 space-y-1 text-xs leading-relaxed text-foreground">
                <div className="font-semibold uppercase tracking-wider text-[10px] text-muted-foreground">
                  {block.alertType}
                </div>
                <div>{formatInline(block.content)}</div>
              </div>
            </div>
          )
        }

        // Standard Text Rendering
        const textLines = block.content.split('\n')
        return (
          <div key={bIdx} className="space-y-1.5">
            {textLines.map((tLine, lIdx) => {
              const trimmed = tLine.trim()
              if (!trimmed) return <div key={lIdx} className="h-1" />

              // Headers
              if (trimmed.startsWith('### ')) {
                return (
                  <h4 key={lIdx} className="text-sm font-semibold text-foreground mt-3 mb-1">
                    {trimmed.slice(4)}
                  </h4>
                )
              }
              if (trimmed.startsWith('## ')) {
                return (
                  <h3 key={lIdx} className="text-base font-bold text-foreground mt-4 mb-1 border-b border-border pb-1">
                    {trimmed.slice(3)}
                  </h3>
                )
              }
              if (trimmed.startsWith('# ')) {
                return (
                  <h2 key={lIdx} className="text-lg font-bold text-foreground mt-4 mb-2">
                    {trimmed.slice(2)}
                  </h2>
                )
              }

              // Bullet List
              if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                return (
                  <div key={lIdx} className="flex items-start gap-2.5 pl-2 py-0.5">
                    <span className="mt-1.5 size-1.5 rounded-full bg-foreground shrink-0" />
                    <span className="flex-1">{formatInline(trimmed.slice(2))}</span>
                  </div>
                )
              }

              // Numbered List
              const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/)
              if (numMatch) {
                return (
                  <div key={lIdx} className="flex items-start gap-2.5 pl-2 py-0.5 font-mono text-xs">
                    <span className="font-bold text-foreground select-none shrink-0 w-4">
                      {numMatch[1]}.
                    </span>
                    <span className="flex-1 font-sans text-sm">{formatInline(numMatch[2])}</span>
                  </div>
                )
              }

              return <p key={lIdx}>{formatInline(tLine)}</p>
            })}
          </div>
        )
      })}
    </div>
  )
}
export default RichChatRenderer
