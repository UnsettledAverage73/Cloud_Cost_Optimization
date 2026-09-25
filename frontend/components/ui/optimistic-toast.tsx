'use client'

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { CheckCircle2, AlertCircle, Info, Zap, X, ShieldCheck, Sparkles } from 'lucide-react'

export interface OptimisticToastItem {
  id: string
  title: string
  description?: string
  type?: 'success' | 'info' | 'warning' | 'error' | 'security'
  duration?: number
}

interface OptimisticToastContextType {
  toast: (options: Omit<OptimisticToastItem, 'id'>) => void
  dismiss: (id: string) => void
}

const OptimisticToastContext = createContext<OptimisticToastContextType | null>(null)

export function useOptimisticToast() {
  const ctx = useContext(OptimisticToastContext)
  if (!ctx) {
    return {
      toast: () => {},
      dismiss: () => {},
    }
  }
  return ctx
}

export function OptimisticToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<OptimisticToastItem[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const toast = useCallback(({ title, description, type = 'success', duration = 3800 }: Omit<OptimisticToastItem, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
    setToasts(prev => [
      ...prev.slice(-3), // keep maximum 4 active toasts to avoid clutter
      { id, title, description, type, duration }
    ])

    if (duration > 0) {
      setTimeout(() => {
        dismiss(id)
      }, duration)
    }
  }, [dismiss])

  return (
    <OptimisticToastContext.Provider value={{ toast, dismiss }}>
      {children}
      {/* Floating Toast Container */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none px-4 sm:px-0">
        {toasts.map(t => {
          const isSuccess = t.type === 'success'
          const isSecurity = t.type === 'security'
          const isWarning = t.type === 'warning'
          const isError = t.type === 'error'

          const borderStyle = isSuccess
            ? 'border-emerald-500/30 bg-slate-950/90 text-foreground shadow-[0_8px_32px_-4px_rgba(16,185,129,0.25)]'
            : isSecurity
            ? 'border-cyan-500/30 bg-slate-950/90 text-foreground shadow-[0_8px_32px_-4px_rgba(6,182,212,0.25)]'
            : isWarning
            ? 'border-amber-500/30 bg-slate-950/90 text-foreground shadow-[0_8px_32px_-4px_rgba(245,158,11,0.25)]'
            : isError
            ? 'border-rose-500/30 bg-slate-950/90 text-foreground shadow-[0_8px_32px_-4px_rgba(244,63,94,0.25)]'
            : 'border-white/15 bg-slate-950/90 text-foreground shadow-xl'

          const iconColor = isSuccess
            ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
            : isSecurity
            ? 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20'
            : isWarning
            ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
            : isError
            ? 'text-rose-400 bg-rose-500/10 border-rose-500/20'
            : 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20'

          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-start gap-3 rounded-xl border p-3.5 backdrop-blur-xl animate-optimistic-pop transition-all ${borderStyle}`}
            >
              <div className={`flex size-8 shrink-0 items-center justify-center rounded-lg border ${iconColor}`}>
                {isSuccess && <CheckCircle2 className="size-4" />}
                {isSecurity && <ShieldCheck className="size-4" />}
                {isWarning && <AlertCircle className="size-4" />}
                {isError && <AlertCircle className="size-4" />}
                {t.type === 'info' && <Zap className="size-4" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-semibold text-foreground tracking-tight">{t.title}</span>
                  <span className="inline-block size-1.5 rounded-full bg-cyan-400 animate-pulse" />
                </div>
                {t.description && (
                  <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground break-words">
                    {t.description}
                  </p>
                )}
              </div>
              <button
                onClick={() => dismiss(t.id)}
                className="size-6 -mr-1 -mt-1 flex items-center justify-center rounded-md text-muted-foreground/60 hover:text-foreground hover:bg-white/5 transition-colors"
                aria-label="Dismiss notification"
              >
                <X className="size-3.5" />
              </button>
            </div>
          )
        })}
      </div>
    </OptimisticToastContext.Provider>
  )
}
