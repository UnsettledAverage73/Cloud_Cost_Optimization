export interface Breadcrumb {
  timestamp: string
  category: 'ui' | 'navigation' | 'api' | 'state' | 'system'
  message: string
  level?: 'info' | 'warning' | 'error'
  data?: Record<string, unknown>
}

export interface CapturedError {
  id: string
  timestamp: string
  message: string
  stack?: string
  component?: string
  tags?: Record<string, string>
  extra?: Record<string, unknown>
  breadcrumbs: Breadcrumb[]
}

class MonitoringService {
  private static instance: MonitoringService
  private breadcrumbs: Breadcrumb[] = []
  private readonly maxBreadcrumbs = 30
  private recentErrors: CapturedError[] = []
  private readonly maxErrors = 20
  private initialized = false
  private dsn: string | null = null

  private constructor() {
    if (typeof window !== 'undefined') {
      this.dsn = process.env.NEXT_PUBLIC_SENTRY_DSN || null
    }
  }

  public static getInstance(): MonitoringService {
    if (!MonitoringService.instance) {
      MonitoringService.instance = new MonitoringService()
    }
    return MonitoringService.instance
  }

  public init() {
    if (this.initialized || typeof window === 'undefined') return
    this.initialized = true

    // Capture unhandled global exceptions
    window.addEventListener('error', (event: ErrorEvent) => {
      this.captureException(event.error || new Error(event.message), {
        category: 'unhandled_error',
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      })
    })

    // Capture unhandled promise rejections
    window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
      const reason = event.reason
      const error = reason instanceof Error ? reason : new Error(String(reason))
      this.captureException(error, {
        category: 'unhandled_promise_rejection',
      })
    })

    this.addBreadcrumb({
      category: 'system',
      message: 'Monitoring initialized',
      level: 'info',
      data: {
        env: process.env.NODE_ENV,
        userAgent: navigator.userAgent,
      },
    })
  }

  public addBreadcrumb(breadcrumb: Omit<Breadcrumb, 'timestamp'>) {
    const entry: Breadcrumb = {
      ...breadcrumb,
      timestamp: new Date().toISOString(),
    }
    this.breadcrumbs.push(entry)
    if (this.breadcrumbs.length > this.maxBreadcrumbs) {
      this.breadcrumbs.shift()
    }
  }

  public captureException(error: unknown, context?: {
    component?: string
    tags?: Record<string, string>
    extra?: Record<string, unknown>
    [key: string]: unknown
  }): string {
    const errorId = `err_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`
    const isError = error instanceof Error
    const message = isError ? error.message : String(error)
    const stack = isError ? error.stack : undefined

    const captured: CapturedError = {
      id: errorId,
      timestamp: new Date().toISOString(),
      message,
      stack,
      component: context?.component,
      tags: context?.tags,
      extra: context?.extra,
      breadcrumbs: [...this.breadcrumbs],
    }

    this.recentErrors.unshift(captured)
    if (this.recentErrors.length > this.maxErrors) {
      this.recentErrors.pop()
    }

    // Always log formatted error telemetry
    if (process.env.NODE_ENV !== 'production') {
      console.warn(`[Monitoring] Captured Exception (${errorId}):`, {
        error,
        context,
        breadcrumbs: captured.breadcrumbs,
      })
    }

    // If Sentry DSN is configured, dispatch envelope to Sentry API
    if (this.dsn && typeof window !== 'undefined') {
      this.dispatchToSentry(captured)
    }

    return errorId
  }

  public captureMessage(message: string, level: 'info' | 'warning' | 'error' = 'info', extra?: Record<string, unknown>) {
    this.addBreadcrumb({
      category: 'system',
      message,
      level,
      data: extra,
    })
  }

  public getRecentErrors(): CapturedError[] {
    return [...this.recentErrors]
  }

  public getRecentBreadcrumbs(): Breadcrumb[] {
    return [...this.breadcrumbs]
  }

  public clear() {
    this.breadcrumbs = []
    this.recentErrors = []
  }

  private dispatchToSentry(error: CapturedError) {
    try {
      if (!this.dsn) return
      // Sentry envelope dispatch mock/real implementation
      const payload = {
        event_id: error.id.replace('err_', ''),
        timestamp: new Date(error.timestamp).getTime() / 1000,
        level: 'error',
        platform: 'javascript',
        exception: {
          values: [
            {
              type: error.message.split(':')[0] || 'Error',
              value: error.message,
              stacktrace: error.stack ? { frames: [{ filename: 'bundle.js', function: error.component || 'anonymous' }] } : undefined,
            },
          ],
        },
        breadcrumbs: error.breadcrumbs.map((b) => ({
          timestamp: new Date(b.timestamp).getTime() / 1000,
          category: b.category,
          message: b.message,
          level: b.level || 'info',
          data: b.data,
        })),
        tags: error.tags,
        extra: error.extra,
      }

      // Best-effort sendBeacon or fetch
      if (typeof navigator !== 'undefined' && 'sendBeacon' in navigator) {
        navigator.sendBeacon(this.dsn, JSON.stringify(payload))
      }
    } catch {
      // Avoid recursive crash from error reporting
    }
  }
}

export const monitoring = MonitoringService.getInstance()
export const captureException = (err: unknown, context?: Record<string, unknown>) =>
  monitoring.captureException(err, context)
export const addBreadcrumb = (crumb: Omit<Breadcrumb, 'timestamp'>) =>
  monitoring.addBreadcrumb(crumb)
export const captureMessage = (msg: string, level?: 'info' | 'warning' | 'error', extra?: Record<string, unknown>) =>
  monitoring.captureMessage(msg, level, extra)
