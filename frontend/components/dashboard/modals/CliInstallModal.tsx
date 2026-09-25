'use client'

import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Terminal,
  Check,
  Copy,
  Sparkles,
  ExternalLink,
  Laptop,
  CheckCircle2,
  Code2,
  Zap,
} from 'lucide-react'

interface CliInstallModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  backendUrl?: string
}

export function CliInstallModal({
  open,
  onOpenChange,
  backendUrl = 'https://cloud-cost-optimization.onrender.com',
}: CliInstallModalProps) {
  const [copied, setCopied] = useState<string | null>(null)
  const [detectedOs, setDetectedOs] = useState<'linux' | 'macos' | 'windows'>('linux')

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const ua = window.navigator.userAgent.toLowerCase()
      if (ua.includes('win')) {
        setDetectedOs('windows')
      } else if (ua.includes('mac') || ua.includes('darwin')) {
        setDetectedOs('macos')
      } else {
        setDetectedOs('linux')
      }
    }
  }, [])

  const copyToClipboard = (text: string, id: string) => {
    if (typeof navigator !== 'undefined') {
      navigator.clipboard.writeText(text)
      setCopied(id)
      setTimeout(() => setCopied(null), 2500)
    }
  }

  const linuxCmd = `curl -fsSL ${backendUrl}/install.sh | bash`
  const macCmd = `curl -fsSL ${backendUrl}/install.sh | bash`
  const winCmd = `irm ${backendUrl}/install.ps1 | iex`
  const pipxCmd = `pipx install git+https://github.com/UnsettledAverage73/Cloud_Cost_Optimization.git`
  const pipCmd = `pip install git+https://github.com/UnsettledAverage73/Cloud_Cost_Optimization.git`

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-border bg-card sm:max-w-2xl max-h-[92vh] overflow-y-auto shadow-2xl p-0 gap-0">
        {/* Header Banner */}
        <div className="border-b border-border p-6 bg-gradient-to-r from-sky-500/10 via-cyan-500/5 to-transparent">
          <div className="flex items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-sky-600 text-white shadow-sm">
              <Terminal className="size-5" />
            </div>
            <div>
              <DialogTitle className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
                Install CloudPulse CLI
                <Badge variant="outline" className="border-sky-500/30 text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-500/10 text-[10px] font-mono">
                  v2.0 Standalone
                </Badge>
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Run FinOps audits, live telemetry, and AI Copilot directly from your terminal. No repository clone needed.
              </DialogDescription>
            </div>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* OS Auto-Detection Pill */}
          <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3.5 py-2 text-xs">
            <div className="flex items-center gap-2">
              <Laptop className="size-4 text-sky-600 dark:text-sky-400" />
              <span className="text-muted-foreground">Auto-detected OS:</span>
              <strong className="text-foreground capitalize">{detectedOs === 'macos' ? 'macOS (Darwin)' : detectedOs}</strong>
            </div>
            <span className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
              <CheckCircle2 className="size-3.5" /> 1-Step Command Ready
            </span>
          </div>

          {/* Installation Tabs */}
          <Tabs defaultValue={detectedOs} className="w-full">
            <TabsList className="grid grid-cols-4 h-9 p-0.5 bg-muted/60">
              <TabsTrigger value="linux" className="text-xs font-medium">
                🐧 Linux
              </TabsTrigger>
              <TabsTrigger value="macos" className="text-xs font-medium">
                🍎 macOS
              </TabsTrigger>
              <TabsTrigger value="windows" className="text-xs font-medium">
                🪟 Windows
              </TabsTrigger>
              <TabsTrigger value="pip" className="text-xs font-medium">
                🐍 Python / pipx
              </TabsTrigger>
            </TabsList>

            {/* Linux Tab */}
            <TabsContent value="linux" className="mt-4 space-y-3">
              <div className="text-xs text-muted-foreground flex items-center justify-between">
                <span>Copy and paste into your Linux terminal (Ubuntu, Debian, Fedora, Arch, Alpine):</span>
                <span className="text-[10px] font-mono text-muted-foreground/80">POSIX sh/bash</span>
              </div>
              <div className="group relative rounded-xl border border-border bg-slate-950 p-4 font-mono text-xs text-slate-100 shadow-sm">
                <div className="flex items-center justify-between gap-2 overflow-x-auto pr-16 py-1">
                  <span className="text-emerald-400 select-none">$</span>
                  <span className="text-sky-300 font-semibold">{linuxCmd}</span>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  className="absolute right-2 top-2.5 h-8 px-2.5 text-xs bg-slate-800 hover:bg-slate-700 text-white border border-slate-700"
                  onClick={() => copyToClipboard(linuxCmd, 'linux')}
                >
                  {copied === 'linux' ? (
                    <>
                      <Check className="mr-1.5 size-3.5 text-emerald-400" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="mr-1.5 size-3.5" /> Copy
                    </>
                  )}
                </Button>
              </div>
              <p className="text-[11px] text-muted-foreground">
                • Automatically creates an isolated virtual environment, installs the global <code className="text-foreground font-mono">cloudpulse</code> binary, and configures your <code className="text-foreground font-mono">$PATH</code>.
              </p>
            </TabsContent>

            {/* macOS Tab */}
            <TabsContent value="macos" className="mt-4 space-y-3">
              <div className="text-xs text-muted-foreground flex items-center justify-between">
                <span>Open Terminal or iTerm2 on your Mac (Apple Silicon M1/M2/M3/M4 or Intel):</span>
                <span className="text-[10px] font-mono text-muted-foreground/80">zsh/bash</span>
              </div>
              <div className="group relative rounded-xl border border-border bg-slate-950 p-4 font-mono text-xs text-slate-100 shadow-sm">
                <div className="flex items-center justify-between gap-2 overflow-x-auto pr-16 py-1">
                  <span className="text-emerald-400 select-none">$</span>
                  <span className="text-sky-300 font-semibold">{macCmd}</span>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  className="absolute right-2 top-2.5 h-8 px-2.5 text-xs bg-slate-800 hover:bg-slate-700 text-white border border-slate-700"
                  onClick={() => copyToClipboard(macCmd, 'macos')}
                >
                  {copied === 'macos' ? (
                    <>
                      <Check className="mr-1.5 size-3.5 text-emerald-400" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="mr-1.5 size-3.5" /> Copy
                    </>
                  )}
                </Button>
              </div>
              <p className="text-[11px] text-muted-foreground">
                • Installs to <code className="text-foreground font-mono">~/.local/bin/cloudpulse</code> and automatically sets your shell configuration (<code className="text-foreground font-mono">~/.zshrc</code>).
              </p>
            </TabsContent>

            {/* Windows Tab */}
            <TabsContent value="windows" className="mt-4 space-y-3">
              <div className="text-xs text-muted-foreground flex items-center justify-between">
                <span>Open PowerShell (or Windows Terminal) as standard user:</span>
                <span className="text-[10px] font-mono text-muted-foreground/80">PowerShell 5.1+ / pwsh 7+</span>
              </div>
              <div className="group relative rounded-xl border border-border bg-slate-950 p-4 font-mono text-xs text-slate-100 shadow-sm">
                <div className="flex items-center justify-between gap-2 overflow-x-auto pr-16 py-1">
                  <span className="text-emerald-400 select-none">PS&gt;</span>
                  <span className="text-sky-300 font-semibold">{winCmd}</span>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  className="absolute right-2 top-2.5 h-8 px-2.5 text-xs bg-slate-800 hover:bg-slate-700 text-white border border-slate-700"
                  onClick={() => copyToClipboard(winCmd, 'windows')}
                >
                  {copied === 'windows' ? (
                    <>
                      <Check className="mr-1.5 size-3.5 text-emerald-400" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="mr-1.5 size-3.5" /> Copy
                    </>
                  )}
                </Button>
              </div>
              <p className="text-[11px] text-muted-foreground">
                • Automatically configures <code className="text-foreground font-mono">%USERPROFILE%\.cloudpulse\bin</code> in your Windows User PATH environment variable.
              </p>
            </TabsContent>

            {/* Pip / Pipx Tab */}
            <TabsContent value="pip" className="mt-4 space-y-3">
              <div className="text-xs text-muted-foreground">
                If you already have <code className="font-mono text-foreground">pipx</code> or Python installed:
              </div>
              <div className="space-y-2">
                <div className="group relative rounded-xl border border-border bg-slate-950 p-3.5 font-mono text-xs text-slate-100 shadow-sm">
                  <div className="flex items-center justify-between gap-2 overflow-x-auto pr-16 py-0.5">
                    <span className="text-sky-300 font-semibold">{pipxCmd}</span>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    className="absolute right-2 top-2 h-7 px-2 text-xs bg-slate-800 hover:bg-slate-700 text-white"
                    onClick={() => copyToClipboard(pipxCmd, 'pipx')}
                  >
                    {copied === 'pipx' ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                  </Button>
                </div>
                <div className="group relative rounded-xl border border-border bg-slate-950 p-3.5 font-mono text-xs text-slate-100 shadow-sm">
                  <div className="flex items-center justify-between gap-2 overflow-x-auto pr-16 py-0.5">
                    <span className="text-sky-300 font-semibold">{pipCmd}</span>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    className="absolute right-2 top-2 h-7 px-2 text-xs bg-slate-800 hover:bg-slate-700 text-white"
                    onClick={() => copyToClipboard(pipCmd, 'pip')}
                  >
                    {copied === 'pip' ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                  </Button>
                </div>
              </div>
            </TabsContent>
          </Tabs>

          {/* Quick Verification & Commands Grid */}
          <div className="rounded-xl border border-border bg-muted/20 p-4 space-y-3">
            <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <Zap className="size-3.5 text-amber-500" />
              Instant Verification & Presentation Commands
            </div>
            <div className="grid gap-2 sm:grid-cols-2 text-xs font-mono">
              <div className="rounded-lg border border-border bg-card p-2.5 flex items-center justify-between">
                <div>
                  <div className="text-sky-600 dark:text-sky-400 font-semibold">cloudpulse status</div>
                  <div className="text-[11px] font-sans text-muted-foreground">Test database & telemetry health</div>
                </div>
              </div>
              <div className="rounded-lg border border-border bg-card p-2.5 flex items-center justify-between">
                <div>
                  <div className="text-emerald-600 dark:text-emerald-400 font-semibold">cloudpulse audit</div>
                  <div className="text-[11px] font-sans text-muted-foreground">Run FinOps spend & waste audit</div>
                </div>
              </div>
              <div className="rounded-lg border border-border bg-card p-2.5 flex items-center justify-between">
                <div>
                  <div className="text-purple-600 dark:text-purple-400 font-semibold">cloudpulse inspect</div>
                  <div className="text-[11px] font-sans text-muted-foreground">10-category multi-cloud inventory</div>
                </div>
              </div>
              <div className="rounded-lg border border-border bg-card p-2.5 flex items-center justify-between">
                <div>
                  <div className="text-amber-600 dark:text-amber-400 font-semibold">cloudpulse pov --open</div>
                  <div className="text-[11px] font-sans text-muted-foreground">Generate interactive HTML dossier</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border px-6 py-3 bg-muted/30 text-xs">
          <div className="text-muted-foreground flex items-center gap-1.5">
            <Sparkles className="size-3.5 text-sky-600 dark:text-sky-400" />
            Zero dependencies required · Uses standard Python 3.8+
          </div>
          <Button
            size="sm"
            variant="outline"
            className="border-border bg-card hover:bg-muted"
            onClick={() => onOpenChange(false)}
          >
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
