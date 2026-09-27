'use client'

import React, { useState } from 'react'
import { Check, Copy, Download, Terminal } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface CodeBlockProps {
  code: string
  language?: string
}

export function CodeBlock({ code, language = 'text' }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const isDiff = language.toLowerCase() === 'diff'
  const isTerraform = ['terraform', 'hcl', 'tf'].includes(language.toLowerCase())

  const copyCode = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const downloadCode = () => {
    const ext = isDiff ? 'diff' : isTerraform ? 'tf' : language === 'python' ? 'py' : language === 'json' ? 'json' : 'txt'
    const blob = new Blob([code], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cloudpulse-code.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  }

  const lines = code.trim().split('\n')

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-border bg-background shadow-xs">
      {/* Code Header Bar */}
      <div className="flex items-center justify-between border-b border-border bg-muted/40 px-3 py-1.5 text-xs">
        <div className="flex items-center gap-2 font-mono text-[11px] text-foreground font-semibold">
          <Terminal className="size-3.5" />
          <span>{language.toUpperCase()}</span>
          {isDiff && <span className="text-[10px] text-muted-foreground">(Unified Diff)</span>}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={downloadCode}
            className="h-6 px-2 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted"
            title="Download file"
          >
            <Download className="mr-1 size-3" />
            Download
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={copyCode}
            className="h-6 px-2 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted"
          >
            {copied ? <Check className="mr-1 size-3" /> : <Copy className="mr-1 size-3" />}
            {copied ? 'Copied' : 'Copy'}
          </Button>
        </div>
      </div>

      {/* Code Body */}
      <div className="overflow-x-auto p-3 font-mono text-xs leading-relaxed text-foreground">
        {lines.map((line, idx) => {
          if (isDiff) {
            const isAdd = line.startsWith('+') && !line.startsWith('+++')
            const isRemove = line.startsWith('-') && !line.startsWith('---')
            const isHeader = line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')

            return (
              <div
                key={idx}
                className={`flex gap-3 py-0.5 px-1 rounded-sm ${
                  isAdd
                    ? 'bg-foreground/10 text-foreground font-semibold'
                    : isRemove
                    ? 'line-through opacity-60 text-muted-foreground'
                    : isHeader
                    ? 'text-muted-foreground font-semibold'
                    : 'text-foreground'
                }`}
              >
                <span className="w-6 shrink-0 select-none text-right text-muted-foreground opacity-50 text-[10px]">
                  {idx + 1}
                </span>
                <span className="flex-1 whitespace-pre">{line}</span>
              </div>
            )
          }

          return (
            <div key={idx} className="flex gap-3 py-0.5 px-1 hover:bg-muted/30 rounded-sm">
              <span className="w-6 shrink-0 select-none text-right text-muted-foreground opacity-40 text-[10px]">
                {idx + 1}
              </span>
              <span className="flex-1 whitespace-pre">{line}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
export default CodeBlock
