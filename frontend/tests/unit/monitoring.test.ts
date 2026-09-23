import { describe, it, expect, beforeEach } from 'vitest'
import { monitoring, captureException, addBreadcrumb, captureMessage } from '@/lib/monitoring/logger'

describe('Real-Time Error Monitoring & Tracking', () => {
  beforeEach(() => {
    monitoring.clear()
  })

  it('records and retrieves breadcrumbs with timestamps', () => {
    addBreadcrumb({
      category: 'navigation',
      message: 'Navigated to /inventory',
      level: 'info',
    })

    addBreadcrumb({
      category: 'ui',
      message: 'Filtered instances by running state',
      level: 'info',
    })

    const breadcrumbs = monitoring.getRecentBreadcrumbs()
    expect(breadcrumbs.length).toBe(2)
    expect(breadcrumbs[0].message).toBe('Navigated to /inventory')
    expect(breadcrumbs[1].category).toBe('ui')
    expect(breadcrumbs[1].timestamp).toBeDefined()
  })

  it('captures exceptions with stack traces, component name, and tags', () => {
    const error = new Error('Database connection timed out')
    const errorId = captureException(error, {
      component: 'DatabaseOptimizer',
      tags: { severity: 'high', environment: 'test' },
      extra: { query: 'SELECT * FROM metrics' },
    })

    expect(errorId).toMatch(/^err_\d+_[a-z0-9]+$/)

    const recentErrors = monitoring.getRecentErrors()
    expect(recentErrors.length).toBe(1)
    expect(recentErrors[0].message).toBe('Database connection timed out')
    expect(recentErrors[0].component).toBe('DatabaseOptimizer')
    expect(recentErrors[0].tags?.environment).toBe('test')
    expect(recentErrors[0].extra?.query).toBe('SELECT * FROM metrics')
  })

  it('attaches current breadcrumbs snapshot to captured exceptions', () => {
    addBreadcrumb({
      category: 'api',
      message: 'GET /api/v1/dashboard/summary',
      level: 'info',
    })

    const error = new Error('500 Internal Server Error')
    captureException(error, { component: 'OverviewView' })

    const recentErrors = monitoring.getRecentErrors()
    expect(recentErrors[0].breadcrumbs.length).toBe(1)
    expect(recentErrors[0].breadcrumbs[0].message).toBe('GET /api/v1/dashboard/summary')
  })

  it('captures messages with severity levels', () => {
    captureMessage('Cache warm-up completed', 'info', { itemsCached: 42 })
    const breadcrumbs = monitoring.getRecentBreadcrumbs()
    expect(breadcrumbs[breadcrumbs.length - 1].message).toBe('Cache warm-up completed')
    expect(breadcrumbs[breadcrumbs.length - 1].level).toBe('info')
  })
})
