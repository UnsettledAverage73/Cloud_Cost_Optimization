'use client'

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

interface Props {
  children: ReactNode
  title?: string
  description?: string
  fallback?: ReactNode
  onReset?: () => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export class SectionErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[SectionErrorBoundary:${this.props.title || 'Widget'}] caught an error:`, error, errorInfo)
  }

  public reset = () => {
    this.setState({ hasError: false, error: null })
    if (this.props.onReset) {
      this.props.onReset()
    }
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <Card className="my-4 border-red-500/20 bg-red-500/5 text-foreground backdrop-blur-sm">
          <CardContent className="flex flex-col items-center justify-center p-8 text-center sm:p-10">
            <div className="flex size-12 items-center justify-center rounded-full border border-red-500/30 bg-red-500/10 text-red-400 shadow-inner">
              <AlertTriangle className="size-6" />
            </div>

            <h3 className="mt-4 text-base font-semibold text-red-200 sm:text-lg">
              {this.props.title ? `${this.props.title} Temporarily Unavailable` : 'Section Encountered an Issue'}
            </h3>

            <p className="mt-2 max-w-md text-xs text-muted-foreground sm:text-sm">
              {this.props.description || 'This component encountered an unexpected error while rendering data. Other dashboard features remain unaffected.'}
            </p>

            {this.state.error?.message && (
              <div className="mt-3 max-w-lg overflow-x-auto rounded border border-white/5 bg-black/40 px-3 py-1.5 font-mono text-[11px] text-red-300/80">
                {this.state.error.message}
              </div>
            )}

            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={this.reset}
                className="border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 hover:text-red-200"
              >
                <RefreshCw className="mr-1.5 size-3.5" />
                Retry Component
              </Button>
            </div>
          </CardContent>
        </Card>
      )
    }

    return this.props.children
  }
}
